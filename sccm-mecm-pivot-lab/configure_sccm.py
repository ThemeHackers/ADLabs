import samba
import samba.param
from samba.samdb import SamDB
from samba.auth import system_session
from ldb import Message, MessageElement, FLAG_MOD_REPLACE, FLAG_MOD_ADD, Dn, SCOPE_SUBTREE
import samba.dcerpc.security as security
from samba.ndr import ndr_pack, ndr_unpack
import subprocess
import os

lp = samba.param.LoadParm()
lp.load('/samba/etc/smb.conf')
samdb = SamDB(url='/samba/private/sam.ldb', lp=lp, session_info=system_session())
domain_dn = samdb.domain_dn()

def run_tool(args):
    cmd = ["samba-tool"] + args + ["--configfile=/samba/etc/smb.conf"]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print(f"[!] {' '.join(args[:3])}: {res.stderr.strip()[:100]}")
    else:
        print(f"[+] {' '.join(args[:3])}: OK")
    return res.returncode == 0

print("=" * 60)
print("Configuring Enterprise SCCM Infrastructure & Active Directory")
print("=" * 60)

run_tool(["domain", "passwordsettings", "set", "--complexity=off"])
run_tool(["domain", "passwordsettings", "set", "--min-pwd-length=4"])
run_tool(["domain", "passwordsettings", "set", "--account-lockout-threshold=0"])


try:
    msg = Message()
    msg.dn = Dn(samdb, "CN=System Management,CN=System," + domain_dn)
    msg["objectClass"] = MessageElement(["top", "container"], FLAG_MOD_ADD, "objectClass")
    msg["description"] = MessageElement(["SCCM Primary Site Server Registration: SiteCode=PS1, MP=sccm-site.corp-management.local"], FLAG_MOD_ADD, "description")
    samdb.add(msg)
    print("[+] Created CN=System Management Container in AD")
except Exception as e:
    print(f"[!] System Management container notice: {e}")


run_tool(["group", "create", "SCCM-Admins"])
run_tool(["group", "create", "Workstation-Admins"])
run_tool(["group", "create", "HelpDesk-Support"])


users_seed = [
    ("l12_j.intern", "InternPass2026!", "HelpDesk IT Intern"),
    ("sccm_naa", "NaaSecretPassword2026!", "SCCM Network Access Account for Distribution Share Downloads"),
    ("sccm_client_push", "ClientPushAdminPass2026!", "SCCM Client Push Installation Privileged Service Account"),
    ("m.manager", "ManagerPass2026!", "IT Systems Operations Manager"),
    ("k.analyst", "AnalystPass2026!", "Endpoint Security Analyst")
]

for username, pwd, desc in users_seed:
    run_tool(["user", "create", username, pwd, "--description=" + desc])


run_tool(["group", "addmembers", "HelpDesk-Support", "l12_j.intern"])
run_tool(["group", "addmembers", "Workstation-Admins", "sccm_naa"])
run_tool(["group", "addmembers", "SCCM-Admins", "sccm_client_push"])
run_tool(["group", "addmembers", "Domain Admins", "sccm_client_push"])


try:
    flag_content = "OSCP{sccm_naa_client_push_network_pivot_mastered_2026}\n"
    for p in ["/var/flag.txt", "/samba/state/sysvol/flag.txt", "/samba/state/sysvol/corp-management.local/flag.txt"]:
        try:
            with open(p, "w") as f:
                f.write(flag_content)
        except Exception:
            pass
    print("[+] Flag planted at /var/flag.txt and sysvol")
except Exception as e:
    print(f"[!] Failed to write flag: {e}")

print("=" * 60)
print("SCCM AD Configuration Complete!")
print("=" * 60)
