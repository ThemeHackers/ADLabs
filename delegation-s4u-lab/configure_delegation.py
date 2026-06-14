import samba
from samba.samdb import SamDB
import samba.param
import samba.dsdb as dsdb
from samba.auth import system_session
from ldb import Message, MessageElement, FLAG_MOD_REPLACE, Dn, SCOPE_SUBTREE
import samba.dcerpc.security as security
from samba.ndr import ndr_pack, ndr_unpack
import subprocess

lp = samba.param.LoadParm()
lp.load('/samba/etc/smb.conf')
samdb = SamDB(url='/samba/private/sam.ldb', lp=lp, session_info=system_session())
domain_dn = samdb.domain_dn()


def run_tool(args):
    cmd = ["samba-tool"] + args + ["--configfile=/samba/etc/smb.conf"]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print(f"[!] {' '.join(args[:3])}: {res.stderr.strip()[:120]}")
    else:
        print(f"[+] {' '.join(args[:3])}: OK")
    return res.returncode == 0

def get_sid_and_dn(filter_expr):
    res = samdb.search(base=domain_dn, scope=SCOPE_SUBTREE, expression=filter_expr)
    if not res:
        return None, None
    sid = ndr_unpack(security.dom_sid, bytes(res[0]["objectSid"][0]))
    return sid, res[0].dn

def grant_ace(target_dn, trustee_sid, access_mask):
    try:
        res = samdb.search(base=target_dn, scope=SCOPE_SUBTREE,
                           expression="(objectClass=*)",
                           attrs=["nTSecurityDescriptor"])
        if not res:
            return
        sd = ndr_unpack(security.descriptor, bytes(res[0]["nTSecurityDescriptor"][0]))
        ace = security.ace()
        ace.type = security.SEC_ACE_TYPE_ACCESS_ALLOWED
        ace.flags = 0
        ace.access_mask = access_mask
        ace.trustee = trustee_sid
        aces = list(sd.dacl.aces) if sd.dacl and sd.dacl.aces else []
        aces.append(ace)
        sd.dacl.aces = aces
        sd.dacl.num_aces = len(aces)
        msg = Message()
        msg.dn = target_dn
        msg["nTSecurityDescriptor"] = MessageElement(ndr_pack(sd), FLAG_MOD_REPLACE, "nTSecurityDescriptor")
        samdb.modify(msg)
        print(f"[+] ACE 0x{access_mask:08X} granted on {target_dn}")
    except Exception as e:
        print(f"[!] grant_ace failed: {e}")


print("=" * 55)
print("Delegation Lab - S4U / Protocol Transition Configuration")
print("=" * 55)

run_tool(["domain", "passwordsettings", "set", "--complexity=off"])
run_tool(["domain", "passwordsettings", "set", "--min-pwd-length=4"])
run_tool(["domain", "passwordsettings", "set", "--history-length=0"])
run_tool(["domain", "passwordsettings", "set", "--account-lockout-threshold=0"])

run_tool(["user", "create", "web_service", "WebServPass123!", "--realm=DELEGATELAB.LOCAL"])
run_tool(["user", "create", "db_service", "DBServPass123!", "--realm=DELEGATELAB.LOCAL"])
run_tool(["user", "create", "j.student", "StudentPass2026!", "--realm=DELEGATELAB.LOCAL"])
run_tool(["user", "create", "svc_backup_deleg", "BackupDelegPass123!", "--realm=DELEGATELAB.LOCAL"])

run_tool(["computer", "create", "deleg-db"])
run_tool(["computer", "create", "deleg-web"])

run_tool(["spn", "add", "HTTP/web-server.delegatelab.local", "web_service"])
run_tool(["spn", "add", "HTTP/web-server.delegatelab.local:80", "web_service"])
run_tool(["spn", "add", "MSSQLSvc/deleg-db.delegatelab.local:1433", "db_service"])

res = samdb.search(base=domain_dn, scope=SCOPE_SUBTREE, expression="sAMAccountName=web_service")
if res:
    user_dn = res[0].dn
    msg = Message()
    msg.dn = user_dn
    msg["msDS-AllowedToDelegateTo"] = MessageElement(
        "cifs/deleg-db.delegatelab.local".encode("utf-8"),
        FLAG_MOD_REPLACE, "msDS-AllowedToDelegateTo"
    )
    samdb.modify(msg)
    print("[+] web_service -> msDS-AllowedToDelegateTo: cifs/deleg-db.delegatelab.local")

try:
    samdb.toggle_userAccountFlags(
        "sAMAccountName=web_service",
        dsdb.UF_TRUSTED_TO_AUTHENTICATE_FOR_DELEGATION,
        "trusted-to-authenticate-for-delegation",
        on=True, strict=False
    )
    print("[+] web_service has Protocol Transition (S4U2Self) enabled")
except Exception as e:
    print(f"[!] Protocol Transition flag error (trying UAC direct): {e}")
    try:
        res = samdb.search(base=domain_dn, scope=SCOPE_SUBTREE, expression="sAMAccountName=web_service")
        if res:
            current_uac = int(res[0].get("userAccountControl", [b"512"])[0])
            new_uac = current_uac | 0x01000000
            msg = Message()
            msg.dn = res[0].dn
            msg["userAccountControl"] = MessageElement(str(new_uac).encode(), FLAG_MOD_REPLACE, "userAccountControl")
            samdb.modify(msg)
            print(f"[+] UAC updated to 0x{new_uac:08X} (Protocol Transition enabled)")
    except Exception as e2:
        print(f"[!] UAC fallback also failed: {e2}")

samdb.toggle_userAccountFlags("sAMAccountName=svc_backup_deleg", dsdb.UF_DONT_REQUIRE_PREAUTH,
                               "dont-require-preauth", on=True, strict=False)
samdb.toggle_userAccountFlags("sAMAccountName=svc_backup_deleg", dsdb.UF_DONT_EXPIRE_PASSWD,
                               "dont-expire-passwd", on=True, strict=False)
print("[+] svc_backup_deleg is AS-REP Roastable")

jstudent_sid, _ = get_sid_and_dn("sAMAccountName=j.student")
_, dbsvc_dn = get_sid_and_dn("sAMAccountName=db_service")
if jstudent_sid and dbsvc_dn:
    grant_ace(dbsvc_dn, jstudent_sid, security.SEC_GENERIC_WRITE)
    print("[+] j.student has GenericWrite on db_service -> msDS-KeyCredentialLink (Shadow Credentials)")

print("[+] Delegation Lab configuration complete!")
