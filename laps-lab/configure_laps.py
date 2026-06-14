import samba
from samba.samdb import SamDB
import samba.param
from samba.auth import system_session
from ldb import Message, MessageElement, FLAG_MOD_REPLACE, Dn, SCOPE_SUBTREE
import subprocess

lp = samba.param.LoadParm()
lp.load('/samba/etc/smb.conf')
samdb = SamDB(url='/samba/private/sam.ldb', lp=lp, session_info=system_session())

print("Setting password policy...")
subprocess.run(["samba-tool", "domain", "passwordsettings", "set", "--complexity=off", "--configfile=/samba/etc/smb.conf"])
subprocess.run(["samba-tool", "domain", "passwordsettings", "set", "--min-pwd-length=4", "--configfile=/samba/etc/smb.conf"])
subprocess.run(["samba-tool", "domain", "passwordsettings", "set", "--history-length=0", "--configfile=/samba/etc/smb.conf"])

print("Creating user audit_user...")
subprocess.run(["samba-tool", "user", "create", "audit_user", "AuditPass2026!", "--realm=LAPSLAB.LOCAL", "--configfile=/samba/etc/smb.conf"])

print("Creating computer srv-finance...")
subprocess.run(["samba-tool", "computer", "create", "srv-finance", "--configfile=/samba/etc/smb.conf"])

print("Injecting LAPS password into srv-finance computer description...")
res_comp = samdb.search(base=samdb.domain_dn(), scope=SCOPE_SUBTREE, expression="sAMAccountName=srv-finance$")
comp_dn = res_comp[0].dn

msg = Message()
msg.dn = comp_dn
msg['description'] = MessageElement("LAPS Password: FinanceSrvLocalAdminPass2026!".encode('utf-8'), FLAG_MOD_REPLACE, 'description')
samdb.modify(msg)
print("Successfully configured LAPS lab: injected LAPS password leak.")
