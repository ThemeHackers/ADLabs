import http.server
import socketserver
import subprocess
import os
import urllib.parse

PORT = 80
CA_DIR = "/tmp/ca"
CA_KEY = os.path.join(CA_DIR, "ca.key")
CA_CERT = os.path.join(CA_DIR, "ca.crt")

def init_ca():
    os.makedirs(CA_DIR, exist_ok=True)
    if not os.path.exists(CA_KEY):
        print("[*] Generating Root CA...", flush=True)
        subprocess.run(["openssl", "genrsa", "-out", CA_KEY, "2048"], check=True, capture_output=True)
        subprocess.run([
            "openssl", "req", "-x509", "-new", "-nodes", "-key", CA_KEY,
            "-sha256", "-days", "3650", "-out", CA_CERT,
            "-subj", "/CN=ADCSLAB-Root-CA/O=ADCSLAB/C=US"
        ], check=True, capture_output=True)
        print(f"[+] Root CA generated: {CA_CERT}", flush=True)

class ADCSHandler(http.server.BaseHTTPRequestHandler):

    def log_message(self, format, *args):
        pass

    def do_GET(self):
        if self.path in ("/certsrv", "/certsrv/", "/"):
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            html = """<!DOCTYPE html>
<html>
<head>
    <title>Microsoft Active Directory Certificate Services - Web Enrollment</title>
    <style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f4f4f9; margin: 0; padding: 20px; }
        .container { max-width: 800px; background: white; padding: 35px; border-radius: 8px; box-shadow: 0 4px 15px rgba(0,0,0,0.1); margin: auto; }
        h2 { color: #0078d4; border-bottom: 2px solid #0078d4; padding-bottom: 10px; margin-top: 0; }
        label { font-weight: bold; display: block; margin-top: 15px; }
        textarea { width: 100%; height: 180px; font-family: monospace; padding: 10px; border: 1px solid #ccc; border-radius: 4px; box-sizing: border-box; }
        select, input[type="text"] { width: 100%; padding: 10px; border: 1px solid #ccc; border-radius: 4px; box-sizing: border-box; margin-top: 5px; }
        input[type="submit"] { background-color: #0078d4; color: white; padding: 12px 20px; border: none; border-radius: 4px; cursor: pointer; font-size: 16px; margin-top: 20px; font-weight: bold; }
        input[type="submit"]:hover { background-color: #005a9e; }
        .nav-links { margin-top: 25px; padding-top: 15px; border-top: 1px solid #eee; }
        .nav-links a { color: #0078d4; text-decoration: none; font-weight: bold; }
        .nav-links a:hover { text-decoration: underline; }
    </style>
</head>
<body>
    <div class="container">
        <h2>Microsoft AD CS Web Enrollment (ADCSLAB.LOCAL)</h2>
        <p>Use this form to submit a Certificate Signing Request (CSR) to request a new certificate from the CA.</p>
        <form method="POST" action="/certsrv/certfnsh.asp">
            <label for="template">Certificate Template:</label>
            <select name="template" id="template">
                <option value="User">User (Standard User Cert)</option>
                <option value="Machine">Machine (Standard Computer Cert)</option>
                <option value="ESC1">ESC1-Vulnerable (Allows SAN / User Impersonation - Misconfigured)</option>
            </select>

            <label for="upn">Alternative UPN (Only applicable if template allows SAN specification - ESC1):</label>
            <input type="text" name="upn" id="upn" placeholder="e.g., Administrator@ADCSLAB.LOCAL">

            <label for="csr">Base64-encoded Certificate Request (CSR):</label>
            <textarea name="csr" id="csr" placeholder="-----BEGIN CERTIFICATE REQUEST-----&#10;...&#10;-----END CERTIFICATE REQUEST-----" required></textarea>

            <input type="submit" value="Submit Request">
        </form>

        <div class="nav-links">
            <a href="/certsrv/ca.crt" download>Download Root CA Certificate (ca.crt)</a>
        </div>
    </div>
</body>
</html>
"""
            self.wfile.write(html.encode("utf-8"))

        elif self.path == "/certsrv/ca.crt":
            if os.path.exists(CA_CERT):
                self.send_response(200)
                self.send_header("Content-type", "application/x-x509-ca-cert")
                self.end_headers()
                with open(CA_CERT, "rb") as f:
                    self.wfile.write(f.read())
            else:
                self.send_error(404, "File Not Found")
        else:
            self.send_error(404, "File Not Found")

    def do_POST(self):
        if self.path == "/certsrv/certfnsh.asp":
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length).decode('utf-8')
            params = urllib.parse.parse_qs(post_data)

            csr_data = params.get('csr', [''])[0].strip()
            template = params.get('template', ['User'])[0]
            upn = params.get('upn', [''])[0].strip()

            if not csr_data:
                self.send_response(400)
                self.wfile.write(b"Error: CSR is empty.")
                return

            csr_path = "/tmp/request.csr"
            with open(csr_path, "w") as f:
                f.write(csr_data)

            ext_path = "/tmp/ext.conf"
            with open(ext_path, "w") as f:
                f.write("[v3_req]\n")
                f.write("basicConstraints = CA:FALSE\n")
                f.write("keyUsage = digitalSignature, keyEncipherment\n")
                if template == "ESC1" and upn:
                    f.write(f"subjectAltName = otherName:1.3.6.1.4.1.311.20.2.3;UTF8:{upn}\n")
                    print(f"[+] Signing ESC1 request with SAN UPN: {upn}", flush=True)
                else:
                    print(f"[+] Signing request with template: {template}", flush=True)

            cert_path = "/tmp/issued.crt"
            if os.path.exists(cert_path):
                os.remove(cert_path)

            cmd = [
                "openssl", "x509", "-req", "-in", csr_path,
                "-CA", CA_CERT, "-CAkey", CA_KEY, "-CAcreateserial",
                "-out", cert_path, "-days", "365", "-sha256",
                "-extfile", ext_path, "-extensions", "v3_req"
            ]
            res = subprocess.run(cmd, capture_output=True, text=True)

            if res.returncode != 0:
                self.send_response(500)
                self.send_header("Content-type", "text/plain")
                self.end_headers()
                self.wfile.write(f"Error signing certificate:\n{res.stderr}".encode("utf-8"))
                return

            with open(cert_path, "r") as f:
                issued_cert = f.read()

            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            html = f"""<!DOCTYPE html>
<html>
<head>
    <title>Certificate Issued</title>
    <style>
        body {{ font-family: 'Segoe UI', sans-serif; background-color: #f4f4f9; padding: 20px; }}
        .container {{ max-width: 800px; background: white; padding: 35px; border-radius: 8px; box-shadow: 0 4px 15px rgba(0,0,0,0.1); margin: auto; }}
        h2 {{ color: #107c41; border-bottom: 2px solid #107c41; padding-bottom: 10px; }}
        pre {{ background-color: #f0f0f0; padding: 15px; border-radius: 4px; font-family: monospace; overflow-x: auto; }}
        .btn {{ display: inline-block; background-color: #0078d4; color: white; padding: 10px 15px; text-decoration: none; border-radius: 4px; font-weight: bold; margin-top: 15px; }}
        .btn:hover {{ background-color: #005a9e; }}
    </style>
</head>
<body>
    <div class="container">
        <h2>Certificate Issued Successfully</h2>
        <p>Your certificate has been signed by the Certificate Authority.</p>
        <p><strong>Template Used:</strong> {template}</p>
        {"<p><strong>Injected SAN UPN:</strong> " + upn + "</p>" if (template == "ESC1" and upn) else ""}
        <label><strong>PEM Certificate:</strong></label>
        <pre>{issued_cert}</pre>
        <a href="/certsrv" class="btn">Back to Enrollment Page</a>
    </div>
</body>
</html>
"""
            self.wfile.write(html.encode("utf-8"))
        else:
            self.send_error(404, "Not Found")

if __name__ == "__main__":
    init_ca()
    with socketserver.TCPServer(("", PORT), ADCSHandler) as httpd:
        print(f"[+] AD CS Web Enrollment Server running on port {PORT}", flush=True)
        httpd.serve_forever()
