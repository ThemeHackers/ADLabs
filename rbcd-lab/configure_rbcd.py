import samba
from samba.samdb import SamDB
import samba.param
from samba.auth import system_session
from ldb import Message, MessageElement, FLAG_MOD_REPLACE, Dn, SCOPE_SUBTREE
import samba.dcerpc.security as security
from samba.ndr import ndr_pack, ndr_unpack
import subprocess

lp = samba.param.LoadParm()
lp.load('/samba/etc/smb.conf')
samdb = SamDB(url='/samba/private/sam.ldb', lp=lp, session_info=system_session())

print("Setting password policy...")
subprocess.run(["samba-tool", "domain", "passwordsettings", "set", "--complexity=off", "--configfile=/samba/etc/smb.conf"])
subprocess.run(["samba-tool", "domain", "passwordsettings", "set", "--min-pwd-length=4", "--configfile=/samba/etc/smb.conf"])
subprocess.run(["samba-tool", "domain", "passwordsettings", "set", "--history-length=0", "--configfile=/samba/etc/smb.conf"])

print("Creating user r.worker...")
subprocess.run(["samba-tool", "user", "create", "r.worker", "WorkerPass2026!", "--realm=RBCDLAB.LOCAL", "--configfile=/samba/etc/smb.conf"])

print("Creating computer srv-target...")
subprocess.run(["samba-tool", "computer", "create", "srv-target", "--configfile=/samba/etc/smb.conf"])

print("Modifying security descriptor of srv-target to set owner to r.worker...")
res = samdb.search(base=samdb.domain_dn(), scope=SCOPE_SUBTREE, expression="sAMAccountName=r.worker")
user_sid = ndr_unpack(security.dom_sid, res[0]['objectSid'][0])

res_comp = samdb.search(base=samdb.domain_dn(), scope=SCOPE_SUBTREE, expression="sAMAccountName=srv-target$", attrs=["nTSecurityDescriptor"])
comp_dn = res_comp[0].dn

sd_binary = res_comp[0]['nTSecurityDescriptor'][0]
sd = ndr_unpack(security.descriptor, sd_binary)
sd.owner_sid = user_sid

msg = Message()
msg.dn = comp_dn
msg['nTSecurityDescriptor'] = MessageElement(ndr_pack(sd), FLAG_MOD_REPLACE, 'nTSecurityDescriptor')
samdb.modify(msg)
print("Successfully configured RBCD lab: made r.worker owner of srv-target")
