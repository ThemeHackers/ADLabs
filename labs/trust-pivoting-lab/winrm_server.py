import base64
import hashlib
import os
import subprocess
from flask import Flask, request, Response

app = Flask(__name__)

VALID_USERS = {
    "j.forestb": "ForestBUserPass2026!",
    "Administrator": "ForestBAdminPass2026!",
}

FLAG = "OSCP{winrm_lateral_movement_forestb_pwned}"
ADMIN_FLAG = "OSCP{cross_forest_trust_full_compromise}"

def check_basic_auth(auth_header):
    if not auth_header or not auth_header.startswith("Basic "):
        return None
    try:
        decoded = base64.b64decode(auth_header[6:]).decode("utf-8")
        username, password = decoded.split(":", 1)
        if username in VALID_USERS and VALID_USERS[username] == password:
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

def winrm_response(output, command=""):
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope"
            xmlns:wsmv="http://schemas.microsoft.com/wbem/wsman/1/wsman.xsd">
  <s:Header>
    <wsmv:ResourceURI>http://schemas.microsoft.com/wbem/wsman/1/windows/shell/cmd</wsmv:ResourceURI>
  </s:Header>
  <s:Body>
    <rsp:ReceiveResponse xmlns:rsp="http://schemas.microsoft.com/wbem/wsman/1/windows/shell">
      <rsp:Stream Name="stdout" CommandId="1">{base64.b64encode(output.encode()).decode()}</rsp:Stream>
      <rsp:CommandState CommandId="1" State="http://schemas.microsoft.com/wbem/wsman/1/windows/shell/CommandState/Done">
        <rsp:ExitCode>0</rsp:ExitCode>
      </rsp:CommandState>
    </rsp:ReceiveResponse>
  </s:Body>
</s:Envelope>"""
    return Response(xml, status=200, headers={
        "Content-Type": "application/soap+xml;charset=UTF-8",
        "Server": "Microsoft-HTTPAPI/2.0"
    })

def handle_command(cmd_input, username):
    cmd = cmd_input.strip().lower()

    if "whoami" in cmd:
        return f"forestb\\{username}\r\n"
    if "hostname" in cmd:
        return "FORESTB-WS01\r\n"
    if "ipconfig" in cmd or "ifconfig" in cmd:
        return (
            "Windows IP Configuration\r\n\r\n"
            "Ethernet adapter Ethernet0:\r\n"
            "   IPv4 Address. . . . . . . . . . . : 10.103.20.30\r\n"
            "   Subnet Mask . . . . . . . . . . . : 255.255.255.0\r\n"
            "   Default Gateway . . . . . . . . . : 10.103.20.254\r\n"
        )
    if "type" in cmd and "flag" in cmd:
        if username == "Administrator":
            return f"{ADMIN_FLAG}\r\n"
        return f"{FLAG}\r\n"
    if "dir" in cmd and "c:\\" in cmd:
        return (
            " Directory of C:\\\r\n\r\n"
            "06/14/2026  12:00 AM    <DIR>          Users\r\n"
            "06/14/2026  12:00 AM    <DIR>          Windows\r\n"
            "06/14/2026  12:00 AM                42 flag.txt\r\n"
            "               1 File(s)             42 bytes\r\n"
        )
    if "net user" in cmd:
        return (
            "User accounts for \\\\FORESTB-WS01\r\n\r\n"
            "-------------------------------------------------------------------------------\r\n"
            "Administrator            j.forestb\r\n"
        )
    if "net localgroup administrators" in cmd:
        return (
            "Members\r\n\r\n"
            "-------------------------------------------------------------------------------\r\n"
            f"FORESTB\\Administrator\r\nFORESTB\\{username}\r\n"
        )
    if "systeminfo" in cmd:
        return (
            "Host Name:                 FORESTB-WS01\r\n"
            "OS Name:                   Microsoft Windows Server 2022\r\n"
            "OS Version:                10.0.20348\r\n"
            "Domain:                    FORESTB.LOCAL\r\n"
            "Logon Server:              \\\\DC-FORESTB\r\n"
        )
    return f"'{cmd_input}' is not recognized as an internal or external command.\r\n"

@app.route("/wsman", methods=["POST"])
def wsman():
    auth = request.headers.get("Authorization", "")
    username = check_basic_auth(auth)
    if not username:
        return winrm_unauthorized()

    body = request.data.decode("utf-8", errors="ignore")
    cmd_input = ""

    if "CommandLine" in body:
        import re
        m = re.search(r"<rsp:Arguments>(.*?)</rsp:Arguments>", body)
        if m:
            try:
                cmd_input = base64.b64decode(m.group(1)).decode("utf-8", errors="ignore")
            except Exception:
                cmd_input = m.group(1)

    if not cmd_input and "Command" in body:
        import re
        m = re.search(r"<rsp:Command>(.*?)</rsp:Command>", body)
        if m:
            cmd_input = m.group(1)

    output = handle_command(cmd_input, username)
    return winrm_response(output, cmd_input)

@app.route("/wsman", methods=["GET"])
def wsman_get():
    return Response(
        "WinRM Service Running - FORESTB-WS01 (10.103.20.30:5985)",
        status=200,
        headers={"Server": "Microsoft-HTTPAPI/2.0", "Content-Type": "text/plain"}
    )

if __name__ == "__main__":
    print("[+] WinRM Simulation Server running on 0.0.0.0:5985", flush=True)
    print("[+] Valid users: j.forestb:ForestBUserPass2026! | Administrator:ForestBAdminPass2026!", flush=True)
    print("[+] Attack: evil-winrm -i 10.103.20.30 -u j.forestb -p ForestBUserPass2026!", flush=True)
    app.run(host="0.0.0.0", port=5985, debug=False)
