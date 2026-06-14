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

def get_sid(filter_expr):
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


print("=" * 50)
print("LAPS Lab - Enhanced Configuration")
print("=" * 50)

run_tool(["domain", "passwordsettings", "set", "--complexity=off"])
run_tool(["domain", "passwordsettings", "set", "--min-pwd-length=4"])
run_tool(["domain", "passwordsettings", "set", "--history-length=0"])
run_tool(["domain", "passwordsettings", "set", "--account-lockout-threshold=0"])

run_tool(["user", "create", "l8_audit_user", "AuditPass2026!", "--realm=LAPSLAB.LOCAL"])
run_tool(["user", "create", "l8_it_helpdesk", "HelpdeskPass2026!", "--realm=LAPSLAB.LOCAL"])
run_tool(["user", "create", "l8_svc_monitor", "MonitorSvcPass123!", "--realm=LAPSLAB.LOCAL"])
run_tool(["spn", "add", "HTTP/monitor.lapslab.local:8080", "l8_svc_monitor"])

run_tool(["computer", "create", "srv-finance"])
run_tool(["computer", "create", "ws-admin"])
run_tool(["computer", "create", "srv-backup"])

for computer, pwd in [
    ("srv-finance$", "FinanceSrvLocalAdminPass2026!"),
    ("ws-admin$", "AdminWsLocalP@ss2026!"),
]:
    res = samdb.search(base=domain_dn, scope=SCOPE_SUBTREE,
                       expression=f"sAMAccountName={computer}")
    if res:
        msg = Message()
        msg.dn = res[0].dn
        msg["description"] = MessageElement(
            f"LAPS: {pwd}".encode("utf-8"), FLAG_MOD_REPLACE, "description"
        )
        samdb.modify(msg)
        print(f"[+] LAPS password set in description for {computer}")

res_fin = samdb.search(base=domain_dn, scope=SCOPE_SUBTREE, expression="sAMAccountName=srv-finance$")
if res_fin:
    msg = Message()
    msg.dn = res_fin[0].dn
    msg["info"] = MessageElement(
        "LocalAdminPassword=FinanceSrvLocalAdminPass2026!;Expiry=2026-12-31".encode("utf-8"),
        FLAG_MOD_REPLACE, "info"
    )
    samdb.modify(msg)
    print("[+] LAPS password injected in 'info' attribute on srv-finance$")

audit_sid, _ = get_sid("sAMAccountName=l8_audit_user")
_, fin_dn = get_sid("sAMAccountName=srv-finance$")
if audit_sid and fin_dn:
    grant_ace(fin_dn, audit_sid, security.SEC_ADS_READ_PROP | security.SEC_ADS_LIST)
    print("[+] l8_audit_user has ReadProperty on srv-finance$")

hd_sid, _ = get_sid("sAMAccountName=l8_it_helpdesk")
_, bk_dn = get_sid("sAMAccountName=srv-backup$")
if hd_sid and bk_dn:
    grant_ace(bk_dn, hd_sid, security.SEC_GENERIC_ALL)
    print("[+] l8_it_helpdesk has GenericAll on srv-backup$ -> RBCD path")

samdb.toggle_userAccountFlags("sAMAccountName=l8_audit_user", dsdb.UF_DONT_REQUIRE_PREAUTH,
                               "dont-require-preauth", on=True, strict=False)
samdb.toggle_userAccountFlags("sAMAccountName=l8_audit_user", dsdb.UF_DONT_EXPIRE_PASSWD,
                               "dont-expire-passwd", on=True, strict=False)
print("[+] l8_audit_user is AS-REP Roastable")

print("[+] LAPS Lab configuration complete!")
