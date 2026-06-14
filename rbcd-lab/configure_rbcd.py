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
print("RBCD Lab - Enhanced Multi-Path Configuration")
print("=" * 55)

run_tool(["domain", "passwordsettings", "set", "--complexity=off"])
run_tool(["domain", "passwordsettings", "set", "--min-pwd-length=4"])
run_tool(["domain", "passwordsettings", "set", "--history-length=0"])
run_tool(["domain", "passwordsettings", "set", "--account-lockout-threshold=0"])

run_tool(["user", "create", "r.worker", "WorkerPass2026!", "--realm=RBCDLAB.LOCAL"])
run_tool(["user", "create", "svc_web_rbcd", "WebRBCDPass123!", "--realm=RBCDLAB.LOCAL"])
run_tool(["user", "create", "j.intern", "InternPass2026!", "--realm=RBCDLAB.LOCAL"])
run_tool(["user", "create", "svc_sql_rbcd", "SQLRBCDPass123!", "--realm=RBCDLAB.LOCAL"])
run_tool(["spn", "add", "MSSQLSvc/rbcd-db.rbcdlab.local:1433", "svc_sql_rbcd"])

samdb.toggle_userAccountFlags("sAMAccountName=j.intern", dsdb.UF_DONT_REQUIRE_PREAUTH,
                               "dont-require-preauth", on=True, strict=False)
samdb.toggle_userAccountFlags("sAMAccountName=j.intern", dsdb.UF_DONT_EXPIRE_PASSWD,
                               "dont-expire-passwd", on=True, strict=False)
print("[+] j.intern is AS-REP Roastable")

run_tool(["computer", "create", "srv-target"])
run_tool(["computer", "create", "ws-corp"])

r_worker_sid, _ = get_sid_and_dn("sAMAccountName=r.worker")
res_comp = samdb.search(base=domain_dn, scope=SCOPE_SUBTREE,
                        expression="sAMAccountName=srv-target$",
                        attrs=["nTSecurityDescriptor"])
if res_comp and r_worker_sid:
    comp_dn = res_comp[0].dn
    sd = ndr_unpack(security.descriptor, bytes(res_comp[0]["nTSecurityDescriptor"][0]))
    sd.owner_sid = r_worker_sid
    msg = Message()
    msg.dn = comp_dn
    msg["nTSecurityDescriptor"] = MessageElement(ndr_pack(sd), FLAG_MOD_REPLACE, "nTSecurityDescriptor")
    samdb.modify(msg)
    print("[+] r.worker set as Owner of srv-target$")

_, srv_target_dn = get_sid_and_dn("sAMAccountName=srv-target$")
if r_worker_sid and srv_target_dn:
    grant_ace(srv_target_dn, r_worker_sid, security.SEC_GENERIC_WRITE)
    print("[+] r.worker has GenericWrite on srv-target$ -> direct RBCD attack")

svc_web_sid, _ = get_sid_and_dn("sAMAccountName=svc_web_rbcd")
_, ws_corp_dn = get_sid_and_dn("sAMAccountName=ws-corp$")
if svc_web_sid and ws_corp_dn:
    grant_ace(ws_corp_dn, svc_web_sid, security.SEC_GENERIC_WRITE)
    print("[+] svc_web_rbcd has GenericWrite on ws-corp$ -> Shadow Credentials path")

jintern_sid, _ = get_sid_and_dn("sAMAccountName=j.intern")
_, svcweb_dn = get_sid_and_dn("sAMAccountName=svc_web_rbcd")
if jintern_sid and svcweb_dn:
    grant_ace(svcweb_dn, jintern_sid, security.SEC_GENERIC_ALL)
    print("[+] j.intern has GenericAll over svc_web_rbcd -> Password Reset -> pivot to Shadow Creds")

print("[+] RBCD Lab configuration complete!")
