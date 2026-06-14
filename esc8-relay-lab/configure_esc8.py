import subprocess

print("Setting password policy...")
subprocess.run(["samba-tool", "domain", "passwordsettings", "set", "--complexity=off", "--configfile=/samba/etc/smb.conf"])
subprocess.run(["samba-tool", "domain", "passwordsettings", "set", "--min-pwd-length=4", "--configfile=/samba/etc/smb.conf"])
subprocess.run(["samba-tool", "domain", "passwordsettings", "set", "--history-length=0", "--configfile=/samba/etc/smb.conf"])

print("Creating user student...")
subprocess.run(["samba-tool", "user", "create", "student", "StudentPass2026!", "--realm=ESC8LAB.LOCAL", "--configfile=/samba/etc/smb.conf"])
print("Successfully configured ESC8 AD lab.")
