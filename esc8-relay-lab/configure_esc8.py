import subprocess

def run_tool(args):
    cmd = ["samba-tool"] + args + ["--configfile=/samba/etc/smb.conf"]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print(f"[!] {' '.join(args[:3])}: {res.stderr.strip()[:120]}")
    else:
        print(f"[+] {' '.join(args[:3])}: OK")
    return res.returncode == 0

print("=" * 55)
print("ESC8 NTLM Relay Lab - Configuration")
print("=" * 55)

run_tool(["domain", "passwordsettings", "set", "--complexity=off"])
run_tool(["domain", "passwordsettings", "set", "--min-pwd-length=4"])
run_tool(["domain", "passwordsettings", "set", "--history-length=0"])
run_tool(["domain", "passwordsettings", "set", "--account-lockout-threshold=0"])

run_tool(["user", "create", "l9_student", "StudentPass2026!", "--realm=ESC8LAB.LOCAL"])
run_tool(["user", "create", "l9_svc_http", "HTTPServPass123!", "--realm=ESC8LAB.LOCAL"])
run_tool(["spn", "add", "HTTP/esc8-web.esc8lab.local:80", "l9_svc_http"])
run_tool(["spn", "add", "HTTP/esc8-web.esc8lab.local", "l9_svc_http"])
run_tool(["user", "create", "l9_svc_enroll", "EnrollSvcPass123!", "--realm=ESC8LAB.LOCAL"])
run_tool(["spn", "add", "HOST/esc8-enroll.esc8lab.local", "l9_svc_enroll"])

print("[+] ESC8 Lab configuration complete!")
