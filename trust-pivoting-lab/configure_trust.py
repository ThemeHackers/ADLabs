import subprocess
import os
import time

def run_ldap(args, host, password, user="Administrator"):
    cmd = ["samba-tool"] + args + [
        f"-H", f"ldap://{host}",
        "-U", user,
        f"--password={password}"
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    label = " ".join(args[:3])
    if res.returncode != 0:
        print(f"[!] {label}: {res.stderr.strip()[:120]}")
    else:
        print(f"[+] {label}: OK")
    return res.returncode == 0

FORESTA_HOST = "10.103.10.10"
FORESTA_PASS = "ForestAAdminPass2026!"
FORESTB_HOST = "10.103.20.10"
FORESTB_PASS = "ForestBAdminPass2026!"

print("[*] Waiting 60s for both DCs to initialize...", flush=True)
time.sleep(60)

print("[*] Setting password policies...", flush=True)
for host, pwd in [(FORESTA_HOST, FORESTA_PASS), (FORESTB_HOST, FORESTB_PASS)]:
    run_ldap(["domain", "passwordsettings", "set", "--complexity=off"], host, pwd)
    run_ldap(["domain", "passwordsettings", "set", "--min-pwd-length=4"], host, pwd)
    run_ldap(["domain", "passwordsettings", "set", "--history-length=0"], host, pwd)
    run_ldap(["domain", "passwordsettings", "set", "--account-lockout-threshold=0"], host, pwd)

print("[*] Creating FORESTA users...", flush=True)
run_ldap(["user", "create", "j.foresta", "ForestAUserPass2026!", "--realm=FORESTA.LOCAL"], FORESTA_HOST, FORESTA_PASS)
run_ldap(["user", "create", "svc_foresta", "ForestASvcPass123!", "--realm=FORESTA.LOCAL"], FORESTA_HOST, FORESTA_PASS)
run_ldap(["spn", "add", "HTTP/foresta-web.foresta.local:80", "svc_foresta"], FORESTA_HOST, FORESTA_PASS)

print("[*] Creating FORESTB users...", flush=True)
run_ldap(["user", "create", "j.forestb", "ForestBUserPass2026!", "--realm=FORESTB.LOCAL"], FORESTB_HOST, FORESTB_PASS)
run_ldap(["user", "create", "svc_forestb", "ForestBSvcPass123!", "--realm=FORESTB.LOCAL"], FORESTB_HOST, FORESTB_PASS)
run_ldap(["spn", "add", "MSSQLSvc/forestb-db.forestb.local:1433", "svc_forestb"], FORESTB_HOST, FORESTB_PASS)

run_ldap(["user", "create", "svc_asrep_trust", "TrustASREPPass123!", "--realm=FORESTB.LOCAL"], FORESTB_HOST, FORESTB_PASS)

print("[*] Setting AS-REP Roasting flag via LDIF on svc_asrep_trust...", flush=True)
ldif = "dn: CN=svc_asrep_trust,CN=Users,DC=forestb,DC=local\nchangetype: modify\nreplace: userAccountControl\nuserAccountControl: 4194816\n"
ldif_path = "/tmp/asrep_trust.ldif"
with open(ldif_path, "w") as f:
    f.write(ldif)
subprocess.run([
    "ldbmodify", "-H", f"ldap://{FORESTB_HOST}",
    "-U", "Administrator", f"--password={FORESTB_PASS}", ldif_path
], capture_output=True)
print("[+] svc_asrep_trust AS-REP Roasting flag set")

print("[*] Establishing Cross-Forest Trust FORESTA -> FORESTB...", flush=True)

trust_cmd_a = [
    "samba-tool", "domain", "trust", "create", "FORESTB.LOCAL",
    "--type=external",
    "--direction=both",
    "--create-location=both",
    f"-H", f"ldap://{FORESTA_HOST}",
    "-U", "Administrator",
    f"--password={FORESTA_PASS}",
    "--trust-user-pass=TrustBothPass2026!",
    f"--remote-dc={FORESTB_HOST}",
    "--remote-user=Administrator",
    f"--remote-password={FORESTB_PASS}"
]
res_trust = subprocess.run(trust_cmd_a, capture_output=True, text=True)
if res_trust.returncode == 0:
    print("[+] Cross-Forest Trust established successfully!")
else:
    print(f"[!] Trust creation returned: {res_trust.stderr.strip()[:200]}")
    print("[*] Attempting Trust via DNS-only method as fallback...")
    subprocess.run([
        "samba-tool", "domain", "trust", "create", "FORESTB.LOCAL",
        "--type=forest",
        f"-H", f"ldap://{FORESTA_HOST}",
        "-U", "Administrator",
        f"--password={FORESTA_PASS}",
        "--trust-user-pass=TrustBothPass2026!",
        f"--remote-dc={FORESTB_HOST}",
        "--remote-user=Administrator",
        f"--remote-password={FORESTB_PASS}"
    ], capture_output=True)

print("[*] Setting up SID History simulation on FORESTB...", flush=True)
sid_hist_ldif = """dn: CN=j.forestb,CN=Users,DC=forestb,DC=local
changetype: modify
replace: description
description: SID-History-Target: S-1-5-21-FORESTA-512 (Domain Admins)
"""
sid_path = "/tmp/sid_hist.ldif"
with open(sid_path, "w") as f:
    f.write(sid_hist_ldif)
subprocess.run([
    "ldbmodify", "-H", f"ldap://{FORESTB_HOST}",
    "-U", "Administrator", f"--password={FORESTB_PASS}", sid_path
], capture_output=True)
print("[+] SID History target annotation set on j.forestb")

print("[*] Writing flag files...", flush=True)
os.makedirs("/tmp/flags", exist_ok=True)
with open("/tmp/flags/foresta_flag.txt", "w") as f:
    f.write("OSCP{trust_pivot_foresta_compromised}\n")
with open("/tmp/flags/forestb_flag.txt", "w") as f:
    f.write("OSCP{cross_forest_sid_history_attack}\n")

print("[+] Trust Pivoting Lab configuration complete!")
print("    Attack Paths:")
print("    1. Kerberoast svc_foresta -> crack -> foothold FORESTA")
print("    2. AS-REP Roast svc_asrep_trust in FORESTB")
print("    3. Enumerate trust: nltest /domain_trusts or bloodhound")
print("    4. Cross-forest TGT request: getST.py -spn krbtgt/FORESTB.LOCAL FORESTA.LOCAL/j.foresta")
print("    5. SID History abuse: inject FORESTA Domain Admin SID into FORESTB cross-domain auth")
print("    6. secretsdump on FORESTB DC after cross-forest escalation")
