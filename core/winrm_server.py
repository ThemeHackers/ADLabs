#!/usr/bin/env python3
"""
ADLabs Centralized WinRM Simulation Server
Compatible with Evil-WinRM, NetExec (CrackMapExec), and pywinrm.
Simulates a Windows WinRM endpoint (WS-Management protocol over HTTP port 5985).
"""

import argparse
import base64
import os
import re
import subprocess
import sys
import uuid
from flask import Flask, request, Response

app = Flask(__name__)

# Server configuration state
CONFIG = {
    "hostname": os.environ.get("WINRM_HOSTNAME", "WIN-SRV01"),
    "domain": os.environ.get("WINRM_DOMAIN", "CORP.LOCAL"),
    "ip": os.environ.get("WINRM_IP", "10.100.10.50"),
    "gateway": os.environ.get("WINRM_GATEWAY", "10.100.10.254"),
    "flag": os.environ.get("WINRM_FLAG", "OSCP{winrm_lateral_movement_pwned}"),
    "admin_flag": os.environ.get("WINRM_ADMIN_FLAG", "OSCP{winrm_local_admin_full_compromise}"),
    "users": {},
    "exec_mode": os.environ.get("WINRM_EXEC_MODE", "simulated"),  # simulated, hybrid, or real
}

def load_users_from_env_or_args(user_args=None, users_file=None):
    users = {}

    # 1. Environment variable: WINRM_USERS="user1:pass1,user2:pass2"
    env_users = os.environ.get("WINRM_USERS", "")
    if env_users:
        for entry in env_users.split(","):
            if ":" in entry:
                u, p = entry.split(":", 1)
                users[u.strip()] = p.strip()

    # 2. Users file
    if users_file and os.path.exists(users_file):
        with open(users_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and ":" in line and not line.startswith("#"):
                    u, p = line.split(":", 1)
                    users[u.strip()] = p.strip()

    # 3. CLI argument
    if user_args:
        for entry in user_args.split(","):
            if ":" in entry:
                u, p = entry.split(":", 1)
                users[u.strip()] = p.strip()

    # Fallback default if empty
    if not users:
        users = {
            "Administrator": "AdminPass2026!",
            "operator": "OperatorPass2026!"
        }
    CONFIG["users"] = users

def check_basic_auth(auth_header):
    if not auth_header or not auth_header.startswith("Basic "):
        return None
    try:
        decoded = base64.b64decode(auth_header[6:]).decode("utf-8")
        username, password = decoded.split(":", 1)
        # Handle DOMAIN\username format
        if "\\" in username:
            _, username = username.split("\\", 1)
        elif "@" in username:
            username, _ = username.split("@", 1)

        if username in CONFIG["users"] and CONFIG["users"][username] == password:
            return username
    except Exception:
        pass
    return None

def winrm_unauthorized():
    return Response(
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope">'
        '<s:Body><s:Fault><s:Code><s:Value>s:Sender</s:Value></s:Code>'
        '<s:Reason><s:Text>Access is denied.</s:Text></s:Reason>'
        '</s:Fault></s:Body></s:Envelope>',
        status=401,
        headers={
            "Content-Type": "application/soap+xml;charset=UTF-8",
            "WWW-Authenticate": 'Basic realm="WinRM"',
            "Server": "Microsoft-HTTPAPI/2.0"
        }
    )

def winrm_shell_response(shell_id):
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope"
            xmlns:wsmv="http://schemas.microsoft.com/wbem/wsman/1/wsman.xsd"
            xmlns:wsa="http://schemas.xmlsoap.org/ws/2004/08/addressing">
  <s:Header>
    <wsa:Action>http://schemas.xmlsoap.org/ws/2004/09/transfer/CreateResponse</wsa:Action>
    <wsa:RelatesTo>{uuid.uuid4()}</wsa:RelatesTo>
  </s:Header>
  <s:Body>
    <rsp:Shell xmlns:rsp="http://schemas.microsoft.com/wbem/wsman/1/windows/shell">
      <rsp:ShellId>{shell_id}</rsp:ShellId>
      <rsp:ResourceURI>http://schemas.microsoft.com/wbem/wsman/1/windows/shell/cmd</rsp:ResourceURI>
      <rsp:Owner>CORP\\Administrator</rsp:Owner>
      <rsp:ClientIP>127.0.0.1</rsp:ClientIP>
    </rsp:Shell>
  </s:Body>
</s:Envelope>"""
    return Response(xml, status=200, headers={
        "Content-Type": "application/soap+xml;charset=UTF-8",
        "Server": "Microsoft-HTTPAPI/2.0"
    })

def winrm_command_response(command_id):
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope"
            xmlns:rsp="http://schemas.microsoft.com/wbem/wsman/1/windows/shell">
  <s:Body>
    <rsp:CommandResponse>
      <rsp:CommandId>{command_id}</rsp:CommandId>
    </rsp:CommandResponse>
  </s:Body>
</s:Envelope>"""
    return Response(xml, status=200, headers={
        "Content-Type": "application/soap+xml;charset=UTF-8",
        "Server": "Microsoft-HTTPAPI/2.0"
    })

def winrm_output_response(output, command_id="1"):
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope"
            xmlns:wsmv="http://schemas.microsoft.com/wbem/wsman/1/wsman.xsd">
  <s:Header>
    <wsmv:ResourceURI>http://schemas.microsoft.com/wbem/wsman/1/windows/shell/cmd</wsmv:ResourceURI>
  </s:Header>
  <s:Body>
    <rsp:ReceiveResponse xmlns:rsp="http://schemas.microsoft.com/wbem/wsman/1/windows/shell">
      <rsp:Stream Name="stdout" CommandId="{command_id}">{base64.b64encode(output.encode()).decode()}</rsp:Stream>
      <rsp:CommandState CommandId="{command_id}" State="http://schemas.microsoft.com/wbem/wsman/1/windows/shell/CommandState/Done">
        <rsp:ExitCode>0</rsp:ExitCode>
      </rsp:CommandState>
    </rsp:ReceiveResponse>
  </s:Body>
</s:Envelope>"""
    return Response(xml, status=200, headers={
        "Content-Type": "application/soap+xml;charset=UTF-8",
        "Server": "Microsoft-HTTPAPI/2.0"
    })

def winrm_empty_response():
    xml = """<?xml version="1.0" encoding="UTF-8"?>
<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope">
  <s:Body/>
</s:Envelope>"""
    return Response(xml, status=200, headers={
        "Content-Type": "application/soap+xml;charset=UTF-8",
        "Server": "Microsoft-HTTPAPI/2.0"
    })

def handle_command(cmd_input, username):
    cmd = cmd_input.strip()
    cmd_lower = cmd.lower()
    hostname = CONFIG["hostname"]
    domain = CONFIG["domain"]
    ip = CONFIG["ip"]
    gw = CONFIG["gateway"]

    # Read dynamic flags if file exists
    flag_val = CONFIG["flag"]
    admin_flag_val = CONFIG["admin_flag"]
    if os.path.exists("/flag.txt"):
        try:
            with open("/flag.txt", "r") as f:
                flag_val = f.read().strip()
        except Exception:
            pass
    if os.path.exists("/root/flag.txt"):
        try:
            with open("/root/flag.txt", "r") as f:
                admin_flag_val = f.read().strip()
        except Exception:
            pass

    # Windows command simulation
    if "whoami" in cmd_lower:
        if "/all" in cmd_lower or "/priv" in cmd_lower:
            return (
                f"USER INFORMATION\r\n----------------\r\n"
                f"User Name: {domain}\\{username}\r\n\r\n"
                f"PRIVILEGES INFORMATION\r\n----------------------\r\n"
                f"SeSecurityPrivilege       Manage auditing and security log    Disabled\r\n"
                f"SeBackupPrivilege         Back up files and directories       Disabled\r\n"
                f"SeRestorePrivilege        Restore files and directories      Disabled\r\n"
                f"SeShutdownPrivilege       Shut down the system               Disabled\r\n"
            )
        return f"{domain}\\{username}\r\n"

    if "hostname" in cmd_lower:
        return f"{hostname}\r\n"

    if "ipconfig" in cmd_lower or "ifconfig" in cmd_lower:
        return (
            "Windows IP Configuration\r\n\r\n"
            "Ethernet adapter Ethernet0:\r\n"
            f"   Connection-specific DNS Suffix  . : {domain.lower()}\r\n"
            f"   IPv4 Address. . . . . . . . . . . : {ip}\r\n"
            f"   Subnet Mask . . . . . . . . . . . : 255.255.255.0\r\n"
            f"   Default Gateway . . . . . . . . . : {gw}\r\n"
        )

    if ("type" in cmd_lower or "cat" in cmd_lower) and ("flag" in cmd_lower or "proof" in cmd_lower or "local" in cmd_lower):
        if username.lower() == "administrator":
            return f"{admin_flag_val}\r\n"
        return f"{flag_val}\r\n"

    if "dir" in cmd_lower or "ls" in cmd_lower:
        return (
            f" Directory of C:\\Users\\{username}\\Desktop\r\n\r\n"
            "06/14/2026  12:00 AM    <DIR>          .\r\n"
            "06/14/2026  12:00 AM    <DIR>          ..\r\n"
            "06/14/2026  12:00 AM                38 proof.txt\r\n"
            "06/14/2026  12:00 AM                38 local.txt\r\n"
            "               2 File(s)             76 bytes\r\n"
        )

    if "net user" in cmd_lower:
        users_list = "            ".join(CONFIG["users"].keys())
        return (
            f"User accounts for \\\\{hostname}\r\n\r\n"
            "-------------------------------------------------------------------------------\r\n"
            f"{users_list}\r\n"
        )

    if "net localgroup administrators" in cmd_lower:
        return (
            f"Members of Administrators on \\\\{hostname}\r\n\r\n"
            "-------------------------------------------------------------------------------\r\n"
            f"{domain}\\Administrator\r\n"
            f"{domain}\\{username}\r\n"
        )

    if "systeminfo" in cmd_lower:
        return (
            f"Host Name:                 {hostname}\r\n"
            f"OS Name:                   Microsoft Windows Server 2022 Datacenter\r\n"
            f"OS Version:                10.0.20348 N/A Build 20348\r\n"
            f"Domain:                    {domain}\r\n"
            f"Network Card(s):           1 NIC(s) Installed.\r\n"
            f"                           [01]: {ip}\r\n"
        )

    # Hybrid execution for real container commands
    if CONFIG["exec_mode"] in ("hybrid", "real") and shutil_which("bash"):
        try:
            res = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
            return (res.stdout or "") + (res.stderr or "") + "\r\n"
        except Exception as e:
            return f"Execution error: {e}\r\n"

    return f"'{cmd_input}' is not recognized as an internal or external command, operable program or batch file.\r\n"

def shutil_which(cmd):
    import shutil
    return shutil.which(cmd)

@app.route("/wsman", methods=["POST"])
def wsman():
    auth = request.headers.get("Authorization", "")
    username = check_basic_auth(auth)
    if not username:
        return winrm_unauthorized()

    body = request.data.decode("utf-8", errors="ignore")
    action = request.headers.get("WSMAN-Action", "") or ""

    # Detect action from body if not in headers
    if "transfer/Create" in body or "wsmv:Create" in body:
        return winrm_shell_response(str(uuid.uuid4()))

    if "transfer/Delete" in body:
        return winrm_empty_response()

    if "windows/shell/Command" in body:
        # Extract command
        cmd_input = ""
        m = re.search(r"<rsp:CommandLine>(.*?)</rsp:CommandLine>", body)
        if m:
            cmd_input = m.group(1).strip()
        else:
            m = re.search(r"<rsp:Arguments>(.*?)</rsp:Arguments>", body)
            if m:
                try:
                    cmd_input = base64.b64decode(m.group(1)).decode("utf-8", errors="ignore")
                except Exception:
                    cmd_input = m.group(1)

        # Store command output for subsequent Receive or return immediately
        app.config["last_cmd"] = cmd_input
        app.config["last_user"] = username
        return winrm_command_response(str(uuid.uuid4()))

    if "windows/shell/Receive" in body:
        cmd_input = app.config.get("last_cmd", "whoami")
        username = app.config.get("last_user", username)
        output = handle_command(cmd_input, username)
        return winrm_output_response(output)

    # Fallback direct command extraction
    cmd_input = ""
    for pattern in [r"<rsp:CommandLine>(.*?)</rsp:CommandLine>", r"<rsp:Arguments>(.*?)</rsp:Arguments>", r"<rsp:Command>(.*?)</rsp:Command>"]:
        m = re.search(pattern, body)
        if m:
            try:
                cmd_input = base64.b64decode(m.group(1)).decode("utf-8", errors="ignore")
            except Exception:
                cmd_input = m.group(1)
            break

    if cmd_input:
        output = handle_command(cmd_input, username)
        return winrm_output_response(output)

    return winrm_empty_response()

@app.route("/wsman", methods=["GET"])
def wsman_get():
    return Response(
        f"WinRM Service Running - {CONFIG['hostname']} ({CONFIG['ip']}:5985)",
        status=200,
        headers={"Server": "Microsoft-HTTPAPI/2.0", "Content-Type": "text/plain"}
    )

def main():
    parser = argparse.ArgumentParser(description="ADLabs Centralized WinRM Simulation Server")
    parser.add_argument("--host", default="0.0.0.0", help="Listen host (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=int(os.environ.get("WINRM_PORT", 5985)), help="Listen port (default: 5985)")
    parser.add_argument("--hostname", default=os.environ.get("WINRM_HOSTNAME", "WIN-SRV01"), help="Simulated Windows hostname")
    parser.add_argument("--domain", default=os.environ.get("WINRM_DOMAIN", "CORP.LOCAL"), help="Simulated Windows domain")
    parser.add_argument("--ip", default=os.environ.get("WINRM_IP", "10.100.10.50"), help="Simulated host IP")
    parser.add_argument("--gateway", default=os.environ.get("WINRM_GATEWAY", "10.100.10.254"), help="Simulated default gateway")
    parser.add_argument("--users", default=None, help="Comma-separated username:password pairs")
    parser.add_argument("--users-file", default=None, help="File containing username:password lines")
    parser.add_argument("--flag", default=os.environ.get("WINRM_FLAG", "OSCP{winrm_lateral_movement_pwned}"), help="User flag")
    parser.add_argument("--admin-flag", default=os.environ.get("WINRM_ADMIN_FLAG", "OSCP{winrm_local_admin_full_compromise}"), help="Admin flag")
    parser.add_argument("--exec-mode", default=os.environ.get("WINRM_EXEC_MODE", "simulated"), choices=["simulated", "hybrid", "real"])

    args = parser.parse_args()

    CONFIG["hostname"] = args.hostname
    CONFIG["domain"] = args.domain
    CONFIG["ip"] = args.ip
    CONFIG["gateway"] = args.gateway
    CONFIG["flag"] = args.flag
    CONFIG["admin_flag"] = args.admin_flag
    CONFIG["exec_mode"] = args.exec_mode

    load_users_from_env_or_args(args.users, args.users_file)

    print(f"[+] ADLabs WinRM Server starting on {args.host}:{args.port}", flush=True)
    print(f"[+] Simulated Host: {CONFIG['hostname']}.{CONFIG['domain']} ({CONFIG['ip']})", flush=True)
    print(f"[+] Loaded {len(CONFIG['users'])} user accounts:", flush=True)
    for u in CONFIG["users"]:
        print(f"    - {u}:{'*' * 8}", flush=True)
    print(f"[+] Connect test: evil-winrm -i {CONFIG['ip']} -u <username> -p <password>", flush=True)

    app.run(host=args.host, port=args.port, debug=False)

if __name__ == "__main__":
    main()
