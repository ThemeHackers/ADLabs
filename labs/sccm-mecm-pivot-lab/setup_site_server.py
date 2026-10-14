import os
import subprocess

os.makedirs("/opt/sccm/shares/SMSPKGD", exist_ok=True)
os.makedirs("/opt/sccm/config", exist_ok=True)
os.makedirs("/opt/sccm/web", exist_ok=True)


tsconfig_content = """<?xml version="1.0" encoding="utf-8"?>
<SmsMediaConfig>
  <SiteCode>PS1</SiteCode>
  <ManagementPoint>http://10.112.20.20/CCM_System_WindowsAuth</ManagementPoint>
  <CertificateHash>a1b2c3d4e5f67890abcdef1234567890abcdef12</CertificateHash>
  <NetworkAccessAccount>
    <Domain>CORPMGMT</Domain>
    <Username>sccm_naa</Username>
    <Password>NaaSecretPassword2026!</Password>
    <Description>Auto-generated Network Access Account for Distribution Share Downloads</Description>
  </NetworkAccessAccount>
</SmsMediaConfig>
"""

with open("/opt/sccm/shares/SMSPKGD/TSConfig.xml", "w") as f:
    f.write(tsconfig_content)
os.chmod("/opt/sccm/shares/SMSPKGD/TSConfig.xml", 0o644)

with open("/opt/sccm/web/TSConfig.xml", "w") as f:
    f.write(tsconfig_content)
os.chmod("/opt/sccm/web/TSConfig.xml", 0o644)


client_push_content = """[SCCM Client Push Installation Settings]
SiteCode = PS1
ClientPushEnabled = True
InstallOnServers = True
InstallOnWorkstations = True

[Configured Administrative Push Accounts]
Account = CORPMGMT\\sccm_client_push
Password = ClientPushAdminPass2026!
AssignedRole = Enterprise SCCM Deployer & Domain Admin
"""

with open("/opt/sccm/config/client_push_creds.txt", "w") as f:
    f.write(client_push_content)
os.chmod("/opt/sccm/config/client_push_creds.txt", 0o644)


try:
    subprocess.run(["chown", "-R", "sccm_naa:sccm_naa", "/opt/sccm"])
except Exception:
    pass


web_html = """<!DOCTYPE html>
<html>
<head>
  <title>Microsoft Endpoint Configuration Manager - Management Point</title>
  <style>
    body { font-family: Segoe UI, sans-serif; background: #f4f6f8; margin: 40px; color: #2d3748; }
    .card { background: white; border-radius: 8px; padding: 25px; box-shadow: 0 4px 12px rgba(0,0,0,0.08); max-width: 820px; margin: auto; }
    h1 { color: #0078d4; border-bottom: 2px solid #0078d4; padding-bottom: 8px; }
    table { width: 100%; border-collapse: collapse; margin-top: 20px; }
    th, td { padding: 12px; border-bottom: 1px solid #e2e8f0; text-align: left; }
    th { background: #edf2f7; }
    .badge { background: #38a169; color: white; padding: 4px 8px; border-radius: 4px; font-size: 13px; }
  </style>
</head>
<body>
  <div class="card">
    <h1>MECM Primary Site Server (Site Code: PS1)</h1>
    <p><strong>Management Point:</strong> sccm-site-srv.corp-management.local (10.112.20.20)</p>
    <p><strong>Restricted DC Gateway:</strong> 10.112.10.10 (Direct Access Filtered by Perimeter Firewall)</p>
    <p><strong>Distribution Point Share:</strong> \\\\10.112.20.20\\SMSPKGD$ (TSConfig.xml)</p>
    <p><strong>System Status:</strong> <span class="badge">Operational</span></p>
    <h3>Site Roles & Services</h3>
    <table>
      <tr><th>Role</th><th>Service Port</th><th>Protocol</th><th>Status</th></tr>
      <tr><td>Management Point</td><td>80, 443</td><td>HTTP / BITS</td><td>Online</td></tr>
      <tr><td>Distribution Point</td><td>445</td><td>SMB2 / SMB3</td><td>Active</td></tr>
      <tr><td>Client Push Engine</td><td>22, 135</td><td>RPC / SSH</td><td>Listening</td></tr>
    </table>
  </div>
</body>
</html>
"""

with open("/opt/sccm/web/index.html", "w") as f:
    f.write(web_html)


smb_conf = """[global]
   workgroup = CORPMGMT
   server string = SCCM Distribution Point
   security = user
   map to guest = Bad User
   guest account = nobody
   load printers = no
   disable netbios = yes
   smb ports = 445

[SMSPKGD$]
   path = /opt/sccm/shares/SMSPKGD
   read only = yes
   guest ok = yes
   guest only = yes
   browseable = yes
"""

with open("/etc/samba/smb.conf", "w") as f:
    f.write(smb_conf)

subprocess.run(["chmod", "-R", "777", "/opt/sccm/shares"], check=False)
subprocess.run(["service", "smbd", "restart"], check=False)
print("[+] SCCM Site Server services (SMB Distribution Point, Web MP, Configs) configured successfully!")
