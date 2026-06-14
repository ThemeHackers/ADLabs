import http.server
import base64
import struct

class NTLMRequestHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        auth_header = self.headers.get('Authorization')
        if not auth_header:
            self.send_response(401)
            self.send_header('WWW-Authenticate', 'NTLM')
            self.send_header('Content-Type', 'text/html')
            self.end_headers()
            self.wfile.write(b"Unauthorized - NTLM Required")
            return
        
        if auth_header.startswith('NTLM '):
            try:
                ntlm_data = base64.b64decode(auth_header[5:])
                if ntlm_data.startswith(b'NTLMSSP\x00'):
                    msg_type = struct.unpack('<I', ntlm_data[8:12])[0]
                    if msg_type == 1:
                        # Challenge message (Type 2)
                        challenge = b'NTLMSSP\x00\x02\x00\x00\x00' \
                                    b'\x00\x00\x00\x00' \
                                    b'\x00\x00\x00\x00' \
                                    b'\x01\x02\x03\x04\x05\x06\x07\x08' \
                                    b'\x00\x00\x00\x00\x00\x00\x00\x00'
                        self.send_response(401)
                        self.send_header('WWW-Authenticate', f'NTLM {base64.b64encode(challenge).decode()}')
                        self.end_headers()
                        return
                    elif msg_type == 3:
                        # Authenticate message (Type 3)
                        user_len = struct.unpack('<H', ntlm_data[36:38])[0]
                        user_off = struct.unpack('<I', ntlm_data[40:44])[0]
                        username = ntlm_data[user_off:user_off+user_len].decode('utf-16-le', errors='ignore')
                        
                        self.send_response(200)
                        self.send_header('Content-Type', 'text/html')
                        self.end_headers()
                        html = f"""
                        <html>
                        <head><title>AD CS Enrollment Services</title></head>
                        <body>
                        <h2>AD CS Web Enrollment Portal</h2>
                        <p style="color: green;">[+] NTLM Authentication Relayed Successfully!</p>
                        <p>Relayed Username: <b>{username}</b></p>
                        <hr>
                        <h3>Certificate Issued:</h3>
                        <pre>
-----BEGIN CERTIFICATE-----
MIIEczCCA1ugAwIBAgIQHTY5d2F5c1...
[MOCK CERTIFICATE FOR {username.upper()}]
-----END CERTIFICATE-----
                        </pre>
                        <p>Use this certificate to authenticate via PKINIT to DC 10.108.10.10.</p>
                        </body>
                        </html>
                        """
                        self.wfile.write(html.encode())
                        return
            except Exception as e:
                self.send_response(500)
                self.end_headers()
                self.wfile.write(f"Error decoding NTLM: {e}".encode())
                return
        
        self.send_response(400)
        self.end_headers()

if __name__ == '__main__':
    http.server.HTTPServer(('0.0.0.0', 80), NTLMRequestHandler).serve_forever()
