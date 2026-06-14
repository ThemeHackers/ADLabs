import subprocess

print("Setting password policy...")
subprocess.run(["samba-tool", "domain", "passwordsettings", "set", "--complexity=off", "--configfile=/samba/etc/smb.conf"])
subprocess.run(["samba-tool", "domain", "passwordsettings", "set", "--min-pwd-length=4", "--configfile=/samba/etc/smb.conf"])
subprocess.run(["samba-tool", "domain", "passwordsettings", "set", "--history-length=0", "--configfile=/samba/etc/smb.conf"])

print("Creating user db_operator...")
subprocess.run(["samba-tool", "user", "create", "db_operator", "OperatorSecurePass2026!", "--realm=SQLPIVOT.LOCAL", "--configfile=/samba/etc/smb.conf"])
print("Successfully configured SQL Pivot AD lab.")
