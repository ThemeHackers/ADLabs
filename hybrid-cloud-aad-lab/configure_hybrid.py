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

def grant_extended_right(target_dn, trustee_sid, right_guid_str):
    try:
        import uuid
        u = uuid.UUID(right_guid_str)
        guid_bytes = u.bytes_le

        res = samdb.search(base=target_dn, scope=SCOPE_SUBTREE,
                           expression="(objectClass=*)",
                           attrs=["nTSecurityDescriptor"])
        if not res:
            return
        sd = ndr_unpack(security.descriptor, bytes(res[0]["nTSecurityDescriptor"][0]))
        ace = security.ace()
        ace.type = security.SEC_ACE_TYPE_ACCESS_ALLOWED_OBJECT
        ace.flags = 0
        ace.access_mask = security.SEC_ADS_CONTROL_ACCESS
        ace.object_type = security.GUID(right_guid_str)
        ace.inherited_object_type = None
        ace.object_flags = security.SEC_ACE_OBJECT_TYPE_PRESENT
        ace.trustee = trustee_sid

        aces = list(sd.dacl.aces) if sd.dacl and sd.dacl.aces else []
        aces.append(ace)
        sd.dacl.aces = aces
        sd.dacl.num_aces = len(aces)

        msg = Message()
        msg.dn = target_dn
        msg["nTSecurityDescriptor"] = MessageElement(ndr_pack(sd), FLAG_MOD_REPLACE, "nTSecurityDescriptor")
        samdb.modify(msg)
        print(f"[+] Extended Right {right_guid_str} granted to trustee on {target_dn}")
    except Exception as e:
        print(f"[!] grant_extended_right failed: {e}")

print("=" * 60)
print("Configuring Enterprise Hybrid Cloud AD & Azure AD Connect")
print("=" * 60)

run_tool(["domain", "passwordsettings", "set", "--complexity=off"])
run_tool(["domain", "passwordsettings", "set", "--min-pwd-length=4"])
run_tool(["domain", "passwordsettings", "set", "--account-lockout-threshold=0"])

# 1. Create Enterprise Organizational Units (OUs)
ous = [
    "OU=Enterprise," + domain_dn,
    "OU=Finance,OU=Enterprise," + domain_dn,
    "OU=Engineering,OU=Enterprise," + domain_dn,
    "OU=IT-Ops,OU=Enterprise," + domain_dn,
    "OU=HelpDesk,OU=Enterprise," + domain_dn,
    "OU=Executive,OU=Enterprise," + domain_dn,
    "OU=ServiceAccounts,OU=Enterprise," + domain_dn
]

for ou in ous:
    try:
        msg = Message()
        msg.dn = Dn(samdb, ou)
        msg["objectClass"] = MessageElement(["top", "organizationalUnit"], FLAG_MOD_ADD, "objectClass")
        samdb.add(msg)
        print(f"[+] Created OU: {ou}")
    except Exception:
        pass

# 2. Bulk Seed Enterprise Users
users_seed = [
    ("l11_t.intern", "InternPass2026!", "HelpDesk Tier 1 Intern", "OU=HelpDesk,OU=Enterprise," + domain_dn),
    ("devops_admin", "DevOpsPass2026!", "DevOps Lead Engineer", "OU=IT-Ops,OU=Enterprise," + domain_dn),
    ("c.jenkins", "JenkinsBuild2026!", "CI/CD Pipeline Lead", "OU=Engineering,OU=Enterprise," + domain_dn),
    ("m.finance", "FinanceAuditPass2026!", "Senior Accountant", "OU=Finance,OU=Enterprise," + domain_dn),
    ("e.exec", "ExecutiveSecret2026!", "Chief Operating Officer", "OU=Executive,OU=Enterprise," + domain_dn),
    ("j.helpdesk", "HelpDeskWorker2026!", "IT Support Specialist", "OU=HelpDesk,OU=Enterprise," + domain_dn),
    ("a.developer", "DevPasswordSecure2026!", "Backend Engineer", "OU=Engineering,OU=Enterprise," + domain_dn),
    ("r.sysadmin", "SysAdminCorePass2026!", "IT Operations Admin", "OU=IT-Ops,OU=Enterprise," + domain_dn)
]

for username, pwd, desc, user_ou in users_seed:
    run_tool(["user", "create", username, pwd, "--userou=" + user_ou.replace("," + domain_dn, ""), "--description=" + desc])

# 3. Create Security Groups
run_tool(["group", "create", "HelpDesk-Tier1", "--groupou=OU=HelpDesk,OU=Enterprise"])
run_tool(["group", "create", "DevOps-Admins", "--groupou=OU=IT-Ops,OU=Enterprise"])
run_tool(["group", "create", "Cloud-Sync-Operators", "--groupou=OU=ServiceAccounts,OU=Enterprise"])

run_tool(["group", "addmembers", "HelpDesk-Tier1", "l11_t.intern"])
run_tool(["group", "addmembers", "DevOps-Admins", "devops_admin"])

# 4. BloodHound ACL Attack Path: HelpDesk-Tier1 has GenericAll on DevOps-Admins
hd_sid, _ = get_sid_and_dn("sAMAccountName=HelpDesk-Tier1")
_, devops_group_dn = get_sid_and_dn("sAMAccountName=DevOps-Admins")
if hd_sid and devops_group_dn:
    grant_ace(devops_group_dn, hd_sid, security.SEC_GENERIC_ALL)
    print("[+] HelpDesk-Tier1 granted GenericAll on DevOps-Admins (BloodHound Path)")

# 5. Create Azure AD Connect Sync Account (MSOL_a1b2c3d4e5f6)
msol_account = "MSOL_a1b2c3d4e5f6"
msol_password = "AADSync_SuperSecret_P@ss2026!#"
run_tool(["user", "create", msol_account, msol_password, 
          "--userou=OU=ServiceAccounts,OU=Enterprise", 
          "--description=Account created by Azure AD Connect with rights to replicate directory changes."])

# Grant DCSync permissions to MSOL account on Domain Root
msol_sid, _ = get_sid_and_dn(f"sAMAccountName={msol_account}")
if msol_sid:
    # DS-Replication-Get-Changes (1131f6aa-9c07-11d1-f79f-00c04fc2dcd2)
    grant_extended_right(Dn(samdb, domain_dn), msol_sid, "1131f6aa-9c07-11d1-f79f-00c04fc2dcd2")
    # DS-Replication-Get-Changes-All (1131f6ad-9c07-11d1-f79f-00c04fc2dcd2)
    grant_extended_right(Dn(samdb, domain_dn), msol_sid, "1131f6ad-9c07-11d1-f79f-00c04fc2dcd2")
    print(f"[+] {msol_account} granted DCSync rights (Replicating Directory Changes & Changes All)!")

# 6. Write final flag on DC
try:
    with open("/var/flag.txt", "w") as f:
        f.write("OSCP{aad_connect_hybrid_sync_account_compromised_2026}\n")
    print("[+] Flag planted at /var/flag.txt")
except Exception as e:
    print(f"[!] Failed to write flag: {e}")

print("=" * 60)
print("Hybrid Cloud AD Configuration Complete!")
print("=" * 60)
