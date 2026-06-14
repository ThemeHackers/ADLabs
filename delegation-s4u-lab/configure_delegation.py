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

print("Creating user web_service...")
subprocess.run(["samba-tool", "user", "create", "web_service", "WebServPass123!", "--realm=DELEGATELAB.LOCAL", "--configfile=/samba/etc/smb.conf"])

print("Creating computer deleg-db...")
subprocess.run(["samba-tool", "computer", "create", "deleg-db", "--configfile=/samba/etc/smb.conf"])

print("Adding SPN to web_service...")
subprocess.run(["samba-tool", "spn", "add", "HTTP/web-server.delegatelab.local", "web_service", "--configfile=/samba/etc/smb.conf"])

print("Configuring Constrained Delegation (AllowedToDelegateTo)...")
res = samdb.search(base=samdb.domain_dn(), scope=SCOPE_SUBTREE, expression="sAMAccountName=web_service")
user_dn = res[0].dn

msg = Message()
msg.dn = user_dn
msg['msDS-AllowedToDelegateTo'] = MessageElement("cifs/deleg-db.delegatelab.local".encode('utf-8'), FLAG_MOD_REPLACE, 'msDS-AllowedToDelegateTo')
samdb.modify(msg)
print("Successfully configured Constrained Delegation on web_service.")
