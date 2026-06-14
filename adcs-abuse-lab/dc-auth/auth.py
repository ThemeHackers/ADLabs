import http.server
import socketserver
import subprocess
import os
import urllib.parse
import re

PORT = 8000
CA_CERT = "/tmp/ca/ca.crt" # Mounted from shared volume

class PKINITAuthHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/" or self.path == "/pkinit":
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            
            # Simple form to paste cert
            html = """<!DOCTYPE html>
<html>
<head>
    <title>PKINIT Authentication Gateway</title>
    <style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f4f4f9; padding: 20px; }
        .container { max-width: 800px; background: white; padding: 35px; border-radius: 8px; box-shadow: 0 4px 15px rgba(0,0,0,0.1); margin: auto; }
        h2 { color: #0078d4; border-bottom: 2px solid #0078d4; padding-bottom: 10px; margin-top: 0; }
        label { font-weight: bold; display: block; margin-top: 15px; }
        textarea { width: 100%; height: 180px; font-family: monospace; padding: 10px; border: 1px solid #ccc; border-radius: 4px; box-sizing: border-box; }
        input[type="submit"] { background-color: #0078d4; color: white; padding: 12px 20px; border: none; border-radius: 4px; cursor: pointer; font-size: 16px; margin-top: 20px; font-weight: bold; }
        input[type="submit"]:hover { background-color: #005a9e; }
    </style>
</head>
<body>
    <div class="container">
        <h2>PKINIT Mock Authentication Gateway (ADCSLAB.LOCAL)</h2>
        <p>Paste your issued PEM certificate here to authenticate and request the NT hash of your session ticket.</p>
        <form method="POST" action="/pkinit">
            <label for="cert">PEM Certificate:</label>
            <textarea name="cert" id="cert" placeholder="-----BEGIN CERTIFICATE-----&#10;...&#10;-----END CERTIFICATE-----" required></textarea>
            <input type="submit" value="Authenticate & Get NT Hash">
        </form>
    </div>
</body>
</html>
"""
            self.wfile.write(html.encode("utf-8"))
        else:
            self.send_error(404, "Not Found")

    def do_POST(self):
        if self.path == "/pkinit":
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length).decode('utf-8')
            params = urllib.parse.parse_qs(post_data)
            
            cert_data = params.get('cert', [''])[0].strip()
            if not cert_data:
                self.send_response(400)
                self.wfile.write(b"Error: Certificate is empty.")
                return

            # Save cert to temp file
            cert_path = "/tmp/client.crt"
            with open(cert_path, "w") as f:
                f.write(cert_data)

            # 1. Verify certificate against Root CA
            if not os.path.exists(CA_CERT):
                self.send_response(500)
                self.send_header("Content-type", "text/plain")
                self.end_headers()
                self.wfile.write(b"Error: Root CA certificate not found on Domain Controller. PKI setup incomplete.")
                return

            verify_cmd = ["openssl", "verify", "-CAfile", CA_CERT, cert_path]
            res_verify = subprocess.run(verify_cmd, capture_output=True, text=True)
            
            if res_verify.returncode != 0:
                self.send_response(403)
                self.send_header("Content-type", "text/html; charset=utf-8")
                self.end_headers()
                html = f"""<html><body><h2>Authentication Failed</h2><p>Certificate signature is invalid or not signed by the Trusted CA.</p><pre>{res_verify.stderr}</pre></body></html>"""
                self.wfile.write(html.encode("utf-8"))
                return

            # 2. Extract SAN (UPN)
            san_cmd = ["openssl", "x509", "-in", cert_path, "-noout", "-ext", "subjectAltName"]
            res_san = subprocess.run(san_cmd, capture_output=True, text=True)
            
            # Search for UPN (UTF8 string in subjectAltName)
            # The structure in openssl output usually looks like:
            # "otherName: 1.3.6.1.4.1.311.20.2.3;UTF8::username@domain.local"
            # or "otherName: 1.3.6.1.4.1.311.20.2.3;UTF8:username@domain.local"
            san_text = res_san.stdout
            upn_match = re.search(r"UTF8::?([^,\s\n]+)", san_text)
            
            if not upn_match:
                self.send_response(403)
                self.send_header("Content-type", "text/html; charset=utf-8")
                self.end_headers()
                html = f"""<html><body><h2>Authentication Failed</h2><p>Certificate is valid, but no User Principal Name (UPN) Subject Alternative Name (SAN) was found.</p><pre>{san_text}</pre></body></html>"""
                self.wfile.write(html.encode("utf-8"))
                return

            upn = upn_match.group(1)
            # Extract sAMAccountName from UPN (e.g. Administrator@ADCSLAB.LOCAL -> Administrator)
            username = upn.split("@")[0]
            
            print(f"Authenticating user: {username} (UPN: {upn})", flush=True)

            # 3. Retrieve NT Hash via samba-tool
            samba_cmd = [
                "samba-tool", "user", "getpassword", username,
                "--configfile=/samba/etc/smb.conf"
            ]
            res_samba = subprocess.run(samba_cmd, capture_output=True, text=True)
            
            if res_samba.returncode != 0:
                self.send_response(500)
                self.send_header("Content-type", "text/html; charset=utf-8")
                self.end_headers()
                html = f"""<html><body><h2>Internal Error</h2><p>Samba could not locate user '{username}'.</p><pre>{res_samba.stderr}</pre></body></html>"""
                self.wfile.write(html.encode("utf-8"))
                return

            # Extract NT Hash from output
            # Output of samba-tool user getpassword username contains:
            # "nthash: <hash>"
            samba_out = res_samba.stdout
            hash_match = re.search(r"nthash:\s*([a-fA-F0-9]{32})", samba_out)
            
            if not hash_match:
                self.send_response(500)
                self.send_header("Content-type", "text/html; charset=utf-8")
                self.end_headers()
                html = f"""<html><body><h2>Internal Error</h2><p>Could not extract NT Hash from Samba database output.</p><pre>{samba_out}</pre></body></html>"""
                self.wfile.write(html.encode("utf-8"))
                return
                
            nthash = hash_match.group(1)

            # Return success and NT Hash!
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            
            html = f"""<!DOCTYPE html>
<html>
<head>
    <title>PKINIT Authentication Succeeded</title>
    <style>
        body {{ font-family: 'Segoe UI', sans-serif; background-color: #f4f4f9; padding: 20px; }}
        .container {{ max-width: 800px; background: white; padding: 35px; border-radius: 8px; box-shadow: 0 4px 15px rgba(0,0,0,0.1); margin: auto; }}
        h2 {{ color: #107c41; border-bottom: 2px solid #107c41; padding-bottom: 10px; }}
        .success-box {{ border-left: 6px solid #107c41; background-color: #f3fcf5; padding: 15px; margin-bottom: 20px; }}
        pre {{ background-color: #f0f0f0; padding: 15px; border-radius: 4px; font-family: monospace; overflow-x: auto; font-size: 16px; font-weight: bold; }}
    </style>
</head>
<body>
    <div class="container">
        <h2>PKINIT Authentication Succeeded!</h2>
        <div class="success-box">
            <p><strong>Authenticated Principal (UPN):</strong> {upn}</p>
            <p><strong>sAMAccountName:</strong> {username}</p>
        </div>
        
        <p>Below is your Session NT Hash. You can use this for Pass-the-Hash (PtH) or authentication attacks:</p>
        <pre>{nthash}</pre>
        
        <p><strong>NXC / Impacket PtH Command Example:</strong></p>
        <pre>impacket-wmiexec -hashes 'aad3b435b51404eeaad3b435b51404ee:{nthash}' ADCSLAB.LOCAL/{username}@10.102.10.10</pre>
        
        <a href="/pkinit">Back to Login Gateway</a>
    </div>
</body>
</html>
"""
            self.wfile.write(html.encode("utf-8"))
        else:
            self.send_error(404, "Not Found")

if __name__ == "__main__":
    handler = PKINITAuthHandler
    with socketserver.TCPServer(("", PORT), handler) as httpd:
        print(f"PKINIT Auth Gateway running on port {PORT}...", flush=True)
        httpd.serve_forever()
