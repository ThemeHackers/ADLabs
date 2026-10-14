import subprocess
import os
import sys
import time
import argparse
import socket
import re
import atexit
import json
import urllib.request
import shutil

# Core ADLabs modules
try:
    from core.generate_wordlists import (
        create_wordlist_for_lab,
        generate_all_wordlists,
        load_lab_credentials
    )
except ImportError:
    create_wordlist_for_lab = None
    generate_all_wordlists = None
    load_lab_credentials = None

try:
    from core.flag_manager import (
        load_flags_db,
        init_flags_for_all_labs,
        submit_flag,
        get_hints,
        calculate_score
    )
except ImportError:
    load_flags_db = None
    init_flags_for_all_labs = None
    submit_flag = None
    get_hints = None
    calculate_score = None

try:
    from core.mock_exam import (
        start_mock_exam,
        get_exam_status,
        stop_mock_exam,
        load_exam_session,
        submit_exam_flag
    )
except ImportError:
    start_mock_exam = None
    get_exam_status = None
    stop_mock_exam = None
    load_exam_session = None
    submit_exam_flag = None

CONFIG_HOST_FILE = ".adlabs_host"
ACTIVE_HOST_OVERRIDE = None

BLUE = "\033[94m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
MAGENTA = "\033[95m"
CYAN = "\033[96m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"

if os.name == 'nt':
    os.system('')

def print_info(msg):
    print(f"{CYAN}[*] {msg}{RESET}")

def print_success(msg):
    print(f"{GREEN}{BOLD}[+] {msg}{RESET}")

def print_warning(msg):
    print(f"{YELLOW}{BOLD}[!] {msg}{RESET}")

def print_error(msg):
    print(f"{RED}{BOLD}[x] {msg}{RESET}")

def print_header(msg):
    print(f"\n{MAGENTA}{BOLD}━━━ {msg} ━━━{RESET}")

def print_step(current, total, msg):
    print(f"\n{CYAN}{BOLD}▸ Step {current}/{total} ─ {msg}{RESET}")

def print_divider():
    print(f"{DIM}{'─' * 62}{RESET}")

def format_duration(seconds):
    seconds = int(seconds)
    mins, secs = divmod(seconds, 60)
    if mins > 0:
        return f"{mins}m {secs}s"
    return f"{secs}s"

def print_summary_box(title, rows):
    body = [(str(k), str(v)) for k, v in rows]
    width = len(title)
    for k, v in body:
        row_len = len(k) + len(v) + 5
        if row_len > width:
            width = row_len
    width += 4
    print(f"\n{GREEN}{BOLD}╭{'─' * width}╮{RESET}")
    print(f"{GREEN}{BOLD}│{RESET} {BOLD}{title:<{width - 2}}{RESET} {GREEN}{BOLD}│{RESET}")
    print(f"{GREEN}{BOLD}├{'─' * width}┤{RESET}")
    for k, v in body:
        line = f"{k}: {v}"
        print(f"{GREEN}{BOLD}│{RESET} {line:<{width - 2}} {GREEN}{BOLD}│{RESET}")
    print(f"{GREEN}{BOLD}╰{'─' * width}╯{RESET}")

LOCK_NAME = "adlabs.lock"

def pid_alive(pid):
    if os.name == "nt":
        try:
            res = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"], capture_output=True, text=True)
            for line in res.stdout.splitlines():
                parts = line.split()
                if len(parts) >= 2 and parts[1] == str(pid):
                    return True
            return False
        except Exception:
            return True
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except Exception:
        return True

def acquire_deploy_lock(base_dir):
    lock_path = os.path.join(base_dir, LOCK_NAME)
    try:
        fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(fd, str(os.getpid()).encode("utf-8"))
        os.close(fd)
        return True
    except FileExistsError:
        pass
    try:
        with open(lock_path, "r", encoding="utf-8") as f:
            old_pid = int(f.read().strip())
    except Exception:
        old_pid = None
    if old_pid is not None:
        if pid_alive(old_pid):
            print_error(f"Another ADLabs task is already running (PID {old_pid}). Exiting...")
            return False
    try:
        os.remove(lock_path)
    except Exception:
        pass
    return acquire_deploy_lock(base_dir)

def release_deploy_lock(base_dir):
    try:
        os.remove(os.path.join(base_dir, LOCK_NAME))
    except Exception:
        pass

def find_lab(labs_def, target):
    key = target.strip()
    for lab in labs_def:
        if key.isdigit() and int(key) == lab["index"]:
            return lab
        if lab["dir"] == key:
            return lab
    return None

def check_prerequisites():
    ok = True
    if sys.version_info < (3, 8):
        print_error("Python 3.8 or higher is required.")
        ok = False
    try:
        r = subprocess.run(["docker", "--version"], capture_output=True, text=True)
        if r.returncode != 0:
            print_error("Docker is not available. Please install and start Docker.")
            ok = False
    except FileNotFoundError:
        print_error("Docker is not installed or not in PATH.")
        ok = False
    try:
        r = subprocess.run(["docker", "compose", "version"], capture_output=True, text=True)
        if r.returncode != 0:
            print_error("Docker Compose v2 is not available.")
            ok = False
    except FileNotFoundError:
        print_error("Docker Compose is not installed.")
        ok = False
    return ok

def run_cmd(cmd, check=True):
    print(f"{DIM}› {' '.join(cmd)}{RESET}")
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )
    stdout_lines = []
    for line in iter(process.stdout.readline, ''):
        print(f"{DIM}│{RESET} " + line, end='', flush=True)
        stdout_lines.append(line)
    process.stdout.close()
    return_code = process.wait()

    class MockCompletedProcess:
        def __init__(self, returncode, stdout, stderr):
            self.returncode = returncode
            self.stdout = stdout
            self.stderr = stderr

    res = MockCompletedProcess(return_code, ''.join(stdout_lines), '')
    if res.returncode != 0:
        if check:
            print_error(f"Error executing command: exit code {res.returncode}")
            sys.exit(res.returncode)
        else:
            print_warning(f"Command exited with code {res.returncode} (continuing)...")
    return res

def wait_for_healthy(container_name, timeout=180):
    print_info(f"Waiting for {container_name} to become healthy...")
    start_time = time.time()
    while time.time() - start_time < timeout:
        res = subprocess.run(["docker", "inspect", "--format", "{{.State.Health.Status}}", container_name], capture_output=True, text=True)
        status = res.stdout.strip()
        if status == "healthy":
            print_success(f"{container_name} is HEALTHY ({format_duration(time.time() - start_time)}).")
            return True
        if status == "" or "no value" in status.lower() or status == "none":
            run_res = subprocess.run(["docker", "inspect", "--format", "{{.State.Running}}", container_name], capture_output=True, text=True)
            if run_res.stdout.strip() == "true":
                print_success(f"{container_name} is RUNNING ({format_duration(time.time() - start_time)}).")
                return True
        time.sleep(5)
    print_warning(f"Timeout waiting for {container_name} to become healthy. Continuing anyway...")
    return False

def wait_for_postgres(container_name, timeout=30):
    print_info(f"Waiting for {container_name} to accept connections...")
    for _ in range(timeout // 2):
        res = subprocess.run(["docker", "exec", "-u", "postgres", container_name, "pg_isready"], capture_output=True, text=True)
        if res.returncode == 0:
            print_success(f"{container_name} is ready.")
            return True
        time.sleep(2)
    print_warning(f"Could not verify {container_name} readiness. Proceeding anyway...")
    return False

def wait_for_running(container_name, timeout=180):
    print_info(f"Waiting for {container_name} to be running...")
    start_time = time.time()
    while time.time() - start_time < timeout:
        res = subprocess.run(["docker", "inspect", "--format", "{{.State.Status}}", container_name], capture_output=True, text=True)
        status = res.stdout.strip()
        if status == "running":
            print_success(f"{container_name} is running ({format_duration(time.time() - start_time)}).")
            return True
        time.sleep(5)
    print_error(f"{container_name} is stuck in '{status}' state. Last logs:")
    logs = subprocess.run(["docker", "logs", "--tail", "30", container_name], capture_output=True, text=True)
    print(f"{DIM}│{RESET} " + (logs.stdout.strip() + "\n" + logs.stderr.strip()).strip().replace("\n", f"\n{DIM}│{RESET} "))
    return False

def wait_for_tcp(src_container, target_ip, target_port, timeout=180):
    print_info(f"Waiting for {target_ip}:{target_port} (probed from {src_container})...")
    start_time = time.time()
    py_code = "import socket, sys; s=socket.socket(); s.settimeout(2); sys.exit(s.connect_ex((sys.argv[1], int(sys.argv[2]))))"
    sh_fallback = f"nc -z -w 2 {target_ip} {target_port} 2>/dev/null || (cat < /dev/null > /dev/tcp/{target_ip}/{target_port}) 2>/dev/null"
    while time.time() - start_time < timeout:
        res = subprocess.run(
            ["docker", "exec", src_container, "python3", "-c", py_code, str(target_ip), str(target_port)],
            capture_output=True, text=True
        )
        if res.returncode == 0:
            print_success(f"{target_ip}:{target_port} is reachable ({format_duration(time.time() - start_time)}).")
            return True
        if res.returncode == 127 or "not found" in res.stderr.lower():
            res_sh = subprocess.run(["docker", "exec", src_container, "sh", "-c", sh_fallback], capture_output=True, text=True)
            if res_sh.returncode == 0:
                print_success(f"{target_ip}:{target_port} is reachable ({format_duration(time.time() - start_time)}).")
                return True
        time.sleep(5)
    print_warning(f"Timeout waiting for {target_ip}:{target_port}. Continuing anyway...")
    return False

def process_wg_config(src_path, dest_path, host_ip, allocated_port, allocated_client_ip):
    print_info(f"Waiting for WG config file: {src_path} ...")
    for _ in range(60):
        if os.path.exists(src_path):
            break
        time.sleep(1)
    if not os.path.exists(src_path):
        print_error(f"Error: WG config file {src_path} not found.")
        return False

    with open(src_path, "r") as f:
        lines = f.readlines()
    filtered = []
    for line in lines:
        if "ListenPort" in line:
            continue
        elif line.strip().startswith("Address"):
            addr_val = allocated_client_ip if "/" in allocated_client_ip else f"{allocated_client_ip}/24"
            filtered.append(f"Address = {addr_val}\n")
        elif line.strip().startswith("Endpoint"):
            filtered.append(f"Endpoint = {host_ip}:{allocated_port}\n")
        else:
            filtered.append(line)

    with open(dest_path, "w") as f:
        f.writelines(filtered)
    try:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        central_vpn = os.path.join(base_dir, "output", "vpn")
        os.makedirs(central_vpn, exist_ok=True)
        shutil.copy2(dest_path, os.path.join(central_vpn, os.path.basename(dest_path)))
    except Exception:
        pass
    print_success(f"Processed and wrote: {dest_path} (Endpoint={host_ip}:{allocated_port}, Address={allocated_client_ip})")
    return True

def process_generated_creds(src_container, dest_dir):
    os.makedirs(dest_dir, exist_ok=True)
    cred_host_path = os.path.join(dest_dir, "credentials.txt")
    if os.path.exists(cred_host_path):
        try:
            os.remove(cred_host_path)
        except Exception:
            pass
    run_cmd(["docker", "cp", f"{src_container}:/tmp/credentials_generated.txt", cred_host_path], check=False)

    if os.path.exists(cred_host_path):
        with open(cred_host_path, "r") as f:
            lines = f.read().splitlines()
        usernames = []
        passwords = []
        for line in lines:
            if ":" in line:
                u, p = line.split(":", 1)
                usernames.append(u)
                passwords.append(p)
        with open(os.path.join(dest_dir, "usernames.txt"), "w") as uf:
            uf.write("\n".join(usernames) + "\n")
        with open(os.path.join(dest_dir, "passwords.txt"), "w") as pf:
            pf.write("\n".join(passwords) + "\n")
        print_success(f"Processed credentials in {dest_dir}")


def provision_lab1(base_dir, script_path):
    print_header("Provisioning Lab 1 (oscp-network-pivot-lab)")
    run_cmd(["docker", "exec", "perimeter-nginx-ui", "sh", "-c", "echo 'OSCP{foothold_perimeter_breached}' > /var/flag.txt"], check=False)

    run_cmd(["docker", "exec", "perimeter-nginx-ui", "sh", "-c", "mkdir -p /var/www/html && printf '[database]\\ndb_host = 10.20.20.20\\ndb_port = 5432\\ndb_user = postgres\\ndb_pass = DB_Prod_Admin_SuperSecure_Pass2026!\\ndb_name = production\\n' > /var/www/html/db_settings.conf"], check=False)
    run_cmd(["docker", "exec", "perimeter-nginx-ui", "sh", "-c", "printf '[database]\\ndb_host = 10.20.20.20\\ndb_port = 5432\\ndb_user = postgres\\ndb_pass = DB_Prod_Admin_SuperSecure_Pass2026!\\ndb_name = production\\n' > /tmp/db_config.txt"], check=False)

    print_info("Waiting for internal-postgres-db to accept connections...")
    db_ready = False
    for _ in range(15):
        res = subprocess.run(["docker", "exec", "-u", "postgres", "internal-postgres-db", "pg_isready"], capture_output=True, text=True)
        if res.returncode == 0:
            db_ready = True
            print_success("internal-postgres-db is ready.")
            break
        time.sleep(2)

    if not db_ready:
        print_warning("Could not verify internal-postgres-db readiness. Attempting queries anyway...")
    run_cmd(["docker", "exec", "-u", "postgres", "internal-postgres-db", "psql", "-d", "postgres", "-c", "CREATE TABLE IF NOT EXISTS ad_sync_credentials (id SERIAL PRIMARY KEY, service_name VARCHAR(100), ad_username VARCHAR(100), ad_password VARCHAR(100), description TEXT);"], check=False)
    run_cmd(["docker", "exec", "-u", "postgres", "internal-postgres-db", "psql", "-d", "postgres", "-c", "INSERT INTO ad_sync_credentials (service_name, ad_username, ad_password, description) VALUES ('LDAP User Sync', 'l1_j.doe', 'SimplePass2026!', 'AD Bind account for synchronizing users');"], check=False)

    run_cmd(["docker", "cp", script_path, "ad-forest-parent:/tmp/configure_ad.py"])
    run_cmd(["docker", "exec", "ad-forest-parent", "python3", "/tmp/configure_ad.py", "--role", "parent", "--realm", "MEGACORP.LOCAL", "--user-prefix", "l1_"])
    run_cmd(["docker", "cp", script_path, "ad-forest-child:/tmp/configure_ad.py"])
    practice_users_l1 = "j.smith r.jones m.brown t.taylor d.miller j.wilson b.moore s.taylor a.anderson k.thomas c.jackson m.white l.harris e.martin r.clark s.lewis g.robinson j.walker k.young p.allen"
    run_cmd(["docker", "exec", "ad-forest-child", "python3", "/tmp/configure_ad.py", "--role", "child", "--realm", "HQ.MEGACORP.LOCAL", "--practice-users", practice_users_l1, "--user-prefix", "l1_"])
    process_generated_creds("ad-forest-child", os.path.join(base_dir, "labs", "oscp-network-pivot-lab", "oscp_exam_assets"))

    print_info("Applying anti-cheat network isolation rules to WireGuard gateway...")
    run_cmd(["docker", "exec", "oscp-wg-gateway", "iptables", "-I", "FORWARD", "-i", "wg0", "-d", "10.20.20.20", "-p", "tcp", "--dport", "5432", "-j", "ACCEPT"], check=False)
    run_cmd(["docker", "exec", "oscp-wg-gateway", "iptables", "-I", "FORWARD", "-i", "wg0", "-d", "10.20.20.30", "-p", "tcp", "--dport", "6379", "-j", "ACCEPT"], check=False)
    run_cmd(["docker", "exec", "oscp-wg-gateway", "iptables", "-A", "FORWARD", "-i", "wg0", "-d", "10.20.20.0/24", "-j", "DROP"], check=False)
    run_cmd(["docker", "exec", "oscp-wg-gateway", "iptables", "-A", "FORWARD", "-i", "wg0", "-d", "10.100.10.0/24", "-j", "DROP"], check=False)


def provision_lab2(base_dir, script_path):
    print_header("Provisioning Lab 2 (multi-domain-forest-lab)")
    run_cmd(["docker", "cp", script_path, "mega-dc-parent:/tmp/configure_ad.py"])
    run_cmd(["docker", "exec", "mega-dc-parent", "python3", "/tmp/configure_ad.py", "--role", "parent", "--realm", "MEGACORP.LOCAL", "--user-prefix", "l2_"])
    run_cmd(["docker", "cp", script_path, "mega-dc-child:/tmp/configure_ad.py"])
    practice_users_l2 = "j.doe a.smith b.gates l.torvalds s.jobs"
    run_cmd(["docker", "exec", "mega-dc-child", "python3", "/tmp/configure_ad.py", "--role", "child", "--realm", "HQ.MEGACORP.LOCAL", "--practice-users", practice_users_l2, "--user-prefix", "l2_"])
    process_generated_creds("mega-dc-child", os.path.join(base_dir, "labs", "multi-domain-forest-lab"))
    run_cmd(["docker", "cp", script_path, "mega-dc-tree:/tmp/configure_ad.py"])
    run_cmd(["docker", "exec", "mega-dc-tree", "python3", "/tmp/configure_ad.py", "--role", "tree", "--realm", "CYBERTECH.LOCAL", "--user-prefix", "l2_"])

def provision_lab3(base_dir, script_path):
    print_header("Provisioning Lab 3 (adcs-abuse-lab)")
    run_cmd(["docker", "cp", script_path, "adcs-dc:/tmp/configure_ad.py"])
    run_cmd(["docker", "exec", "adcs-dc", "python3", "/tmp/configure_ad.py", "--role", "parent", "--realm", "ADCSLAB.LOCAL", "--user-prefix", "l3_"])
    run_cmd(["docker", "exec", "adcs-dc", "samba-tool", "user", "create", "l3_j.doe", "StudentPass2026!", "--realm=ADCSLAB.LOCAL", "--configfile=/samba/etc/smb.conf"], check=False)
    run_cmd(["docker", "exec", "adcs-dc", "samba-tool", "user", "setpassword", "l3_j.doe", "--newpassword=StudentPass2026!", "--configfile=/samba/etc/smb.conf"], check=False)
    run_cmd(["docker", "exec", "adcs-dc", "samba-tool", "user", "setpassword", "Administrator", "--newpassword=ADCSLabAdminPass2026!", "--configfile=/samba/etc/smb.conf"])
    run_cmd(["docker", "exec", "adcs-dc", "mkdir", "-p", "/tmp/ca"])

def provision_lab4(base_dir, script_path):
    print_header("Provisioning Lab 4 (trust-pivoting-lab)")
    run_cmd(["docker", "cp", script_path, "dc-foresta:/tmp/configure_ad.py"])
    run_cmd(["docker", "exec", "dc-foresta", "python3", "/tmp/configure_ad.py", "--role", "parent", "--realm", "FORESTA.LOCAL", "--user-prefix", "l4a_"])
    run_cmd(["docker", "cp", script_path, "dc-forestb:/tmp/configure_ad.py"])
    run_cmd(["docker", "exec", "dc-forestb", "python3", "/tmp/configure_ad.py", "--role", "parent", "--realm", "FORESTB.LOCAL", "--user-prefix", "l4b_"])
    run_cmd(["docker", "exec", "dc-foresta", "samba-tool", "user", "setpassword", "Administrator", "--newpassword=ForestAAdminPass2026!", "--configfile=/samba/etc/smb.conf"])
    run_cmd(["docker", "exec", "dc-forestb", "samba-tool", "user", "setpassword", "Administrator", "--newpassword=ForestBAdminPass2026!", "--configfile=/samba/etc/smb.conf"])
    run_cmd(["docker", "exec", "dc-forestb", "samba-tool", "user", "create", "l4b_student", "SimpleStudentPass2026!", "--realm=FORESTB.LOCAL", "--configfile=/samba/etc/smb.conf"], check=False)
    wait_for_tcp("dc-foresta", "10.103.20.10", 389)
    wait_for_tcp("dc-forestb", "10.103.10.10", 389)
    run_cmd([
        "docker", "exec", "dc-foresta", "samba-tool", "domain", "trust", "create", "forestb.local",
        "--type=external", "--direction=both", "--create-location=both",
        "--password=TrustPassword2026!", "-U", "Administrator@FORESTB.LOCAL%ForestBAdminPass2026!",
        "--local-dc-username=Administrator@FORESTA.LOCAL", "--local-dc-password=ForestAAdminPass2026!",
        "--configfile=/samba/etc/smb.conf"
    ], check=False)

    res_sid = run_cmd(["docker", "exec", "dc-forestb", "python3", "-c",
                       "import samba, samba.param, samba.samdb, samba.ndr, samba.dcerpc.security; "
                       "lp=samba.param.LoadParm(); lp.load('/samba/etc/smb.conf'); "
                       "samdb=samba.samdb.SamDB('/samba/private/sam.ldb', lp=lp); "
                       "res=samdb.search(expression='sAMAccountName=l4b_student'); "
                       "sid=samba.ndr.ndr_unpack(samba.dcerpc.security.dom_sid, bytes(res[0]['objectSid'][0])); "
                       "print(str(sid))"])
    student_sid = res_sid.stdout.strip()
    print_info(f"Retrieved Forest B student SID: {student_sid}")

    run_cmd(["docker", "exec", "dc-foresta", "samba-tool", "group", "add", "l4a_helpdesk", "--configfile=/samba/etc/smb.conf"], check=False)
    run_cmd(["docker", "exec", "dc-foresta", "samba-tool", "group", "addmembers", "l4a_helpdesk", student_sid, "--configfile=/samba/etc/smb.conf"], check=False)

    temp_script_path = os.path.join(base_dir, "temp_trust_acl.py")
    with open(temp_script_path, "w") as f:
        f.write(f"""import samba, samba.param, samba.samdb, samba.dsdb, samba.ndr
import ldb
from ldb import Message, MessageElement, Dn
import samba.dcerpc.security as security
from samba.auth import system_session

lp = samba.param.LoadParm()
lp.load('/samba/etc/smb.conf')
samdb = samba.samdb.SamDB('/samba/private/sam.ldb', lp=lp, session_info=system_session())

try:
    res_da = samdb.search(expression='sAMAccountName=Domain Admins')
    da_dn = res_da[0].dn

    res_gp = samdb.search(expression='sAMAccountName=l4a_helpdesk')
    gp_sid = samba.ndr.ndr_unpack(security.dom_sid, bytes(res_gp[0]['objectSid'][0]))

    res_sd = samdb.search(base=da_dn, attrs=['nTSecurityDescriptor'])
    sd = samba.ndr.ndr_unpack(security.descriptor, bytes(res_sd[0]['nTSecurityDescriptor'][0]))

    new_ace = security.ace()
    new_ace.type = security.SEC_ACE_TYPE_ACCESS_ALLOWED
    new_ace.flags = 0
    new_ace.access_mask = security.SEC_GENERIC_WRITE
    new_ace.trustee = gp_sid

    aces = list(sd.dacl.aces) if sd.dacl and sd.dacl.aces else []
    aces.append(new_ace)
    sd.dacl.aces = aces
    sd.dacl.num_aces = len(aces)

    msg = Message()
    msg.dn = da_dn
    from ldb import FLAG_MOD_REPLACE
    msg['nTSecurityDescriptor'] = MessageElement(samba.ndr.ndr_pack(sd), FLAG_MOD_REPLACE, 'nTSecurityDescriptor')
    samdb.modify(msg)
    print('Granted l4a_helpdesk GenericWrite over Domain Admins')
except Exception as e:
    print('Failed to grant ACL: ' + str(e))
""")
    run_cmd(["docker", "cp", temp_script_path, "dc-foresta:/tmp/temp_trust_acl.py"])
    run_cmd(["docker", "exec", "dc-foresta", "python3", "/tmp/temp_trust_acl.py"])
    if os.path.exists(temp_script_path):
        os.remove(temp_script_path)

    print_info("Applying anti-cheat network isolation rules to WireGuard gateway...")
    run_cmd(["docker", "exec", "trust-wg-gateway", "iptables", "-A", "FORWARD", "-i", "wg0", "-d", "10.103.10.0/24", "-j", "DROP"], check=False)


def provision_lab5(base_dir, script_path):
    print_header("Provisioning Lab 5 (gpo-admin-pivot-lab)")
    run_cmd(["docker", "cp", script_path, "gpo-dc:/tmp/configure_ad.py"])
    run_cmd(["docker", "exec", "gpo-dc", "python3", "/tmp/configure_ad.py", "--role", "parent", "--realm", "GPOLAB.LOCAL", "--user-prefix", "l5_"])
    run_cmd(["docker", "exec", "gpo-dc", "samba-tool", "user", "setpassword", "Administrator", "--newpassword=GPOLabAdminPass2026!", "--configfile=/samba/etc/smb.conf"])
    run_cmd(["docker", "exec", "gpo-dc", "samba-tool", "user", "create", "l5_operator", "OperatorPass2026!", "--realm=GPOLAB.LOCAL", "--configfile=/samba/etc/smb.conf"], check=False)
    run_cmd(["docker", "exec", "gpo-dc", "mkdir", "-p", "/samba/state/sysvol/gpolab.local/scripts"])
    run_cmd(["docker", "exec", "gpo-dc", "chmod", "-R", "777", "/samba/state/sysvol/gpolab.local/scripts"])
    run_cmd(["docker", "exec", "gpo-dc", "sh", "-c", "echo '#!/bin/sh\necho \"System update checked\"' > /samba/state/sysvol/gpolab.local/scripts/update.sh"])
    run_cmd(["docker", "exec", "gpo-dc", "chmod", "+x", "/samba/state/sysvol/gpolab.local/scripts/update.sh"])

    print_info("Creating authentic GPO GUID folder structure...")
    gpo_guid = "{3137632E-FA86-4d0f-A02F-A5C94B3C53F7}"
    gpo_path = f"/samba/state/sysvol/gpolab.local/Policies/{gpo_guid}/Machine/Preferences/Groups"
    run_cmd(["docker", "exec", "gpo-dc", "mkdir", "-p", gpo_path], check=False)

    groups_xml = """<?xml version="1.0" encoding="utf-8"?>
<Groups clsid="{3125E73C-5169-448C-889E-1ECC56BAA9A4}">
  <User clsid="{DF5F1855-0E2C-4586-819E-E8C4B5D487E0}" name="LocalAdmin" image="2" changed="2026-01-01 00:00:00" uid="{GUID}" userContext="0" removePolicy="0">
    <Properties action="U" newName="" fullName="" description="" cpassword="VABlAHMAdABQAGEAcwBzADIAMAAyADYAIQA=" changeLogon="0" noChange="1" neverExpires="1" acctDisabled="0" subAuthority="" />
  </User>
</Groups>"""
    run_cmd(["docker", "exec", "gpo-dc", "sh", "-c", f"cat > {gpo_path}/Groups.xml << 'EOF'\n{groups_xml}\nEOF"], check=False)
    print_success("Authentic GPO Groups.xml injected with cpassword attribute")

    print_info("Registering computer account ws-gpo-client$ in Active Directory...")
    run_cmd(["docker", "exec", "gpo-dc", "samba-tool", "computer", "create", "ws-gpo-client", "--configfile=/samba/etc/smb.conf"], check=False)
    run_cmd(["docker", "exec", "gpo-dc", "samba-tool", "user", "setpassword", "ws-gpo-client$", "--newpassword=GPOLabAdminPass2026!", "--configfile=/samba/etc/smb.conf"], check=False)

    print_info("Configuring /etc/krb5.conf inside gpo-client-sim...")
    krb5_conf = """[libdefaults]
    default_realm = GPOLAB.LOCAL
    dns_lookup_realm = false
    dns_lookup_kdc = true
    rdns = false

[realms]
    GPOLAB.LOCAL = {
        kdc = 10.104.10.10
        admin_server = 10.104.10.10
    }

[domain_realm]
    .gpolab.local = GPOLAB.LOCAL
    gpolab.local = GPOLAB.LOCAL
"""
    run_cmd(["docker", "exec", "gpo-client-sim", "sh", "-c", "cat > /etc/krb5.conf << 'EOF'\n" + krb5_conf + "EOF"], check=False)

    print_info("Exporting computer keytab for ws-gpo-client$...")
    keytab_export = run_cmd(["docker", "exec", "gpo-dc", "samba-tool", "domain", "exportkeytab", "/tmp/ws-gpo-client.keytab", "--principal=ws-gpo-client$@GPOLAB.LOCAL", "--configfile=/samba/etc/smb.conf"], check=False)

    if keytab_export.returncode == 0:
        print_info("Copying keytab to gpo-client-sim container...")
        copy_result = run_cmd(["docker", "cp", "gpo-dc:/tmp/ws-gpo-client.keytab", "/tmp/ws-gpo-client.keytab"], check=False)
        if copy_result.returncode == 0:
            run_cmd(["docker", "cp", "/tmp/ws-gpo-client.keytab", "gpo-client-sim:/etc/krb5.keytab"], check=False)
            print_success("Domain joined workstation gpo-client-sim configured with krb5.conf and keytab")
        else:
            print_warning("Failed to copy keytab from container - krb5.conf configured but keytab setup incomplete")
    else:
        print_warning("Keytab export failed - krb5.conf configured but keytab setup incomplete (keytab export may not be supported for computer accounts in this Samba version)")

def provision_lab6(base_dir, script_path):
    print_header("Provisioning Lab 6 (rbcd-lab)")
    run_cmd(["docker", "cp", os.path.join(base_dir, "labs", "rbcd-lab", "configure_rbcd.py"), "rbcd-dc:/tmp/configure_rbcd.py"])
    run_cmd(["docker", "exec", "rbcd-dc", "python3", "/tmp/configure_rbcd.py"])
    run_cmd(["docker", "exec", "rbcd-dc", "samba-tool", "user", "setpassword", "Administrator", "--newpassword=RBCDAccessAdminPass2026!", "--configfile=/samba/etc/smb.conf"])

def provision_lab7(base_dir, script_path):
    print_header("Provisioning Lab 7 (sql-pivot-lab)")
    run_cmd(["docker", "cp", os.path.join(base_dir, "labs", "sql-pivot-lab", "configure_sql.py"), "sql-dc:/tmp/configure_sql.py"])
    run_cmd(["docker", "exec", "sql-dc", "python3", "/tmp/configure_sql.py"])
    run_cmd(["docker", "exec", "sql-dc", "samba-tool", "user", "setpassword", "Administrator", "--newpassword=SQLPivotAdminPass2026!", "--configfile=/samba/etc/smb.conf"])

    wait_for_postgres("sql-back")
    wait_for_postgres("sql-front")

    run_cmd(["docker", "exec", "-u", "postgres", "sql-back", "psql", "-d", "postgres", "-c", "CREATE TABLE IF NOT EXISTS secret_flag (id SERIAL PRIMARY KEY, flag_val VARCHAR(100));"], check=False)
    run_cmd(["docker", "exec", "-u", "postgres", "sql-back", "psql", "-d", "postgres", "-c", "INSERT INTO secret_flag (flag_val) VALUES ('OSCP{sql_database_link_pivot_won}');"], check=False)

    run_cmd(["docker", "exec", "-u", "postgres", "sql-front", "psql", "-d", "postgres", "-c", "CREATE EXTENSION IF NOT EXISTS postgres_fdw;"], check=False)
    run_cmd(["docker", "exec", "-u", "postgres", "sql-front", "psql", "-d", "postgres", "-c", "CREATE SERVER IF NOT EXISTS sql_back_link FOREIGN DATA WRAPPER postgres_fdw OPTIONS (host '10.106.10.20', port '5432', dbname 'postgres');"], check=False)
    run_cmd(["docker", "exec", "-u", "postgres", "sql-front", "psql", "-d", "postgres", "-c", "CREATE USER MAPPING IF NOT EXISTS FOR postgres SERVER sql_back_link OPTIONS (user 'postgres', password 'SuperSecureBackPass2026!');"], check=False)
    run_cmd(["docker", "exec", "-u", "postgres", "sql-front", "psql", "-d", "postgres", "-c", "CREATE FOREIGN TABLE IF NOT EXISTS remote_flag (flag_val VARCHAR(100)) SERVER sql_back_link OPTIONS (schema_name 'public', table_name 'secret_flag');"], check=False)

    print_info("Applying anti-cheat network isolation rules to WireGuard gateway...")
    run_cmd(["docker", "exec", "sql-wg-gateway", "iptables", "-A", "FORWARD", "-i", "wg0", "-d", "10.106.10.0/24", "-j", "DROP"], check=False)


def provision_lab8(base_dir, script_path):
    print_header("Provisioning Lab 8 (laps-lab)")
    run_cmd(["docker", "cp", os.path.join(base_dir, "labs", "laps-lab", "configure_laps.py"), "laps-dc:/tmp/configure_laps.py"])
    run_cmd(["docker", "exec", "laps-dc", "python3", "/tmp/configure_laps.py"])
    run_cmd(["docker", "exec", "laps-dc", "samba-tool", "user", "setpassword", "Administrator", "--newpassword=LAPSAdminPass2026!", "--configfile=/samba/etc/smb.conf"])

    print_info("Exporting Domain Admin keytab from laps-dc...")
    run_cmd(["docker", "exec", "laps-dc", "samba-tool", "domain", "exportkeytab", "/tmp/admin.keytab", "--principal=Administrator@LAPSLAB.LOCAL", "--configfile=/samba/etc/smb.conf"], check=False)

    print_info("Obtaining Kerberos ticket cache for Administrator...")
    run_cmd(["docker", "exec", "laps-dc", "kinit", "-k", "-t", "/tmp/admin.keytab", "-c", "/tmp/krb5cc_domain_admin", "Administrator@LAPSLAB.LOCAL"], check=False)

    print_info("Copying ticket cache from laps-dc to host...")
    run_cmd(["docker", "cp", "laps-dc:/tmp/krb5cc_domain_admin", "/tmp/krb5cc_domain_admin"], check=False)

    print_info("Kerberos ticket cache available on host at /tmp/krb5cc_domain_admin")

def provision_lab9(base_dir, script_path):
    print_header("Provisioning Lab 9 (esc8-relay-lab)")
    run_cmd(["docker", "cp", os.path.join(base_dir, "labs", "esc8-relay-lab", "configure_esc8.py"), "esc8-dc:/tmp/configure_esc8.py"])
    run_cmd(["docker", "exec", "esc8-dc", "python3", "/tmp/configure_esc8.py"])
    run_cmd(["docker", "exec", "esc8-dc", "samba-tool", "user", "setpassword", "Administrator", "--newpassword=ESC8AdminPass2026!", "--configfile=/samba/etc/smb.conf"])

def provision_lab10(base_dir, script_path):
    print_header("Provisioning Lab 10 (delegation-s4u-lab)")
    run_cmd(["docker", "cp", os.path.join(base_dir, "labs", "delegation-s4u-lab", "configure_delegation.py"), "deleg-dc:/tmp/configure_delegation.py"])
    run_cmd(["docker", "exec", "deleg-dc", "python3", "/tmp/configure_delegation.py"])
    run_cmd(["docker", "exec", "deleg-dc", "samba-tool", "user", "setpassword", "Administrator", "--newpassword=DelegationAdminPass2026!", "--configfile=/samba/etc/smb.conf"])

def provision_lab11(base_dir, script_path):
    print_header("Provisioning Lab 11 (hybrid-cloud-aad-lab)")
    run_cmd(["docker", "cp", os.path.join(base_dir, "labs", "hybrid-cloud-aad-lab", "configure_hybrid.py"), "hybrid-dc:/tmp/configure_hybrid.py"])
    run_cmd(["docker", "exec", "hybrid-dc", "python3", "/tmp/configure_hybrid.py"])
    run_cmd(["docker", "exec", "hybrid-dc", "samba-tool", "user", "setpassword", "Administrator", "--newpassword=CloudAdminMasterPass2026!", "--configfile=/samba/etc/smb.conf"])

    print_info("Configuring Azure AD Connect synchronization server...")
    run_cmd(["docker", "cp", os.path.join(base_dir, "labs", "hybrid-cloud-aad-lab", "setup_sync_server.py"), "hybrid-sync-srv:/tmp/setup_sync_server.py"])
    run_cmd(["docker", "exec", "hybrid-sync-srv", "python3", "/tmp/setup_sync_server.py"])
    print_success("Lab 11 hybrid cloud environment provisioned successfully!")

def provision_lab12(base_dir, script_path):
    print_header("Provisioning Lab 12 (sccm-mecm-pivot-lab)")
    run_cmd(["docker", "cp", os.path.join(base_dir, "labs", "sccm-mecm-pivot-lab", "configure_sccm.py"), "sccm-dc:/tmp/configure_sccm.py"])
    run_cmd(["docker", "exec", "sccm-dc", "python3", "/tmp/configure_sccm.py"])
    run_cmd(["docker", "exec", "sccm-dc", "samba-tool", "user", "setpassword", "Administrator", "--newpassword=ManagementAdminMasterPass2026!", "--configfile=/samba/etc/smb.conf"])

    print_info("Waiting for sccm-site-srv initialization and python3...")
    for _ in range(60):
        res = subprocess.run(["docker", "exec", "sccm-site-srv", "which", "python3"], capture_output=True, text=True)
        if res.returncode == 0:
            break
        time.sleep(2)

    print_info("Configuring SCCM Site Server & Distribution Point...")
    run_cmd(["docker", "cp", os.path.join(base_dir, "labs", "sccm-mecm-pivot-lab", "setup_site_server.py"), "sccm-site-srv:/tmp/setup_site_server.py"])
    run_cmd(["docker", "exec", "sccm-site-srv", "python3", "/tmp/setup_site_server.py"])

    print_info("Configuring WireGuard gateway routing for pivot topology...")
    run_cmd(["docker", "exec", "sccm-wg-gateway", "ip", "route", "replace", "10.112.10.0/24", "via", "10.112.20.254"], check=False)
    print_success("Lab 12 SCCM & network pivot environment provisioned successfully!")

def get_public_ip(timeout=3):
    endpoints = [
        "https://api.ipify.org",
        "https://ifconfig.me/ip",
        "https://icanhazip.com"
    ]
    for url in endpoints:
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'curl/7.68.0'})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                ip = resp.read().decode('utf-8').strip()
                if ip and re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$', ip):
                    return ip
        except Exception:
            continue
    return None

def get_host_ip(override=None):
    if override and str(override).strip():
        return str(override).strip()
    global ACTIVE_HOST_OVERRIDE
    if ACTIVE_HOST_OVERRIDE:
        return ACTIVE_HOST_OVERRIDE

    for env_var in ["ADLABS_HOST", "HOST_IP", "SERVER_HOST"]:
        val = os.environ.get(env_var)
        if val and val.strip():
            return val.strip()

    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), CONFIG_HOST_FILE)
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                saved = f.read().strip()
                if saved:
                    return saved
        except Exception:
            pass

    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = '127.0.0.1'
    finally:
        s.close()
    return ip

def set_persistent_host(new_host, base_dir, labs_def):
    new_host = str(new_host).strip()
    config_path = os.path.join(base_dir, CONFIG_HOST_FILE)
    with open(config_path, "w", encoding="utf-8") as f:
        f.write(new_host)
    print_success(f"Persistent Host set to: {BOLD}{new_host}{RESET} (Saved in {CONFIG_HOST_FILE})")
    print_info("Updating all WireGuard VPN client profiles and compose configurations...")
    count = 0
    for lab in labs_def:
        compose_path = os.path.join(base_dir, "labs", lab["dir"], "docker-compose.yml")
        if os.path.exists(compose_path):
            generate_vpn_profile(lab, base_dir, override_host=new_host)
            count += 1
    print_success(f"Updated {count} lab VPN configurations with Host: {new_host}")

def auto_update_ip(base_dir, labs_def):
    print_header("Detecting Server IP for Dynamic / Cloud Hosting")
    pub_ip = get_public_ip()
    local_ip = get_host_ip(override="")

    config_path = os.path.join(base_dir, CONFIG_HOST_FILE)
    saved_host = None
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                saved_host = f.read().strip()
        except Exception:
            pass

    if saved_host:
        print_info(f"Previously configured Host: {BOLD}{saved_host}{RESET}")
    print_info(f"Local Interface IP:          {local_ip}")
    if pub_ip:
        print_info(f"Public / External WAN IP:    {BOLD}{pub_ip}{RESET}")
        target = pub_ip
    else:
        print_warning("Public IP check unreachable. Falling back to Local Interface IP.")
        target = local_ip

    set_persistent_host(target, base_dir, labs_def)

def get_docker_used_ports():
    used = set()
    try:
        res = subprocess.run(["docker", "ps", "--format", "{{.Ports}}"], capture_output=True, text=True)
        if res.returncode == 0:
            for token in re.findall(r"0\.0\.0\.0:(\d+)->", res.stdout):
                used.add(int(token))
            for token in re.findall(r"\[::\]:(\d+)->", res.stdout):
                used.add(int(token))
    except Exception:
        pass
    return used

def get_free_udp_port(start_port=51820):
    used = get_docker_used_ports()
    port = start_port
    while True:
        if port in used:
            port += 1
            continue
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            try:
                s.bind(('0.0.0.0', port))
                return port
            except socket.error:
                used.add(port)
                port += 1

def get_free_subnet(start_x=1):
    in_use = set()
    res = subprocess.run(["docker", "network", "ls", "-q"], capture_output=True, text=True)
    if res.returncode == 0:
        ids = res.stdout.strip().split()
        if ids:
            inspect_res = subprocess.run(["docker", "network", "inspect"] + ids, capture_output=True, text=True)
            if inspect_res.returncode == 0:
                subnets = re.findall(r'"Subnet":\s*"([^"]+)"', inspect_res.stdout)
                for sub in subnets:
                    match = re.match(r'10\.252\.(\d+)\.', sub)
                    if match:
                        in_use.add(int(match.group(1)))
    x = start_x
    while x in in_use:
        x += 1
    return f"10.252.{x}.0/24", f"10.252.{x}.2"

def modify_docker_compose(compose_path, host_ip, allocated_port, allocated_subnet):
    with open(compose_path, 'r', encoding='utf-8') as f:
        content = f.read()

    content = re.sub(r'-\s*\d+:51820/udp', f'- {allocated_port}:51820/udp', content)
    content = re.sub(r'-\s*SERVERPORT=\d+', f'- SERVERPORT={allocated_port}', content)
    content = re.sub(r'-\s*SERVERURL=[^\s\n]+', f'- SERVERURL={host_ip}', content)
    content = re.sub(r'-\s*INTERNAL_SUBNET=10\.252\.\d+\.0/24', f'- INTERNAL_SUBNET={allocated_subnet}', content)
    content = re.sub(r'ip route add 10\.252\.\d+\.0/24', f'ip route add {allocated_subnet}', content)

    with open(compose_path, 'w', encoding='utf-8') as f:
        f.write(content)

def generate_vpn_profile(lab, base_dir, override_host=None):
    print_header(f"Generating/Regenerating VPN Profile for {lab['dir']}")
    compose_path = os.path.join(base_dir, "labs", lab["dir"], "docker-compose.yml")
    if not os.path.exists(compose_path):
        print_error(f"docker-compose.yml not found at {compose_path}")
        return False

    with open(compose_path, 'r', encoding='utf-8') as f:
        content = f.read()

    port_match = re.search(r'SERVERPORT=(\d+)', content)
    subnet_match = re.search(r'INTERNAL_SUBNET=(10\.252\.\d+\.0/24)', content)

    if not port_match or not subnet_match:
        default_port = str(lab.get("vpn_port", "51820")).split("/")[0]
        allocated_port = int(default_port) if default_port.isdigit() else 51820
        allocated_subnet = f"10.252.{lab['index']}.0/24"
        allocated_client_ip = f"10.252.{lab['index']}.2"
    else:
        allocated_port = int(port_match.group(1))
        allocated_subnet = subnet_match.group(1)
        subnet_prefix = allocated_subnet.split(".0/24")[0]
        allocated_client_ip = f"{subnet_prefix}.2"

    host_ip = override_host or get_host_ip()
    print_info(f"Using Host / Endpoint: {host_ip}")
    print_info(f"Using WG Port: {allocated_port}")
    print_info(f"Using WG Subnet: {allocated_subnet} (Client IP: {allocated_client_ip})")

    content = re.sub(r'-\s*SERVERURL=[^\s\n]+', f'- SERVERURL={host_ip}', content)
    content = re.sub(r'ip route add 10\.252\.\d+\.0/24', f'ip route add {allocated_subnet}', content)
    with open(compose_path, 'w', encoding='utf-8') as f:
        f.write(content)

    success = True
    for wg_src_sub, wg_dest_name in lab["wg"]:
        src_path = os.path.join(base_dir, "labs", lab["dir"], wg_src_sub, "peer1", "peer1.conf")
        dest_path = os.path.join(base_dir, "labs", lab["dir"], wg_dest_name)
        if not os.path.exists(src_path):
            continue
        if process_wg_config(src_path, dest_path, host_ip, allocated_port, allocated_client_ip):
            print_success(f"Successfully generated client VPN profile at: {dest_path}")
        else:
            success = False

    return success

def stop_other_labs(current_lab, labs_def, base_dir):
    print_info("Checking for running labs to avoid port/resource conflicts...")
    res = subprocess.run(["docker", "ps", "--filter", "label=com.docker.compose.project", "--format", "{{.Label \"com.docker.compose.project\"}}"], capture_output=True, text=True)
    running_projects = set()
    if res.returncode == 0:
        running_projects = {p.strip().lower() for p in res.stdout.strip().split("\n") if p.strip()}

    for lab in labs_def:
        if lab["dir"] == current_lab["dir"]:
            continue

        is_running = False
        if lab["dir"].lower() in running_projects:
            is_running = True
        else:
            check_dc = subprocess.run(["docker", "inspect", "--format", "{{.State.Running}}", lab["dcs"][0]], capture_output=True, text=True)
            if check_dc.returncode == 0 and check_dc.stdout.strip() == "true":
                is_running = True

        if is_running:
            print_warning(f"Conflicting lab '{lab['dir']}' is running. Stopping and cleaning it...")
            os.chdir(os.path.join(base_dir, "labs", lab["dir"]))
            subprocess.run(["docker", "compose", "down"], capture_output=True)
            os.chdir(base_dir)
            print_success(f"Lab {lab['dir']} has stopped.")
            time.sleep(2)

def find_docker_network(lab_dir, net_name):
    res = subprocess.run(["docker", "network", "ls", "--format", "{{.Name}}"], capture_output=True, text=True)
    if res.returncode == 0:
        networks = res.stdout.strip().split()
        normalized_dir = lab_dir.lower().replace("-", "").replace("_", "").replace(".", "")
        for net in networks:
            normalized_net = net.lower().replace("-", "").replace("_", "").replace(".", "")
            if normalized_dir in normalized_net and net_name.lower().replace("-", "").replace("_", "") in normalized_net:
                return net
    return f"{lab_dir}_{net_name}"

def configure_central_dns(lab, labs_def):
    print_info("Configuring central DNS router container...")
    subprocess.run(["docker", "stop", "adlabs-dns"], capture_output=True)
    subprocess.run(["docker", "rm", "adlabs-dns"], capture_output=True)

    cmd = [
        "docker", "run", "-d",
        "--name", "adlabs-dns",
        "-p", "53:53/udp",
        "-p", "53:53/tcp",
        "--restart", "always",
        "andyshinn/dnsmasq:latest"
    ]

    merged = {}
    for entry in labs_def:
        for domain, ip in entry["dns_mappings"].items():
            merged[domain] = ip
    for domain, ip in merged.items():
        cmd.extend(["--server", f"/{domain}/{ip}"])

    cmd.extend(["--server", "8.8.8.8"])

    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print_warning(f"Failed to bind central DNS on port 53: {res.stderr.strip()}")
        print_info("Attempting to run central DNS on fallback port 5353...")
        cmd = [c if c != "53:53/udp" else "5353:53/udp" for c in cmd]
        cmd = [c if c != "53:53/tcp" else "5353:53/tcp" for c in cmd]
        subprocess.run(cmd, capture_output=True)
    else:
        print_success("Central DNS container (adlabs-dns) started on port 53.")

    for entry in labs_def:
        for net_name in entry["dns_networks"]:
            actual_net = find_docker_network(entry["dir"], net_name)
            print_info(f"Connecting central DNS to network: {actual_net}")
            subprocess.run(["docker", "network", "connect", actual_net, "adlabs-dns"], capture_output=True)

def stop_central_dns():
    print_info("Stopping central DNS router...")
    subprocess.run(["docker", "stop", "adlabs-dns"], capture_output=True)
    subprocess.run(["docker", "rm", "adlabs-dns"], capture_output=True)

def start_timeout_daemon(lab, base_dir):
    print_info("Spawning auto-timeout background daemon...")
    daemon_script = os.path.join(base_dir, "core", "adlabs_daemon.py")
    kwargs = {}
    if os.name == 'nt':

        kwargs['creationflags'] = 0x08000000 | 0x00000200
    else:
        kwargs['start_new_session'] = True

    try:
        subprocess.Popen(
            [sys.executable, daemon_script,
             "--lab-dir", os.path.join(base_dir, "labs", lab["dir"]),
             "--wg-container", lab["wg_container"],
             "--timeout", "7200",
             "--idle-timeout", "900"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
            **kwargs
        )
        print_success("Auto-timeout background daemon spawned successfully.")
    except Exception as e:
        print_error(f"Failed to spawn background daemon: {e}")

def deploy_lab(lab, base_dir, script_path, labs_def, stop_others=True, spawn_daemon=True):
    if not check_prerequisites():
        sys.exit(1)
    started = time.time()
    total_steps = 6
    print(f"\n{BLUE}{BOLD}╭{'─' * 60}╮{RESET}")
    print(f"{BLUE}{BOLD}│{RESET} {BOLD}Deploying Lab {lab['index']}/{TOTAL_LABS} ─ {lab['dir']}{RESET}")
    print(f"{BLUE}{BOLD}╰{'─' * 60}╯{RESET}")
    if stop_others:
        stop_other_labs(lab, labs_def, base_dir)
    print_step(1, total_steps, "Allocating network resources")
    host_ip = get_host_ip()
    allocated_port = get_free_udp_port(51820)
    allocated_subnet, allocated_client_ip = get_free_subnet(1)
    print_info(f"Host IP: {host_ip}  |  WG port: {allocated_port}/udp  |  VPN subnet: {allocated_subnet} (client {allocated_client_ip})")

    compose_path = os.path.join(base_dir, "labs", lab["dir"], "docker-compose.yml")
    modify_docker_compose(compose_path, host_ip, allocated_port, allocated_subnet)
    if create_wordlist_for_lab:
        try:
            creds_res = create_wordlist_for_lab(base_dir, lab["dir"], randomize=True)
            print_info(f"Dynamic Wordlists randomized for {lab['dir']} (Active User: {creds_res['user']})")
        except Exception:
            pass
    print_step(2, total_steps, "Starting containers")
    os.chdir(os.path.join(base_dir, "labs", lab["dir"]))
    run_cmd(["docker", "compose", "up", "-d"])
    os.chdir(base_dir)
    for container in lab["containers"]:
        if not wait_for_running(container):
            print_error(f"Deploy aborted for {lab['dir']}: {container} failed to start.")
            return False
    print_step(3, total_steps, "Waiting for containers and domain controllers")
    for dc in lab["dcs"]:
        wait_for_healthy(dc)
    print_step(4, total_steps, "Provisioning vulnerabilities")
    print_info("Sleeping 5s for services stabilization...")
    time.sleep(5)
    try:
        lab["prov_fn"](base_dir, script_path)
    except SystemExit as e:
        print_error(f"Provisioning failed for {lab['dir']} (exit code {e.code}).")
        return False
    try:
        inject_lab_flags(lab, base_dir)
    except Exception as e:
        print_warning(f"Could not inject flags for {lab['dir']}: {e}")
    print_step(5, total_steps, "Configuring DNS and VPN profile")
    configure_central_dns(lab, labs_def)
    for wg_src_sub, wg_dest_name in lab["wg"]:
        src_path = os.path.join(base_dir, "labs", lab["dir"], wg_src_sub, "peer1", "peer1.conf")
        dest_path = os.path.join(base_dir, "labs", lab["dir"], wg_dest_name)
        process_wg_config(src_path, dest_path, host_ip, allocated_port, allocated_client_ip)
    print_step(6, total_steps, "Starting auto-timeout daemon")
    if spawn_daemon:
        start_timeout_daemon(lab, base_dir)
    print_summary_box(f"Lab {lab['index']} READY ─ {lab['dir']}", [
        ("WG endpoint", f"{host_ip}:{allocated_port}/udp"),
        ("VPN client IP", allocated_client_ip),
        ("VPN profile", os.path.join("labs", lab["dir"], lab["vpn_profile"])),
        ("Targets", f"{len(lab['targets'])} services"),
        ("Deploy time", format_duration(time.time() - started)),
    ])
    print(f"{YELLOW}{BOLD}Next:{RESET} import the .conf file into WireGuard and activate the tunnel.")
    return True

def stop_lab(lab, base_dir):
    print(f"\n{YELLOW}{BOLD}■ Stopping lab: {lab['dir']}...{RESET}")
    stop_central_dns()
    os.chdir(os.path.join(base_dir, "labs", lab["dir"]))
    run_cmd(["docker", "compose", "down"])
    os.chdir(base_dir)
    print_success(f"Lab {lab['dir']} has stopped.")

def clean_lab(lab, base_dir):
    print(f"\n{RED}{BOLD}■ Cleaning lab (removing volumes): {lab['dir']}...{RESET}")
    stop_central_dns()
    os.chdir(os.path.join(base_dir, "labs", lab["dir"]))
    run_cmd(["docker", "compose", "down", "-v"])
    os.chdir(base_dir)
    print_success(f"Lab {lab['dir']} has been cleaned.")


def check_container_status(container_name):
    try:
        res = subprocess.run(
            ["docker", "inspect", "--format", "{{.State.Status}} {{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}", container_name],
            capture_output=True, text=True
        )
        if res.returncode != 0:
            return "MISSING", "red"

        output = res.stdout.strip().split()
        status = output[0] if len(output) > 0 else "unknown"
        health = output[1] if len(output) > 1 else "none"

        if status == "running":
            if health == "healthy" or health == "none":
                return "RUNNING", "green"
            elif health == "starting":
                return "STARTING", "yellow"
            else:
                return f"UNHEALTHY ({health})", "red"
        else:
            return f"STOPPED ({status})", "red"
    except Exception:
        return "UNKNOWN", "red"

def test_port(ip, port, timeout=2):
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        s.connect((ip, port))
        s.close()
        return True
    except Exception:
        return False

def test_lab_connectivity(lab):
    wg_container = lab["wg_container"]
    actual_port = lab['vpn_port']
    if wg_container:
        res_port = subprocess.run(["docker", "port", wg_container, "51820/udp"], capture_output=True, text=True)
        if res_port.returncode == 0 and res_port.stdout.strip():
            actual_port = res_port.stdout.strip().split(":")[-1] + "/UDP"

    print(f"\n{BOLD}{CYAN}╭─ Lab {lab['index']}: {lab['dir']}{RESET}")
    print(f"{BOLD}{CYAN}│{RESET} WG port: {actual_port}   Profile: {lab['vpn_profile']}")
    print(f"{BOLD}{CYAN}╰{'─' * 58}{RESET}")
    print(f"\n{BOLD}▸ Containers{RESET}")
    all_containers_running = True
    for container in lab["containers"]:
        status, color_name = check_container_status(container)
        color = GREEN if color_name == "green" else (YELLOW if color_name == "yellow" else RED)
        mark = f"{GREEN}[+]{RESET}" if status == "RUNNING" else f"{RED}[-]{RESET}"
        print(f"  {mark} {container:<25} {color}{status}{RESET}")
        if status != "RUNNING" and "UNHEALTHY" in status:
            all_containers_running = False
        elif status == "MISSING" or "STOPPED" in status:
            all_containers_running = False

    if not all_containers_running:
        print(f"  {YELLOW}[!] Start this lab first: python adlabs.py --lab {lab['index']}{RESET}")
    print(f"\n{BOLD}▸ Service reachability (host → lab){RESET}")
    for target in lab["targets"]:
        success = test_port(target["ip"], target["port"])
        if success:
            print(f"  {GREEN}[+]{RESET} {target['name']:<40} {DIM}{target['ip']}:{target['port']}{RESET}  {GREEN}OPEN{RESET}")
        else:
            print(f"  {RED}[-]{RESET} {target['name']:<40} {DIM}{target['ip']}:{target['port']}{RESET}  {RED}CLOSED{RESET}")
    print_divider()
    print(f"  {DIM}Pivoting labs: internal targets show CLOSED until you pivot through a foothold.{RESET}")
    print(f"  {DIM}If a VPN target is CLOSED, connect WireGuard to '{lab['vpn_profile']}' first.{RESET}")

def run_wordlist_generation(base_dir, randomize=True):
    print_header("Generating / Recreating Dynamic Wordlists for all labs")
    if generate_all_wordlists:
        try:
            generate_all_wordlists(base_dir, randomize=randomize)
        except Exception as e:
            print_error(f"Failed to generate wordlists: {e}")
    else:
        print_error("generate_all_wordlists module is unavailable.")

def get_container_ips(container_name):
    try:
        res = subprocess.run(["docker", "inspect", "--format", "{{json .NetworkSettings.Networks}}", container_name], capture_output=True, text=True)
        if res.returncode == 0 and res.stdout.strip():
            nets = json.loads(res.stdout.strip())
            ips = []
            for _, net_info in nets.items():
                ip = net_info.get("IPAddress")
                if not ip and isinstance(net_info.get("IPAMConfig"), dict):
                    ip = net_info["IPAMConfig"].get("IPv4Address")
                if ip and ip not in ips:
                    ips.append(ip)
            return ", ".join(ips) if ips else "-"
    except Exception:
        pass
    return "-"

def get_lab_runtime_vpn_info(lab, base_dir):
    compose_path = os.path.join(base_dir, "labs", lab["dir"], "docker-compose.yml")
    port = lab.get("vpn_port", "51820/UDP")
    subnet = "N/A"
    client_ip = "N/A"
    endpoint_ip = get_host_ip()

    if os.path.exists(compose_path):
        try:
            with open(compose_path, "r", encoding="utf-8") as f:
                content = f.read()
            m_port = re.search(r'SERVERPORT=(\d+)', content)
            if m_port:
                port = f"{m_port.group(1)}/UDP"
            m_subnet = re.search(r'INTERNAL_SUBNET=(10\.252\.\d+\.0/24)', content)
            if m_subnet:
                subnet = m_subnet.group(1)
                client_ip = f"{subnet.split('.0/24')[0]}.2"
            m_url = re.search(r'SERVERURL=([^\s\n]+)', content)
            if m_url and m_url.group(1) != "auto":
                endpoint_ip = m_url.group(1)
        except Exception:
            pass

    wg_c = lab.get("wg_container")
    if wg_c:
        res_p = subprocess.run(["docker", "port", wg_c, "51820/udp"], capture_output=True, text=True)
        if res_p.returncode == 0 and res_p.stdout.strip():
            port = res_p.stdout.strip().split(":")[-1] + "/UDP"

    return {
        "endpoint": f"{endpoint_ip}:{port.split('/')[0]}",
        "port": port,
        "subnet": subnet,
        "client_ip": client_ip,
        "profile_path": os.path.join("labs", lab["dir"], lab["vpn_profile"])
    }

def get_lab_status(lab, base_dir):
    all_containers = list(lab["containers"])
    wg_c = lab.get("wg_container")
    if wg_c and wg_c not in all_containers:
        all_containers.append(wg_c)

    running_count = 0
    total_count = len(all_containers)
    container_statuses = {}

    for c in all_containers:
        status, color_name = check_container_status(c)
        ips = get_container_ips(c) if status == "RUNNING" else "-"
        container_statuses[c] = {"status": status, "color": color_name, "ips": ips}
        if status == "RUNNING":
            running_count += 1

    if running_count == total_count and total_count > 0:
        overall_status = f"RUNNING ({running_count}/{total_count})"
        overall_color = GREEN
        status_badge = "ACTIVE"
    elif running_count > 0:
        overall_status = f"PARTIAL ({running_count}/{total_count})"
        overall_color = YELLOW
        status_badge = "PARTIAL"
    else:
        overall_status = f"STOPPED (0/{total_count})"
        overall_color = RED
        status_badge = "STOPPED"

    vpn_info = get_lab_runtime_vpn_info(lab, base_dir)

    return {
        "status_str": overall_status,
        "color": overall_color,
        "badge": status_badge,
        "running_count": running_count,
        "total_count": total_count,
        "containers": container_statuses,
        "vpn": vpn_info
    }

def show_all_labs_summary(labs_def, base_dir):
    print(f"\n{BLUE}{BOLD}╭{'─' * 96}╮{RESET}")
    print(f"{BLUE}{BOLD}│{RESET} {BOLD}{'AD LABS STATUS OVERVIEW ─ Active Directory Pentesting Suite':<94}{RESET} {BLUE}{BOLD}│{RESET}")
    print(f"{BLUE}{BOLD}├{'─' * 4}┬{'─' * 26}┬{'─' * 18}┬{'─' * 14}┬{'─' * 30}┤{RESET}")
    print(f"{BLUE}{BOLD}│{RESET} {BOLD}{'#':<2}{RESET} {BLUE}{BOLD}│{RESET} {BOLD}{'LAB DIRECTORY':<24}{RESET} {BLUE}{BOLD}│{RESET} {BOLD}{'STATUS':<16}{RESET} {BLUE}{BOLD}│{RESET} {BOLD}{'VPN PORT':<12}{RESET} {BLUE}{BOLD}│{RESET} {BOLD}{'SCENARIO FOCUS':<28}{RESET} {BLUE}{BOLD}│{RESET}")
    print(f"{BLUE}{BOLD}├{'─' * 4}┼{'─' * 26}┼{'─' * 18}┼{'─' * 14}┼{'─' * 30}┤{RESET}")

    active_count = 0
    partial_count = 0
    stopped_count = 0

    for lab in labs_def:
        info = get_lab_status(lab, base_dir)
        idx = str(lab["index"])
        lab_dir = lab["dir"]
        status_str = info["status_str"]
        col = info["color"]
        vpn_port = info["vpn"]["port"]
        title_summary = lab.get("scenario_focus", lab.get("title", ""))[:28]

        if info["badge"] == "ACTIVE":
            active_count += 1
        elif info["badge"] == "PARTIAL":
            partial_count += 1
        else:
            stopped_count += 1

        print(f"{BLUE}{BOLD}│{RESET} {BOLD}{idx:<2}{RESET} {BLUE}{BOLD}│{RESET} {lab_dir:<24} {BLUE}{BOLD}│{RESET} {col}{status_str:<16}{RESET} {BLUE}{BOLD}│{RESET} {vpn_port:<12} {BLUE}{BOLD}│{RESET} {title_summary:<28} {BLUE}{BOLD}│{RESET}")

    print(f"{BLUE}{BOLD}╰{'─' * 4}┴{'─' * 26}┴{'─' * 18}┴{'─' * 14}┴{'─' * 30}╯{RESET}")
    print(f" {BOLD}Summary:{RESET} Total: {len(labs_def)} | {GREEN}Active: {active_count}{RESET} | {YELLOW}Partial: {partial_count}{RESET} | {RED}Stopped: {stopped_count}{RESET}")
    print(f" {DIM}Tip: Run 'python adlabs.py --info <#>' for full credentials, foothold details, and IPs.{RESET}\n")

def show_lab_info(lab, base_dir):
    info = get_lab_status(lab, base_dir)
    status_str = info["status_str"]
    col = info["color"]
    vpn = info["vpn"]

    print(f"\n{BLUE}{BOLD}╭{'─' * 76}╮{RESET}")
    print(f"{BLUE}{BOLD}│{RESET} {BOLD}LAB {lab['index']}: {lab['dir']}{RESET}")
    print(f"{BLUE}{BOLD}│{RESET}    {CYAN}{lab.get('title', 'Active Directory Lab')}{RESET}")
    print(f"{BLUE}{BOLD}│{RESET}    Current Status: {col}{status_str}{RESET}")
    print(f"{BLUE}{BOLD}╰{'─' * 76}╯{RESET}")

    if lab.get("scenario"):
        print(f"\n{MAGENTA}{BOLD}▸ Scenario & Attack Vectors{RESET}")
        print(f"  {lab['scenario']}")
    if lab.get("objective"):
        print(f"\n{MAGENTA}{BOLD}▸ Objective / Flag{RESET}")
        print(f"  {lab['objective']}")
    if lab.get("attack_chain"):
        print(f"\n{YELLOW}{BOLD}▸ Multi-Step Attack Chain (OSCP/CRTE Challenge){RESET}")
        for step_idx, step_desc in enumerate(lab["attack_chain"], 1):
            print(f"  {BOLD}[Step {step_idx}]{RESET} {step_desc}")

    if lab.get("credentials"):
        print(f"\n{GREEN}{BOLD}▸ Initial Foothold Accounts & Targets{RESET}")
        for role, cred in lab["credentials"]:
            print(f"  • {BOLD}{role:<24}{RESET} : {CYAN}{cred}{RESET}")

    if load_lab_credentials:
        try:
            active_creds = load_lab_credentials()
            if lab["dir"] in active_creds:
                dyn = active_creds[lab["dir"]]
                print(f"  • {BOLD}{'Active Dynamic User':<24}{RESET} : {CYAN}{dyn['user']}:{dyn['pass']}{RESET} {GREEN}(Dynamic Wordlist){RESET}")
        except Exception:
            pass

    if load_flags_db:
        try:
            fdb = load_flags_db()
            if fdb and lab["dir"] in fdb:
                fdata = fdb[lab["dir"]]
                loc_st = f"{GREEN}[SOLVED]{RESET}" if fdata["local"]["solved"] else f"{YELLOW}[UNSOLVED]{RESET}"
                prf_st = f"{GREEN}[SOLVED]{RESET}" if fdata["proof"]["solved"] else f"{YELLOW}[UNSOLVED]{RESET}"
                print(f"\n{MAGENTA}{BOLD}▸ Lab Flags & Target Objectives{RESET}")
                print(f"  • Local Flag ({fdata['local']['points']} pts) : {loc_st} {DIM}{fdata['local']['host']} ({fdata['local']['path']}){RESET}")
                print(f"  • Proof Flag ({fdata['proof']['points']} pts): {prf_st} {DIM}{fdata['proof']['host']} ({fdata['proof']['path']}){RESET}")
        except Exception:
            pass

    wordlist_u = os.path.join(base_dir, "labs", lab["dir"], "users.txt")
    wordlist_p = os.path.join(base_dir, "labs", lab["dir"], "pass.txt")
    if os.path.exists(wordlist_u) and os.path.exists(wordlist_p):
        print(f"  • {DIM}Generated Wordlists   : {os.path.join('labs', lab['dir'], 'users.txt')}, pass.txt{RESET}")

    print(f"\n{CYAN}{BOLD}▸ Containers & IP Addresses{RESET}")
    print(f"  {BOLD}{'Container':<25} {'Status':<18} {'Docker IP':<18}{RESET}")
    print(f"  {DIM}{'─' * 62}{RESET}")
    for c_name, c_info in info["containers"].items():
        st = c_info["status"]
        c_col = GREEN if c_info["color"] == "green" else (YELLOW if c_info["color"] == "yellow" else RED)
        mark = f"{GREEN}[+]{RESET}" if st == "RUNNING" else f"{RED}[-]{RESET}"
        ips = c_info["ips"]
        print(f"  {mark} {c_name:<23} {c_col}{st:<18}{RESET} {ips:<18}")

    print(f"\n{CYAN}{BOLD}▸ Network & WireGuard VPN{RESET}")
    conf_exists = os.path.exists(os.path.join(base_dir, vpn["profile_path"]))
    conf_badge = f"{GREEN}EXISTS{RESET}" if conf_exists else f"{YELLOW}NOT GENERATED YET{RESET}"
    print(f"  • Gateway Container   : {lab.get('wg_container', 'N/A')}")
    print(f"  • WG Endpoint         : {vpn['endpoint']} ({vpn['port']})")
    print(f"  • VPN Subnet / Client : {vpn['subnet']} (Client IP: {vpn['client_ip']})")
    print(f"  • VPN Profile File    : {vpn['profile_path']} [{conf_badge}]")
    if lab.get("dns_mappings"):
        dns_str = ", ".join([f"{k} -> {v}" for k, v in lab["dns_mappings"].items()])
        print(f"  • DNS Mappings        : {dns_str}")

    print(f"\n{CYAN}{BOLD}▸ Targets & Live Service Reachability{RESET}")
    print(f"  {BOLD}{'Service Target':<38} {'Endpoint':<22} {'Status'}{RESET}")
    print(f"  {DIM}{'─' * 68}{RESET}")
    for target in lab.get("targets", []):
        reachable = test_port(target["ip"], target["port"], timeout=1)
        r_mark = f"{GREEN}[+]{RESET}" if reachable else f"{RED}[-]{RESET}"
        r_status = f"{GREEN}OPEN{RESET}" if reachable else f"{RED}CLOSED{RESET}"
        ep = f"{target['ip']}:{target['port']} ({target.get('protocol', 'TCP')})"
        print(f"  {r_mark} {target['name']:<36} {DIM}{ep:<22}{RESET} {r_status}")
    print_divider()
    print(f"  {DIM}Note: Closed targets on internal IPs (10.x.x.x) require connecting via WireGuard first.{RESET}\n")

def connect_wireguard(lab, base_dir):
    conf_path = os.path.join(base_dir, "labs", lab["dir"], lab["vpn_profile"])
    if not os.path.exists(conf_path) or os.path.getsize(conf_path) < 10:
        print_info("VPN profile not found or empty. Generating it now...")
        generate_vpn_profile(lab, base_dir)

    tunnel_name = os.path.splitext(lab["vpn_profile"])[0]
    print_info(f"Connecting WireGuard tunnel for {lab['dir']} ({tunnel_name})...")

    if os.name != 'nt':
        wg_quick = shutil.which("wg-quick")
        if not wg_quick:
            print_error("wg-quick command not found.")
            print_info("Please install wireguard-tools (e.g. sudo apt install wireguard-tools)")
            print_info(f"Profile file available at: {conf_path}")
            return False

        try:
            os.chmod(conf_path, 0o600)
        except Exception:
            pass

        use_sudo = os.geteuid() != 0 if hasattr(os, "geteuid") else True
        prefix = ["sudo"] if use_sudo else []

        allowed_subnets = []
        try:
            with open(conf_path, "r", encoding="utf-8") as f:
                ccontent = f.read()
            ccontent_local = re.sub(r'Endpoint\s*=\s*[^:\n]+:(\d+)', r'Endpoint = 127.0.0.1:\1', ccontent)
            if ccontent_local != ccontent:
                with open(conf_path, "w", encoding="utf-8") as f:
                    f.write(ccontent_local)
                ccontent = ccontent_local

            for line in ccontent.splitlines():
                if line.strip().startswith("AllowedIPs"):
                    _, vals = line.strip().split("=", 1)
                    allowed_subnets = [v.strip() for v in vals.split(",") if v.strip()]
        except Exception:
            pass

        if allowed_subnets:
            route_out = subprocess.run(["ip", "-4", "route", "show"], capture_output=True, text=True).stdout
            for rline in route_out.splitlines():
                parts = rline.strip().split()
                if len(parts) >= 3 and parts[1] == "dev" and (parts[2].startswith("br-") or parts[2].startswith("docker")):
                    if parts[0] in allowed_subnets:
                        subprocess.run(prefix + ["ip", "route", "del", parts[0], "dev", parts[2]], capture_output=True)

        subprocess.run(prefix + ["wg-quick", "down", conf_path], capture_output=True)
        res = subprocess.run(prefix + ["wg-quick", "up", conf_path], capture_output=True, text=True)
        if res.returncode == 0:
            print_success(f"WireGuard tunnel '{tunnel_name}' connected successfully via wg-quick!")
            show_lab_info(lab, base_dir)
            return True
        else:
            print_error(f"Failed to connect: {res.stderr.strip() or res.stdout.strip()}")
            return False

    wg_exe = r"C:\Program Files\WireGuard\wireguard.exe"
    if not os.path.exists(wg_exe):
        print_error(f"WireGuard executable not found at: {wg_exe}")
        print_info("Please install WireGuard from https://www.wireguard.com/install/")
        return False

    is_admin = False
    try:
        import ctypes
        is_admin = (ctypes.windll.shell32.IsUserAnAdmin() != 0)
    except Exception:
        pass

    if is_admin:
        subprocess.run([wg_exe, "/uninstalltunnelservice", tunnel_name], capture_output=True, text=True)
        res = subprocess.run([wg_exe, "/installtunnelservice", conf_path], capture_output=True, text=True)
        time.sleep(2)
        chk = subprocess.run(["sc.exe", "query", f"WireGuardTunnel${tunnel_name}"], capture_output=True, text=True)
        if "RUNNING" in chk.stdout or res.returncode == 0:
            print_success(f"WireGuard tunnel '{tunnel_name}' connected and active via CLI!")
            show_lab_info(lab, base_dir)
            return True
        else:
            print_error(f"Failed to connect: {res.stderr.strip() or res.stdout.strip() or chk.stdout.strip()}")
            return False
    else:
        print_warning("Administrator privileges required to install Windows VPN network service.")
        print_info("Attempting automatic UAC elevation prompt...")
        batch_path = os.path.join(base_dir, "connect.bat")
        if os.path.exists(batch_path):
            cmd = f"Start-Process -FilePath '{batch_path}' -ArgumentList '{lab['index']}' -WorkingDirectory '{base_dir}' -Verb RunAs"
        else:
            cmd = f"Start-Process -FilePath '{wg_exe}' -ArgumentList '/installtunnelservice \"{conf_path}\"' -WorkingDirectory '{base_dir}' -Verb RunAs"
        res = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", cmd], capture_output=True, text=True)
        if res.returncode == 0:
            print_success("Elevation prompt launched! Check the UAC prompt on your screen and click 'Yes'.")
            return True
        else:
            print_error("Could not trigger UAC automatically from current terminal.")
            print_info("You can easily connect via CLI using either method:")
            print(f"  {BOLD}Method 1:{RESET} Run {CYAN}.\\connect.bat {lab['index']}{RESET}")
            print(f"  {BOLD}Method 2:{RESET} Open PowerShell as Administrator and run:")
            print(f"            {CYAN}python adlabs.py --connect {lab['index']}{RESET}")
            return False

def disconnect_wireguard(lab, base_dir):
    tunnel_name = os.path.splitext(lab["vpn_profile"])[0]
    conf_path = os.path.join(base_dir, "labs", lab["dir"], lab["vpn_profile"])
    print_info(f"Disconnecting WireGuard tunnel '{tunnel_name}'...")

    if os.name != 'nt':
        wg_quick = shutil.which("wg-quick")
        if not wg_quick:
            print_error("wg-quick command not found.")
            return False
        use_sudo = os.geteuid() != 0 if hasattr(os, "geteuid") else True
        prefix = ["sudo"] if use_sudo else []
        res = subprocess.run(prefix + ["wg-quick", "down", conf_path], capture_output=True, text=True)

        try:
            inspect_res = subprocess.run(["docker", "network", "ls", "--filter", f"label=com.docker.compose.project={lab['dir']}", "-q"], capture_output=True, text=True)
            if inspect_res.returncode == 0 and inspect_res.stdout.strip():
                for net_id in inspect_res.stdout.strip().split():
                    net_info = subprocess.run(["docker", "network", "inspect", net_id], capture_output=True, text=True)
                    if net_info.returncode == 0:
                        data = json.loads(net_info.stdout)
                        if data and "IPAM" in data[0] and "Config" in data[0]["IPAM"]:
                            for cfg in data[0]["IPAM"]["Config"]:
                                sub = cfg.get("Subnet")
                                gw = cfg.get("Gateway")
                                br_if = f"br-{net_id[:12]}"
                                if sub and gw:
                                    subprocess.run(prefix + ["ip", "route", "add", sub, "dev", br_if, "proto", "kernel", "scope", "link", "src", gw], capture_output=True)
        except Exception:
            pass

        if res.returncode == 0:
            print_success(f"WireGuard tunnel '{tunnel_name}' disconnected successfully.")
            return True
        else:
            print_error(f"Failed to disconnect: {res.stderr.strip() or res.stdout.strip()}")
            return False

    wg_exe = r"C:\Program Files\WireGuard\wireguard.exe"
    is_admin = False
    try:
        import ctypes
        is_admin = (ctypes.windll.shell32.IsUserAnAdmin() != 0)
    except Exception:
        pass

    if is_admin:
        res = subprocess.run([wg_exe, "/uninstalltunnelservice", tunnel_name], capture_output=True, text=True)
        if res.returncode == 0:
            print_success(f"WireGuard tunnel '{tunnel_name}' disconnected successfully.")
            return True
        else:
            print_error(f"Failed to disconnect: {res.stderr.strip() or res.stdout.strip()}")
            return False
    else:
        batch_path = os.path.join(base_dir, "disconnect.bat")
        if os.path.exists(batch_path):
            cmd = f"Start-Process -FilePath '{batch_path}' -ArgumentList '{lab['index']}' -WorkingDirectory '{base_dir}' -Verb RunAs"
        else:
            cmd = f"Start-Process -FilePath '{wg_exe}' -ArgumentList '/uninstalltunnelservice \"{tunnel_name}\"' -WorkingDirectory '{base_dir}' -Verb RunAs"
        res = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", cmd], capture_output=True, text=True)
        if res.returncode == 0:
            print_success(f"WireGuard disconnect command sent for '{tunnel_name}'.")
            return True
        else:
            print_info("You can disconnect via CLI by running:")
            print(f"  {CYAN}.\\disconnect.bat {lab['index']}{RESET}")
            return False

def inject_lab_flags(lab, base_dir):
    if not load_flags_db:
        return
    try:
        db = load_flags_db()
        if not db or lab["dir"] not in db:
            db = init_flags_for_all_labs() if init_flags_for_all_labs else {}
        flag_info = db.get(lab["dir"])
        if not flag_info:
            return

        loc_flag = flag_info["local"]["flag"]
        prf_flag = flag_info["proof"]["flag"]

        if lab["dir"] == "oscp-network-pivot-lab":
            run_cmd(["docker", "exec", "perimeter-nginx-ui", "sh", "-c", f"echo '{loc_flag}' > /home/www-data/local.txt && echo '{loc_flag}' > /var/www/local.txt && echo '{prf_flag}' > /root/proof.txt"], check=False)
            run_cmd(["docker", "exec", "ad-forest-parent", "sh", "-c", f"echo '{prf_flag}' > /root/proof.txt && echo '{prf_flag}' > /samba/proof.txt"], check=False)
        elif lab.get("dcs"):
            main_dc = lab["dcs"][0]
            run_cmd(["docker", "exec", main_dc, "sh", "-c", f"echo '{prf_flag}' > /root/proof.txt && echo '{prf_flag}' > /samba/proof.txt"], check=False)

        for c in lab.get("containers", []):
            if any(k in c for k in ["target", "srv", "client"]):
                run_cmd(["docker", "exec", c, "sh", "-c", f"echo '{loc_flag}' > /flag.txt || true"], check=False)
    except Exception as e:
        print_warning(f"Flag injection warning for {lab['dir']}: {e}")

def handle_connect_command(lab_arg=None, base_dir=None):
    if base_dir is None:
        base_dir = os.path.dirname(os.path.abspath(__file__))
    if not lab_arg:
        print_header("WireGuard Cross-Platform VPN Connector")
        print("\nAvailable Labs:")
        for lab in labs_def:
            print(f"  [{lab['index']}] {lab['dir']} - {lab.get('title', '')}")
        try:
            choice = input(f"\nEnter lab number (1-{len(labs_def)}) or name to connect: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nAborted.")
            return
        if not choice:
            print_error("No lab selected.")
            return
        lab_arg = choice

    matched = find_lab(labs_def, lab_arg)
    if matched:
        connect_wireguard(matched, base_dir)
    else:
        print_error(f"Lab '{lab_arg}' not found.")

def handle_disconnect_command(lab_arg=None, base_dir=None):
    if base_dir is None:
        base_dir = os.path.dirname(os.path.abspath(__file__))
    if not lab_arg:
        print_header("WireGuard Cross-Platform VPN Disconnector")
        print("\nAvailable Labs:")
        for lab in labs_def:
            print(f"  [{lab['index']}] {lab['dir']}")
        try:
            choice = input(f"\nEnter lab number (1-{len(labs_def)}) or name to disconnect: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nAborted.")
            return
        if not choice:
            print_error("No lab selected.")
            return
        lab_arg = choice

    matched = find_lab(labs_def, lab_arg)
    if matched:
        disconnect_wireguard(matched, base_dir)
    else:
        print_error(f"Lab '{lab_arg}' not found.")

def handle_submit_flag(flag_str):
    if not flag_str or not flag_str.strip():
        print_error("Please specify a flag string: adlabs submit <flag>")
        return

    if not submit_flag:
        print_error("Flag management module is unavailable.")
        return

    exam = load_exam_session() if load_exam_session else None
    is_exam = exam and exam.get("status") == "active"

    if is_exam:
        res = submit_exam_flag(flag_str)
        if res["status"] == "success":
            print(f"\n{GREEN}{BOLD}╔══════════════════════════════════════════════════════════════════╗{RESET}")
            print(f"{GREEN}{BOLD}║                 [✓] EXAM FLAG ACCEPTED!                          ║{RESET}")
            print(f"{GREEN}{BOLD}╚══════════════════════════════════════════════════════════════════╝{RESET}")
            print(f"  Target        : {CYAN}{res['target']}{RESET} ({res['type'].upper()} Flag)")
            print(f"  Points Awarded: {GREEN}+{res['points']} pts{RESET}")
            print(f"  Total Score   : {YELLOW}{BOLD}{res['total_score']} / 100 pts{RESET} (Passing: 70 pts)")
            if res["total_score"] >= 70:
                print(f"\n  {GREEN}{BOLD}🎉 CONGRATULATIONS! YOU HAVE REACHED THE 70-POINT PASSING THRESHOLD! 🎉{RESET}")
        elif res["status"] == "already_solved":
            print_warning(f"Flag for {res['target']} ({res['type']}) was already submitted previously.")
        elif res["status"] == "expired":
            print_error("Exam session has expired.")
        else:
            print_error(f"Incorrect flag: {res.get('message', 'Flag not recognized.')}")
        return

    res = submit_flag(flag_str)
    if res["status"] == "success":
        print(f"\n{GREEN}{BOLD}╔══════════════════════════════════════════════════════════════════╗{RESET}")
        print(f"{GREEN}{BOLD}║                  [✓] FLAG ACCEPTED!                             ║{RESET}")
        print(f"{GREEN}{BOLD}╚══════════════════════════════════════════════════════════════════╝{RESET}")
        print(f"  Lab           : {CYAN}{res['title']}{RESET} ({res['lab']})")
        print(f"  Type          : {YELLOW}{res['type'].upper()} Flag{RESET}")
        print(f"  Points Awarded: {GREEN}+{res['points']} pts{RESET}")
        print(f"  Total Lab Score: {BOLD}{res['total_score']} pts{RESET}")
    elif res["status"] == "already_solved":
        print_warning(f"Flag for {res['title']} ({res['type']}) was already submitted at {res['solved_at']}.")
    else:
        print_error(f"Invalid flag submitted: {res['flag']}")

def handle_show_hint(lab_arg=None, tier=None):
    if not get_hints:
        print_error("Hint system module is unavailable.")
        return

    exam = load_exam_session() if load_exam_session else None
    if exam and exam.get("status") == "active":
        print_warning("OSCP Mock Exam is currently ACTIVE!")
        print_info("Hints and walkthroughs are disabled during exam conditions to maintain realistic test integrity.")
        confirm = input(f"{YELLOW}Do you wish to forfeit and stop the exam to view hints? (y/N): {RESET}").strip().lower()
        if confirm != 'y':
            return
        if stop_mock_exam: stop_mock_exam()
        print_info("Exam forfeited and stopped.")

    if not lab_arg:
        print_header("Progressive Multi-Tier Hint System")
        print("\nAvailable Labs for Hints:")
        for lab in labs_def:
            print(f"  [{lab['index']}] {lab['dir']} - {lab.get('title', '')}")
        try:
            choice = input(f"\nEnter lab number (1-{len(labs_def)}) or name: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nAborted.")
            return
        if not choice:
            return
        lab_arg = choice

    meta, hint_result = get_hints(lab_arg, tier=tier)
    if not meta:
        print_error(hint_result)
        return

    print(f"\n{BLUE}{BOLD}╭{'─' * 70}╮{RESET}")
    print(f"{BLUE}{BOLD}│{RESET} {BOLD}HINTS FOR LAB {meta['index']}: {meta['title']}{RESET}")
    print(f"{BLUE}{BOLD}╰{'─' * 70}╯{RESET}")

    if isinstance(hint_result, list):
        for h in hint_result:
            print(f"\n  {YELLOW}💡 {h}{RESET}")
        if len(hint_result) < len(meta["hints"]):
            print(f"\n  {DIM}Run 'adlabs hint {meta['index']}' again to unlock the next progressive hint tier.{RESET}")
    else:
        print(f"\n  {YELLOW}💡 {hint_result}{RESET}")

def handle_show_flags():
    if not load_flags_db:
        print_error("Flag system module is unavailable.")
        return

    db = load_flags_db()
    if not db:
        db = init_flags_for_all_labs()

    total_score = calculate_score(db)
    print_header("ADLabs Flag Progress & Scoreboard")
    print(f"\n  {BOLD}Total Points Earned: {GREEN}{total_score}{RESET} {BOLD}/ 450 pts{RESET}")
    print(f"\n  {BOLD}{'#':<3} {'Lab Name':<28} {'Local (10p)':<14} {'Proof (30/40p)':<16} {'Score'}{RESET}")
    print(f"  {DIM}{'─' * 70}{RESET}")

    for name, data in db.items():
        loc_st = f"{GREEN}[SOLVED]{RESET}" if data["local"]["solved"] else f"{DIM}[PENDING]{RESET}"
        prf_st = f"{GREEN}[SOLVED]{RESET}" if data["proof"]["solved"] else f"{DIM}[PENDING]{RESET}"
        pts = 0
        if data["local"]["solved"]: pts += data["local"]["points"]
        if data["proof"]["solved"]: pts += data["proof"]["points"]
        max_p = data["local"]["points"] + data["proof"]["points"]
        print(f"  {data['index']:<3} {name:<28} {loc_st:<23} {prf_st:<25} {pts}/{max_p}")

def handle_exam_command(sub_cmd=None, args=None):
    if not get_exam_status:
        print_error("Mock exam module is unavailable.")
        return

    if not sub_cmd or sub_cmd == "status":
        session, status = get_exam_status()
        if not session:
            print_info(status)
            print(f"\n  Start a new 24-hour mock exam with: {CYAN}python adlabs.py exam start{RESET}")
            return

        status_color = GREEN if session["status"] == "active" else RED
        print(f"\n{BLUE}{BOLD}╭{'─' * 72}╮{RESET}")
        print(f"{BLUE}{BOLD}│{RESET} {BOLD}OSCP 24-HOUR MOCK EXAM SESSION{RESET}  [{status_color}{session['status'].upper()}{RESET}]")
        print(f"{BLUE}{BOLD}│{RESET} Started: {session['started_at']}  |  Time Remaining: {YELLOW}{BOLD}{status['remaining_str']}{RESET}")
        print(f"{BLUE}{BOLD}│{RESET} Current Score: {YELLOW}{BOLD}{status['score']} / 100 pts{RESET} (Passing: 70 pts)")
        print(f"{BLUE}{BOLD}╰{'─' * 72}╯{RESET}")

        if status["passed"]:
            print(f"\n  {GREEN}{BOLD}🏆 PASSING SCORE ACHIEVED! ({status['score']}/100 PTS) 🏆{RESET}")

        print(f"\n  {BOLD}{'Code':<15} {'Role / Subnet':<40} {'Status':<15} {'Points'}{RESET}")
        print(f"  {DIM}{'─' * 75}{RESET}")
        for t in session["targets"]:
            local_st = f"{GREEN}LOCAL[✓]{RESET}" if t["local_solved"] else f"{DIM}LOCAL[-]{RESET}"
            proof_st = f"{GREEN}PROOF[✓]{RESET}" if t["proof_solved"] else f"{DIM}PROOF[-]{RESET}"
            st = f"{local_st} {proof_st}"
            print(f"  {BOLD}{t['code']:<15}{RESET} {t['role']:<40} {st:<25} {t['points_possible']} pts")
            print(f"    {DIM}Target IP: {t['local_ip']} (Enumerate via WireGuard){RESET}")

        print(f"\n  {CYAN}Commands:{RESET}")
        print(f"    • Submit flag : {BOLD}python adlabs.py submit <flag>{RESET}")
        print(f"    • Check status: {BOLD}python adlabs.py exam status{RESET}")
        print(f"    • Stop / Exit : {BOLD}python adlabs.py exam stop{RESET}")

    elif sub_cmd == "start":
        ok, res = start_mock_exam(duration_hours=24)
        if not ok:
            print_warning(res)
            return
        print_success("OSCP Mock Exam started successfully!")
        handle_exam_command("status")

    elif sub_cmd == "stop":
        confirm = input(f"{YELLOW}{BOLD}[!] Are you sure you want to stop/forfeit the exam session? (y/n): {RESET}").strip().lower()
        if confirm == 'y':
            ok, res = stop_mock_exam()
            if ok:
                print_success(f"Exam stopped. Final score: {res['current_score']} / 100 points.")
            else:
                print_error(res)

def show_banner(total_labs=None):
    if total_labs is None:
        total_labs = len(labs_def) if 'labs_def' in globals() else len([k for k in globals().get('labs_def', [])])
    current_host = get_host_ip()
    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), CONFIG_HOST_FILE)
    is_saved = os.path.exists(config_path)
    host_tag = f"{GREEN}{BOLD}{current_host}{RESET} {DIM}(Configured Static/DDNS){RESET}" if is_saved else f"{YELLOW}{BOLD}{current_host}{RESET} {DIM}(Auto-detected LAN - run --update-ip / --set-host for dynamic WAN){RESET}"
    banner = f"""{CYAN}{BOLD}
  ──────────────────────────────────────────────────────
   █████╗ ██████╗ ██╗      █████╗ ██████╗ ███████╗
  ██╔══██╗██╔══██╗██║     ██╔══██╗██╔══██╗██╔════╝
  ███████║██║  ██║██║     ███████║██████╔╝███████╗
  ██╔══██║██║  ██║██║     ██╔══██║██╔══██╗╚════██║
  ██║  ██║██████╔╝███████╗██║  ██║██████╔╝███████║
  ╚═╝  ╚═╝╚═════╝ ╚══════╝╚═╝  ╚═╝╚═════╝ ╚══════╝
{RESET}{BLUE}  Active Directory Pentesting Lab Suite Manager{RESET}  {DIM}{total_labs} labs · Docker + WireGuard{RESET}
  {DIM}Host / VPN Endpoint: {host_tag}
{CYAN} ──────────────────────────────────────────────────────{RESET}"""
    print(banner)


labs_def = [
    {
        "index": 1,
        "dir": "oscp-network-pivot-lab",
        "title": "OSCP Multi-Tier Network Pivot & Full Attack Loop",
        "scenario_focus": "Web Foothold, PrivEsc, Pivot & AD",
        "scenario": "External DMZ perimeter web portal (SQLi/File Upload) -> Local PrivEsc -> Internal DB & Redis -> AD Forest Child (HQ.MEGACORP.LOCAL) -> Forest Parent (MEGACORP.LOCAL).",
        "objective": "Retrieve DMZ local.txt (10 pts) -> root proof.txt (10 pts) -> Pivot to DB/AD -> elevate to Forest Parent DA proof.txt (40 pts).",
        "attack_chain": [
            "Perimeter Foothold: Access MegaCorp Portal at 10.10.10.80:80 -> exploit SQLi on login or upload PHP webshell via document drop -> obtain www-data shell (local.txt).",
            "Local Privilege Escalation: Exploit sudo find or writable /opt/internal_backup.py to escalate to root (root proof.txt).",
            "Internal Network Pivoting: Review /root/pivot_notes.txt -> establish SSH dynamic port forwarding or Chisel tunnel into 10.20.20.0/24 and 10.100.10.0/24.",
            "Database Credential Hunt: Connect to PostgreSQL (10.20.20.20:5432) -> query ad_sync_credentials table to extract AD bind accounts.",
            "Active Directory Forest Escalation: AS-REP Roasting / Kerberoasting on HQ DC -> exploit bidirectional forest trust to achieve Enterprise Admin on 10.100.10.10."
        ],
        "credentials": [
            ("Perimeter Web Portal", "HTTP at 10.10.10.80:80 (Vulnerable: SQLi / File Upload)"),
            ("Target Domains", "megacorp.local / hq.megacorp.local")
        ],
        "dcs": ["ad-forest-parent", "ad-forest-child"],
        "wg": [("wireguard_oscp", "oscp-pivot-lab.conf")],
        "wg_container": "oscp-wg-gateway",
        "dns_domains": ["megacorp.local", "hq.megacorp.local"],
        "dns_mappings": {"megacorp.local": "10.100.10.10", "hq.megacorp.local": "10.100.10.20"},
        "dns_networks": ["ad-forest-net"],
        "prov_fn": provision_lab1,
        "vpn_port": "51820/UDP",
        "vpn_profile": "oscp-pivot-lab.conf",
        "containers": ["perimeter-nginx-ui", "internal-postgres-db", "ad-forest-parent", "ad-forest-child"],
        "targets": [
            {"name": "Perimeter Web Portal (DMZ Foothold)", "ip": "10.10.10.80", "port": 80, "protocol": "TCP"},
            {"name": "Postgres Internal Database", "ip": "10.20.20.20", "port": 5432, "protocol": "TCP"},
            {"name": "Internal Redis Cache", "ip": "10.20.20.30", "port": 6379, "protocol": "TCP"},
            {"name": "Parent Domain Controller (MEGACORP.LOCAL)", "ip": "10.100.10.10", "port": 445, "protocol": "TCP"},
            {"name": "Child Domain Controller (HQ.MEGACORP.LOCAL)", "ip": "10.100.10.20", "port": 389, "protocol": "TCP"}
        ]
    },
    {
        "index": 2,
        "dir": "multi-domain-forest-lab",
        "title": "Multi-Domain Active Directory Forest Trust Lab",
        "scenario_focus": "Multi-Domain & Kerberoast",
        "scenario": "3-domain forest hierarchy (Parent MEGACORP.LOCAL, Child HQ.MEGACORP.LOCAL, Tree CYBERTECH.LOCAL). Cross-domain trust exploitation, Kerberoasting, and AS-REP roasting.",
        "objective": "Kerberoast SPNs across domains -> crack passwords -> exploit parent-child bidirectional trust to achieve Enterprise Admin.",
        "attack_chain": [
            "Child Domain Foothold: Authenticate with initial standard user j.doe in child domain hq.megacorp.local.",
            "Kerberoasting Service SPN: Enumerate SPNs -> request TGS for MSSQLSvc/sql-db.hq.megacorp.local:1433 -> crack hash using pass.txt.",
            "Child Domain Escalation: Service account has GenericWrite over svc_api -> abuse Shadow Credentials (msDS-KeyCredentialLink) to elevate.",
            "Cross-Forest Trust Abuse: Forge Golden Ticket with SID History (Parent Forest RID 500) -> achieve Enterprise Admin on Parent DC 10.101.10.10."
        ],
        "credentials": [
            ("Initial Child User", "j.doe:CorpSecurePass2026!1"),
            ("Child Domain DC", "10.101.20.10 (hq.megacorp.local)"),
            ("Parent Forest DC", "10.101.10.10 (megacorp.local)")
        ],
        "dcs": ["mega-dc-parent", "mega-dc-child", "mega-dc-tree"],
        "wg": [("wireguard_forest", "oscp-forest.conf")],
        "wg_container": "mega-wg-gateway",
        "dns_domains": ["megacorp.local", "hq.megacorp.local", "cybertech.local"],
        "dns_mappings": {"megacorp.local": "10.101.10.10", "hq.megacorp.local": "10.101.20.10", "cybertech.local": "10.101.30.10"},
        "dns_networks": ["parent-net", "child-net", "tree-net"],
        "prov_fn": provision_lab2,
        "vpn_port": "51821/UDP",
        "vpn_profile": "oscp-forest.conf",
        "containers": ["mega-dc-parent", "mega-dc-child", "mega-dc-tree"],
        "targets": [
            {"name": "Parent DC (MEGACORP.LOCAL)", "ip": "10.101.10.10", "port": 445, "protocol": "TCP"},
            {"name": "Child DC (HQ.MEGACORP.LOCAL)", "ip": "10.101.20.10", "port": 389, "protocol": "TCP"},
            {"name": "Tree DC (CYBERTECH.LOCAL)", "ip": "10.101.30.10", "port": 88, "protocol": "TCP"}
        ]
    },
    {
        "index": 3,
        "dir": "adcs-abuse-lab",
        "title": "Active Directory Certificate Services (ADCS) ESC1 Abuse",
        "scenario_focus": "ADCS ESC1 Abuse",
        "scenario": "Misconfigured certificate template with ENROLLEE_SUPPLIES_SUBJECT and Client Authentication EKU. Low-priv user requests certificate as Domain Admin.",
        "objective": "Request certificate for Administrator via Certipy/Certify -> authenticate via PKINIT to compromise Domain Controller.",
        "attack_chain": [
            "Domain Student Foothold: Authenticate as standard student user l3_j.doe:StudentPass2026! on ADCSTARGET.",
            "ADCS Template Enumeration: Query Certificate Templates -> identify template ESC1-WebServer allowing CT_FLAG_ENROLLEE_SUPPLIES_SUBJECT and Client Authentication.",
            "Certificate Request with SAN: Generate CSR on Web CA enrollment (10.102.20.20:80) requesting certificate with SAN of Administrator@ADCSLAB.LOCAL.",
            "PKINIT DC Authentication: Submit certificate to DC auth service at 10.102.10.10:8080/auth -> retrieve Domain Admin NTLM hash -> takeover DC 10.102.10.10."
        ],
        "credentials": [
            ("Domain Student User", "l3_j.doe:StudentPass2026!"),
            ("CA Web Enrollment", "http://10.102.20.20:80")
        ],
        "dcs": ["adcs-dc"],
        "wg": [("wireguard_adcs", "oscp-adcs-lab.conf")],
        "wg_container": "adcs-wg-gateway",
        "dns_domains": ["adcslab.local"],
        "dns_mappings": {"adcslab.local": "10.102.10.10"},
        "dns_networks": ["ad-net"],
        "prov_fn": provision_lab3,
        "vpn_port": "51822/UDP",
        "vpn_profile": "oscp-adcs-lab.conf",
        "containers": ["adcs-dc", "adcs-ca-mock"],
        "targets": [
            {"name": "Domain Controller (ADCSLAB.LOCAL)", "ip": "10.102.10.10", "port": 445, "protocol": "TCP"},
            {"name": "CA Mock Enrollment Web", "ip": "10.102.20.20", "port": 80, "protocol": "TCP"}
        ]
    },
    {
        "index": 4,
        "dir": "trust-pivoting-lab",
        "title": "Cross-Forest External Trust & SID History Pivoting",
        "scenario_focus": "Cross-Forest External Trust",
        "scenario": "Bidirectional external trust between Forest A (FORESTA.LOCAL) and Forest B (FORESTB.LOCAL). Exploit SID History injection and Foreign Security Principals.",
        "objective": "Abuse Forest B credentials -> forge SID History -> pivot across external trust to gain Domain Admin on Forest A.",
        "attack_chain": [
            "Forest B Foothold: Authenticate as standard student user l4b_student:SimpleStudentPass2026! in FORESTB.LOCAL.",
            "Trust Relationship Recon: Enumerate cross-forest external trust to FORESTA.LOCAL (10.103.10.10).",
            "Foreign Security Principal Abuse: Discover Foreign Security Principal membership of l4b_student inside Forest A group l4a_helpdesk.",
            "Management Server Pivot: Access WinRM administration server at 10.103.20.30:5985 -> extract Forest A administrative credentials -> compromise Forest A DC."
        ],
        "credentials": [
            ("Forest B Student", "FORESTB\\l4b_student:SimpleStudentPass2026!"),
            ("Forest B DC", "10.103.20.10 (forestb.local)"),
            ("Forest A DC", "10.103.10.10 (foresta.local)")
        ],
        "dcs": ["dc-foresta", "dc-forestb"],
        "wg": [("wireguard_trust", "oscp-trust-lab.conf")],
        "wg_container": "trust-wg-gateway",
        "dns_domains": ["foresta.local", "forestb.local"],
        "dns_mappings": {"foresta.local": "10.103.10.10", "forestb.local": "10.103.20.10"},
        "dns_networks": ["foresta-net", "forestb-net"],
        "prov_fn": provision_lab4,
        "vpn_port": "51823/UDP",
        "vpn_profile": "oscp-trust-lab.conf",
        "containers": ["dc-foresta", "dc-forestb", "trust-winrm-target"],
        "targets": [
            {"name": "Forest A DC (FORESTA.LOCAL)", "ip": "10.103.10.10", "port": 445, "protocol": "TCP"},
            {"name": "Forest B DC (FORESTB.LOCAL)", "ip": "10.103.20.10", "port": 389, "protocol": "TCP"},
            {"name": "WinRM Target Machine", "ip": "10.103.20.30", "port": 5985, "protocol": "TCP"}
        ]
    },
    {
        "index": 5,
        "dir": "gpo-admin-pivot-lab",
        "title": "Group Policy Object (GPO) Misconfiguration & Task Injection",
        "scenario_focus": "GPO Abuse & Task Injection",
        "scenario": "Vulnerable GPO write permissions (GenericWrite / WriteProperty). Domain joined client simulator ws-gpo-client$ with Kerberos keytab.",
        "objective": "Identify writable GPO -> modify GPO to deploy malicious scheduled task or immediate startup script -> achieve SYSTEM / DA.",
        "attack_chain": [
            "Operator Foothold: Authenticate as IT operator l5_operator:OperatorPass2026! on GPOLAB.LOCAL.",
            "GPO DACL Misconfiguration: Enumerate Group Policy Objects in SYSVOL / LDAP -> discover write permissions on Default Workstation Policy.",
            "Task / Script Injection: Inject immediate startup task into \\\\10.104.10.10\\sysvol\\gpolab.local\\scripts\\update.sh.",
            "Client Refresh & Elevation: Simulated workstation gpo-client-sim refreshes policy as SYSTEM -> dump cached credentials -> elevate to Domain Admin."
        ],
        "credentials": [
            ("Domain Operator", "l5_operator:OperatorPass2026!"),
            ("Client Workstation", "ws-gpo-client (gpo-client-sim)")
        ],
        "dcs": ["gpo-dc"],
        "wg": [("wireguard_gpo", "oscp-gpo-lab.conf")],
        "wg_container": "gpo-wg-gateway",
        "dns_domains": ["gpolab.local"],
        "dns_mappings": {"gpolab.local": "10.104.10.10"},
        "dns_networks": ["ad-net"],
        "prov_fn": provision_lab5,
        "vpn_port": "51824/UDP",
        "vpn_profile": "oscp-gpo-lab.conf",
        "containers": ["gpo-dc", "gpo-client-sim"],
        "targets": [
            {"name": "Domain Controller (GPOLAB.LOCAL)", "ip": "10.104.10.10", "port": 445, "protocol": "TCP"}
        ]
    },
    {
        "index": 6,
        "dir": "rbcd-lab",
        "title": "Resource-Based Constrained Delegation (RBCD) & Shadow Credentials",
        "scenario_focus": "RBCD & Shadow Credentials",
        "scenario": "GenericWrite on srv-target$ computer object or GenericAll over svc account. RBCD exploitation via S4U2self/S4U2proxy and AS-REP roastable account.",
        "objective": "Write msDS-AllowedToActOnBehalfOfOtherIdentity on srv-target$ -> S4U2self impersonation -> root shell via SSH.",
        "attack_chain": [
            "Unauthenticated Recon: Execute AS-REP Roasting against RBCDLAB.LOCAL for target l6_j.intern (Pre-authentication disabled).",
            "Offline Hash Cracking: Crack AS-REP hash with labs/rbcd-lab/pass.txt -> obtain password InternPass2026!.",
            "ACL BloodHound Pivot: l6_j.intern has GenericAll over service account l6_svc_web_rbcd -> reset password via RPC/LDAP.",
            "RBCD / Delegation Abuse: l6_svc_web_rbcd has GenericWrite on ws-corp$ -> configure msDS-AllowedToActOnBehalfOfOtherIdentity.",
            "S4U Ticket Forging: Execute S4U2Self and S4U2Proxy to impersonate Administrator -> gain root access on srv-target$."
        ],
        "credentials": [
            ("AS-REP Roast Target", "l6_j.intern (Pre-auth Disabled)"),
            ("Target Server SSH", "10.105.20.20:22")
        ],
        "dcs": ["rbcd-dc"],
        "wg": [("wireguard_rbcd", "oscp-rbcd-lab.conf")],
        "wg_container": "rbcd-wg-gateway",
        "dns_domains": ["rbcdlab.local"],
        "dns_mappings": {"rbcdlab.local": "10.105.10.10"},
        "dns_networks": ["ad-net"],
        "prov_fn": provision_lab6,
        "vpn_port": "51825/UDP",
        "vpn_profile": "oscp-rbcd-lab.conf",
        "containers": ["rbcd-dc", "rbcd-target-srv"],
        "targets": [
            {"name": "Domain Controller (RBCDLAB.LOCAL)", "ip": "10.105.10.10", "port": 445, "protocol": "TCP"},
            {"name": "RBCD Target Server SSH", "ip": "10.105.20.20", "port": 22, "protocol": "TCP"}
        ]
    },
    {
        "index": 7,
        "dir": "sql-pivot-lab",
        "title": "Database Link Pivoting & Network Segmentation Bypass",
        "scenario_focus": "SQL Database Link Pivot",
        "scenario": "Frontend PostgreSQL (sql-front at 10.106.20.20) has postgres_fdw foreign server link to network-isolated backend DB (sql-back at 10.106.10.20).",
        "objective": "Query remote foreign table 'remote_flag' via postgres_fdw link across isolated subnet to retrieve flag 'OSCP{sql_database_link_pivot_won}'.",
        "attack_chain": [
            "Database Foothold: Authenticate to frontend PostgreSQL database on 10.106.20.20:5432 using l7_db_operator:OperatorSecurePass2026!.",
            "Foreign Server Recon: Enumerate postgres_fdw foreign servers via pg_foreign_server -> identify link to isolated backend (10.106.10.20).",
            "Double-Hop Query Execution: Inspect foreign user mappings -> execute queries across the foreign server link to access backend tables.",
            "Flag Extraction: Query the remote foreign table remote_flag across the network boundary to capture the flag."
        ],
        "credentials": [
            ("Database Operator", "l7_db_operator:OperatorSecurePass2026!"),
            ("Frontend DB", "10.106.20.20:5432 (PostgreSQL)")
        ],
        "dcs": ["sql-dc"],
        "wg": [("wireguard_sql", "oscp-sql-lab.conf")],
        "wg_container": "sql-wg-gateway",
        "dns_domains": ["sqlpivot.local"],
        "dns_mappings": {"sqlpivot.local": "10.106.10.10"},
        "dns_networks": ["ad-net"],
        "prov_fn": provision_lab7,
        "vpn_port": "51826/UDP",
        "vpn_profile": "oscp-sql-lab.conf",
        "containers": ["sql-dc", "sql-front", "sql-back"],
        "targets": [
            {"name": "Domain Controller (SQLPIVOT.LOCAL)", "ip": "10.106.10.10", "port": 445, "protocol": "TCP"},
            {"name": "Frontend Database (PostgreSQL)", "ip": "10.106.20.20", "port": 5432, "protocol": "TCP"},
            {"name": "Backend Database (PostgreSQL)", "ip": "10.106.10.20", "port": 5432, "protocol": "TCP"}
        ]
    },
    {
        "index": 8,
        "dir": "laps-lab",
        "title": "LAPS Attribute Abuse & Kerberos Pass-the-Ticket",
        "scenario_focus": "LAPS Abuse & Pass-the-Ticket",
        "scenario": "Read ms-Mcs-AdmPwd / info LAPS password attributes or leverage exported Kerberos ticket cache to access finance server.",
        "objective": "Use KRB5CCNAME with exported ccache or query LAPS attributes to authenticate as local admin to finance server.",
        "attack_chain": [
            "Audit Account Foothold: Authenticate as l8_audit_user:AuditPass2026! on LAPSLAB.LOCAL.",
            "LAPS Attribute Enumeration: User has delegated ReadProperty on computer objects -> query LDAP attributes (description / info) on srv-finance$.",
            "Finance Server Shell: Extract local administrator password -> SSH into finance server at 10.107.20.20:22.",
            "Pass-the-Ticket / gMSA Theft: Extract cached Domain Admin Kerberos ticket (ccache) or gMSA l8_gmsa_svc$ -> export KRB5CCNAME -> compromise DC 10.107.10.10."
        ],
        "credentials": [
            ("Audit User (AS-REP)", "l8_audit_user:AuditPass2026!"),
            ("Finance Server SSH", "10.107.20.20:22")
        ],
        "dcs": ["laps-dc"],
        "wg": [("wireguard_laps", "oscp-laps-lab.conf")],
        "wg_container": "laps-wg-gateway",
        "dns_domains": ["lapslab.local"],
        "dns_mappings": {"lapslab.local": "10.107.10.10"},
        "dns_networks": ["ad-net"],
        "prov_fn": provision_lab8,
        "vpn_port": "51827/UDP",
        "vpn_profile": "oscp-laps-lab.conf",
        "containers": ["laps-dc", "laps-finance-srv"],
        "targets": [
            {"name": "Domain Controller (LAPSLAB.LOCAL)", "ip": "10.107.10.10", "port": 445, "protocol": "TCP"},
            {"name": "LAPS Target Server SSH", "ip": "10.107.20.20", "port": 22, "protocol": "TCP"}
        ]
    },
    {
        "index": 9,
        "dir": "esc8-relay-lab",
        "title": "ADCS ESC8: NTLM Relay to HTTP Certificate Enrollment",
        "scenario_focus": "ADCS ESC8 NTLM Relay",
        "scenario": "ADCS Web Enrollment (/certsrv/) without EPA/SMB signing. Coerce DC authentication via PetitPotam -> relay HTTP to CA -> enroll DC cert -> DCSync.",
        "objective": "Coerce authentication from esc8-dc -> relay NTLM to esc8-ca-web -> receive DC machine certificate -> perform DCSync via secretsdump.",
        "attack_chain": [
            "Student Foothold: Authenticate as standard student user l9_student:StudentPass2026! in ESC8LAB.LOCAL.",
            "ADCS HTTP Web Enrollment Recon: Discover unencrypted HTTP enrollment endpoint at http://10.108.20.20:80/certsrv/ (EPA Disabled).",
            "Coercion Attack: Trigger machine authentication from esc8-dc (10.108.10.10) via PetitPotam / PrinterBug coerce trigger.",
            "NTLM Relay to HTTP: Relay coerced machine authentication to CA web endpoint -> enroll certificate on behalf of esc8-dc$.",
            "Machine Certificate DCSync: Use esc8-dc$ machine certificate with PKINIT / secretsdump to DCSync Domain Admin hash."
        ],
        "credentials": [
            ("Student User", "l9_student:StudentPass2026!"),
            ("CA Web Enrollment", "http://10.108.20.20:80/certsrv/")
        ],
        "dcs": ["esc8-dc"],
        "wg": [("wireguard_esc8", "oscp-esc8-lab.conf")],
        "wg_container": "esc8-wg-gateway",
        "dns_domains": ["esc8lab.local"],
        "dns_mappings": {"esc8lab.local": "10.108.10.10"},
        "dns_networks": ["ad-net"],
        "prov_fn": provision_lab9,
        "vpn_port": "51828/UDP",
        "vpn_profile": "oscp-esc8-lab.conf",
        "containers": ["esc8-dc", "esc8-ca-web"],
        "targets": [
            {"name": "Domain Controller (ESC8LAB.LOCAL)", "ip": "10.108.10.10", "port": 445, "protocol": "TCP"},
            {"name": "Web CA ADCS Enrollment", "ip": "10.108.20.20", "port": 80, "protocol": "TCP"}
        ]
    },
    {
        "index": 10,
        "dir": "delegation-s4u-lab",
        "title": "Kerberos Constrained Delegation (S4U2Self & S4U2Proxy)",
        "scenario_focus": "Constrained Delegation S4U",
        "scenario": "Service account with msDS-AllowedToDelegateTo configured with protocol transition. Impersonate Domain Admin to backend database server.",
        "objective": "Request TGT for service account -> execute S4U2Self to get ticket as Administrator -> S4U2Proxy to access backend services.",
        "attack_chain": [
            "Student Foothold: Authenticate as l10_j.student:StudentPass2026! on DELEGATELAB.LOCAL.",
            "ACL Reconnaissance: Enumerate object permissions -> discover GenericWrite on service target l10_db_service or AS-REP roastable l10_svc_backup_deleg.",
            "Kerberos S4U Enumeration: Discover msDS-AllowedToDelegateTo configured on l10_web_service with protocol transition enabled.",
            "S4U2Self Kerberos Ticket Request: Request Kerberos TGT -> issue S4U2Self request to forge a Service Ticket impersonating Administrator.",
            "S4U2Proxy Delegation & Compromise: Exchange S4U2Self ticket via S4U2Proxy for CIFS/MSSQL service ticket -> authenticate as Domain Admin to 10.109.20.20."
        ],
        "foothold": "Target Database Server SSH at 10.109.20.20:22 + Domain Controller at 10.109.10.10:445.",
        "credentials": [
            ("Student Account", "l10_j.student:StudentPass2026!"),
            ("Target Database SSH", "10.109.20.20:22")
        ],
        "dcs": ["deleg-dc"],
        "wg": [("wireguard_deleg", "oscp-deleg.conf")],
        "wg_container": "deleg-wg-gateway",
        "dns_domains": ["delegatelab.local"],
        "dns_mappings": {"delegatelab.local": "10.109.10.10"},
        "dns_networks": ["ad-net"],
        "prov_fn": provision_lab10,
        "vpn_port": "51829/UDP",
        "vpn_profile": "oscp-deleg.conf",
        "containers": ["deleg-dc", "deleg-db"],
        "targets": [
            {"name": "Domain Controller (DELEGATELAB.LOCAL)", "ip": "10.109.10.10", "port": 445, "protocol": "TCP"},
            {"name": "Database Server SSH", "ip": "10.109.20.20", "port": 22, "protocol": "TCP"}
        ]
    },
    {
        "index": 11,
        "dir": "hybrid-cloud-aad-lab",
        "title": "Hybrid Cloud Identity & Azure AD Connect Sync Abuse",
        "scenario_focus": "Azure AD Connect & DCSync",
        "scenario": "Enterprise Hybrid Cloud network with On-Premises AD (MEGACORP-CLOUD.LOCAL) synchronized to Microsoft Entra ID via Azure AD Connect Sync Server. Foothold on HelpDesk account -> BloodHound ACL abuse on DevOps -> Sync Server LocalDB credential extraction -> DCSync domain takeover.",
        "objective": "Enumerate ACLs -> reset devops_admin password -> SSH into hybrid-sync-srv -> decrypt LocalDB MSOL_ credentials -> perform DCSync on Domain Controller -> capture flag.",
        "attack_chain": [
            "HelpDesk Intern Foothold: Authenticate as l11_t.intern:InternPass2026! on MEGACORP-CLOUD.LOCAL.",
            "BloodHound / ACL Analysis: Discover HelpDesk-Tier1 has GenericAll over devops_admin and DevOps-Admins group.",
            "Identity Abuse & Lateral Movement: Abuse GenericAll to reset devops_admin password via RPC/SMB (e.g. net rpc / samba-tool) -> SSH into sync server (10.110.20.20:22) with new password.",
            "LocalDB Credential Extraction: On hybrid-sync-srv, run decryption tool on /opt/aadconnect/ADSync.db using DPAPI/entropy key to recover MSOL_a1b2c3d4e5f6 cleartext password.",
            "DCSync Domain Takeover: MSOL account has Replicating Directory Changes -> execute DCSync against DC 10.110.10.10 to dump Administrator NTLM hash and access \\\\10.110.10.10\\sysvol flag."
        ],
        "foothold": "HelpDesk intern credentials l11_t.intern:InternPass2026! + Web dashboard at 10.110.20.20:80 / SSH at 10.110.20.20:22.",
        "credentials": [
            ("HelpDesk Intern", "l11_t.intern:InternPass2026!"),
            ("Target Entra Connect Sync", "10.110.20.20:22 (SSH) / 10.110.20.20:80 (Web)")
        ],
        "dcs": ["hybrid-dc"],
        "wg": [("wireguard_hybrid", "oscp-hybrid.conf")],
        "wg_container": "hybrid-wg-gateway",
        "dns_domains": ["megacorp-cloud.local"],
        "dns_mappings": {"megacorp-cloud.local": "10.110.10.10"},
        "dns_networks": ["ad-net", "sync-net"],
        "prov_fn": provision_lab11,
        "vpn_port": "51830/UDP",
        "vpn_profile": "oscp-hybrid.conf",
        "containers": ["hybrid-dc", "hybrid-sync-srv", "hybrid-wg-gateway", "hybrid-core-router"],
        "targets": [
            {"name": "Domain Controller (MEGACORP-CLOUD.LOCAL)", "ip": "10.110.10.10", "port": 445, "protocol": "TCP"},
            {"name": "Domain Controller Kerberos", "ip": "10.110.10.10", "port": 88, "protocol": "TCP"},
            {"name": "Entra Connect Sync Web Manager", "ip": "10.110.20.20", "port": 80, "protocol": "TCP"},
            {"name": "Entra Connect Sync SSH", "ip": "10.110.20.20", "port": 22, "protocol": "TCP"}
        ]
    },
    {
        "index": 12,
        "dir": "sccm-mecm-pivot-lab",
        "title": "Lab 12: SCCM/MECM Site Server Abuse & Multi-Tier Network Pivot",
        "scenario_focus": "SCCM NAA, Client Push & Network Pivoting",
        "scenario": "SCCM Network Access Account (NAA) credential extraction from SMB distribution share, site server compromise, dynamic SSH SOCKS network pivoting across segmented firewalls, and Client Push installation account abuse for Domain escalation.",
        "objective": "Enumerate SCCM distribution share -> extract NAA credentials from TSConfig.xml -> gain foothold on sccm-site-srv -> pivot through firewall drop rules to reach Domain Controller -> extract Client Push credentials -> perform DCSync to elevate to Domain Admin and capture flag.",
        "attack_chain": [
            "HelpDesk Intern Foothold: Authenticate as l12_j.intern:InternPass2026! on CORP-MANAGEMENT.LOCAL.",
            "Distribution Point Share Recon: Connect to SMB share SMSPKGD$ at 10.112.20.20 -> inspect task sequence TSConfig.xml -> extract encrypted/obfuscated NAA credentials.",
            "NAA Credential Decrypt & Host Access: Decrypt Network Access Account (sccm_naa) -> SSH into sccm-site-srv (10.112.20.20:22).",
            "Firewall SOCKS Pivoting: Domain Controller (10.112.10.10) is protected by router firewall drop rules -> establish dynamic SSH SOCKS proxy (-D 1080) through sccm-site-srv.",
            "Client Push Abuse & DCSync: Through proxy, extract Client Push Installation account or coerce/relay SCCM site server to dump DC credentials and capture flag."
        ],
        "foothold": "HelpDesk intern credentials l12_j.intern:InternPass2026! + Distribution Point SMB at 10.112.20.20:445 / Web status at 10.112.20.20:80 / SSH at 10.112.20.20:22.",
        "credentials": [
            ("HelpDesk Intern", "l12_j.intern:InternPass2026!"),
            ("Distribution Point SMB", "10.112.20.20:445 (SMSPKGD$)"),
            ("SCCM Site Server SSH", "10.112.20.20:22")
        ],
        "dcs": ["sccm-dc"],
        "wg": [("wireguard_sccm", "oscp-sccm-lab.conf")],
        "wg_container": "sccm-wg-gateway",
        "dns_domains": ["corp-management.local"],
        "dns_mappings": {"corp-management.local": "10.112.10.10"},
        "dns_networks": ["mgmt-net"],
        "prov_fn": provision_lab12,
        "vpn_port": "51831/UDP",
        "vpn_profile": "oscp-sccm-lab.conf",
        "containers": ["sccm-dc", "sccm-site-srv", "sccm-wg-gateway", "sccm-core-router"],
        "targets": [
            {"name": "Domain Controller (CORP-MANAGEMENT.LOCAL)", "ip": "10.112.10.10", "port": 445, "protocol": "TCP"},
            {"name": "Domain Controller Kerberos", "ip": "10.112.10.10", "port": 88, "protocol": "TCP"},
            {"name": "SCCM Distribution Point SMB (SMSPKGD$)", "ip": "10.112.20.20", "port": 445, "protocol": "TCP"},
            {"name": "MECM Management Point Web Portal", "ip": "10.112.20.20", "port": 80, "protocol": "TCP"},
            {"name": "SCCM Site Server SSH (Pivot Host)", "ip": "10.112.20.20", "port": 22, "protocol": "TCP"}
        ]
    }
]

TOTAL_LABS = len(labs_def)


def action_deploy_all(base_dir, script_path, labs_def):
    """Deploys and provisions all labs in sequence."""
    results = []
    ready = []
    try:
        for lab in labs_def:
            ok = deploy_lab(lab, base_dir, script_path, labs_def, stop_others=False, spawn_daemon=False)
            results.append((f"Lab {lab['index']} {lab['dir']}", "READY" if ok else "FAILED"))
            if ok:
                ready.append(lab)
    except KeyboardInterrupt:
        print_warning("Interrupted by user. Showing partial results...")
    for lab in ready:
        start_timeout_daemon(lab, base_dir)
    print_summary_box("DEPLOY ALL FINISHED", results)
    return ready

def action_deploy_single(target, base_dir, script_path, labs_def):
    """Deploys a single lab by index or directory name."""
    matched = find_lab(labs_def, target)
    if matched:
        return deploy_lab(matched, base_dir, script_path, labs_def, stop_others=False)
    print_error(f"Lab '{target}' not found.")
    return False

def action_stop_all(base_dir, labs_def):
    """Stops all active labs."""
    for lab in labs_def:
        stop_lab(lab, base_dir)

def action_stop_single(target, base_dir, labs_def):
    """Stops a single lab by index or directory name."""
    matched = find_lab(labs_def, target)
    if matched:
        stop_lab(matched, base_dir)
        return True
    print_error(f"Lab '{target}' not found.")
    return False

def action_clean_all(base_dir, labs_def):
    """Stops and removes volumes for all labs."""
    for lab in labs_def:
        clean_lab(lab, base_dir)

def action_clean_single(target, base_dir, labs_def):
    """Stops and removes volumes for a single lab."""
    matched = find_lab(labs_def, target)
    if matched:
        clean_lab(matched, base_dir)
        return True
    print_error(f"Lab '{target}' not found.")
    return False

def action_test_all(labs_def):
    """Tests connectivity and service status for all labs."""
    for lab in labs_def:
        test_lab_connectivity(lab)

def action_test_single(target, labs_def):
    """Tests connectivity and service status for a single lab."""
    matched = find_lab(labs_def, target)
    if matched:
        test_lab_connectivity(matched)
        return True
    print_error(f"Lab '{target}' not found.")
    return False

def action_show_info(target, base_dir, labs_def):
    """Displays detailed configuration, credentials, and targets for labs."""
    if not target or target.lower() == 'all' or target == '0':
        for lab in labs_def:
            show_lab_info(lab, base_dir)
    else:
        matched = find_lab(labs_def, target)
        if matched:
            show_lab_info(matched, base_dir)
        else:
            print_error(f"Lab '{target}' not found.")

def action_gen_vpn(target, base_dir, labs_def):
    """Generates WireGuard VPN configuration profiles."""
    if not target or target.lower() == 'all' or target == '0':
        for lab in labs_def:
            generate_vpn_profile(lab, base_dir)
    else:
        matched = find_lab(labs_def, target)
        if matched:
            generate_vpn_profile(matched, base_dir)
        else:
            print_error(f"Lab '{target}' not found.")

def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(base_dir)
    script_path = os.path.join(base_dir, "core", "configure_ad.py")

    # Subcommand dispatch support (e.g. adlabs connect 1, adlabs submit OSCP{...}, adlabs hint 1, adlabs exam start, adlabs flags)
    if len(sys.argv) > 1 and not sys.argv[1].startswith("-"):
        subcmd = sys.argv[1].lower()
        subargs = sys.argv[2:]
        subarg1 = subargs[0] if subargs else None

        if subcmd == "connect":
            show_banner()
            handle_connect_command(subarg1, base_dir)
            return
        elif subcmd == "disconnect":
            show_banner()
            handle_disconnect_command(subarg1, base_dir)
            return
        elif subcmd == "submit":
            show_banner()
            if not subarg1:
                print_error("Please specify a flag string: adlabs submit <flag>")
                return
            handle_submit_flag(subarg1)
            return
        elif subcmd == "hint":
            show_banner()
            tier_arg = None
            if len(subargs) > 1 and subargs[1].isdigit():
                tier_arg = int(subargs[1])
            handle_show_hint(subarg1, tier=tier_arg)
            return
        elif subcmd in ("flags", "scoreboard", "score"):
            show_banner()
            handle_show_flags()
            return
        elif subcmd in ("exam", "mock-exam"):
            show_banner()
            action = subarg1 if subarg1 else "status"
            handle_exam_command(action, subargs)
            return
        elif subcmd in ("status", "ps"):
            show_banner()
            show_all_labs_summary(labs_def, base_dir)
            return
        elif subcmd == "info":
            show_banner()
            target = subarg1 if subarg1 else "all"
            if target.lower() == 'all':
                for lab in labs_def:
                    show_lab_info(lab, base_dir)
            else:
                matched = find_lab(labs_def, target)
                if matched:
                    show_lab_info(matched, base_dir)
                else:
                    print_error(f"Lab '{target}' not found.")
            return
        elif subcmd in ("deploy", "start", "up"):
            if subarg1:
                if subarg1.lower() == "all":
                    sys.argv = [sys.argv[0], "--all"]
                else:
                    sys.argv = [sys.argv[0], "--lab", subarg1]
            else:
                print_error("Please specify lab name or index: adlabs deploy <lab|all>")
                return
        elif subcmd in ("stop", "down"):
            if subarg1:
                if subarg1.lower() == "all":
                    sys.argv = [sys.argv[0], "--stop-all"]
                else:
                    sys.argv = [sys.argv[0], "--stop", subarg1]
            else:
                print_error("Please specify lab name or index: adlabs stop <lab|all>")
                return
        elif subcmd == "clean":
            if subarg1:
                if subarg1.lower() == "all":
                    sys.argv = [sys.argv[0], "--clean-all"]
                else:
                    sys.argv = [sys.argv[0], "--clean", subarg1]
            else:
                print_error("Please specify lab name or index: adlabs clean <lab|all>")
                return
        elif subcmd == "test":
            if subarg1:
                if subarg1.lower() == "all":
                    sys.argv = [sys.argv[0], "--test-all"]
                else:
                    sys.argv = [sys.argv[0], "--test", subarg1]
            else:
                sys.argv = [sys.argv[0], "--test-all"]
        elif subcmd in ("wordlists", "gen-wordlists"):
            show_banner()
            randomize = ("--randomize" in subargs or "-r" in subargs)
            from core.generate_wordlists import generate_all_wordlists
            generate_all_wordlists(base_dir, randomize=randomize)
            return

    parser = argparse.ArgumentParser(description=f"Manage AD Labs ({TOTAL_LABS} scenarios) setup, provisioning, and connectivity.")
    parser.add_argument("--all", "-a", action="store_true", help=f"Start and provision all {TOTAL_LABS} labs")
    parser.add_argument("--lab", "-l", type=str, help=f"Start and provision a specific lab (by name or 1-{TOTAL_LABS} index)")
    parser.add_argument("--status", "-s", action="store_true", help=f"Show live status summary overview of all {TOTAL_LABS} labs")
    parser.add_argument("--info", "-i", type=str, help=f"Show detailed info, credentials, and targets for a lab (1-{TOTAL_LABS}, name, or 'all')")
    parser.add_argument("--stop-all", action="store_true", help="Stop all labs")
    parser.add_argument("--stop", type=str, help=f"Stop a specific lab (by name or 1-{TOTAL_LABS} index)")
    parser.add_argument("--clean-all", action="store_true", help="Stop and remove volumes for all labs")
    parser.add_argument("--clean", type=str, help="Stop and remove volumes for a specific lab")
    parser.add_argument("--test-all", action="store_true", help="Test connectivity & status of all labs")
    parser.add_argument("--test", type=str, help="Test connectivity & status of a specific lab (by name or index)")
    parser.add_argument("--connect", "-c", type=str, help=f"Connect WireGuard VPN tunnel for a lab (by name or 1-{TOTAL_LABS} index)")
    parser.add_argument("--disconnect", "-d", type=str, help=f"Disconnect WireGuard VPN tunnel for a lab (by name or 1-{TOTAL_LABS} index)")
    parser.add_argument("--generate-wordlists", action="store_true", help="Generate / Recreate users.txt and pass.txt wordlists for all labs")
    parser.add_argument("--submit", type=str, help="Submit a captured flag (local.txt or proof.txt)")
    parser.add_argument("--hint", type=str, help="Request progressive hint for a lab (1-12 or name)")
    parser.add_argument("--flags", action="store_true", help="Show flag progress and score breakdown")
    parser.add_argument("--exam", type=str, nargs="?", const="status", help="OSCP Mock Exam simulator (start, status, stop)")
    parser.add_argument("--randomize", "-r", action="store_true", help="Randomize credentials when generating wordlists")
    parser.add_argument("--gen-vpn", type=str, help="Generate / Regenerate VPN profiles for a lab (or 'all' / index / name)")
    parser.add_argument("--set-host", type=str, help="Set persistent Host IP or DDNS Domain (e.g. '203.0.113.1' or 'myvpn.duckdns.org') and update all profiles")
    parser.add_argument("--update-ip", action="store_true", help="Auto-detect current public/local IP and update all deployed labs")
    parser.add_argument("--host", type=str, help="Override Host IP/Domain for the current command")
    parser.add_argument("--list-labs", action="store_true", help="Print available labs list cleanly")
    parser.add_argument("--count-labs", action="store_true", help="Print total lab count")

    args = parser.parse_args()

    if args.host:
        global ACTIVE_HOST_OVERRIDE
        ACTIVE_HOST_OVERRIDE = args.host.strip()

    if args.count_labs:
        print(TOTAL_LABS)
        return

    if args.list_labs:
        for lab in labs_def:
            print(f"[{lab['index']:>2}] {lab['dir']:<28} - {lab.get('title', '')}")
        return

    has_args = any([
        args.all, args.lab, args.stop_all, args.stop,
        args.clean_all, args.clean, args.test_all, args.test,
        args.connect, args.disconnect,
        args.generate_wordlists, args.gen_vpn,
        args.status, args.info,
        args.set_host, args.update_ip,
        args.submit, args.hint, args.flags, args.exam
    ])

    if has_args:
        show_banner()
        mutating = args.all or args.lab or args.stop_all or args.stop or args.clean_all or args.clean or args.generate_wordlists or args.gen_vpn or args.set_host or args.update_ip
        if mutating:
            if not acquire_deploy_lock(base_dir):
                sys.exit(1)
            atexit.register(release_deploy_lock, base_dir)
        if args.submit:
            handle_submit_flag(args.submit)
            return
        elif args.hint:
            handle_show_hint(args.hint)
            return
        elif args.flags:
            handle_show_flags()
            return
        elif args.exam:
            handle_exam_command(args.exam)
            return
        elif args.set_host:
            set_persistent_host(args.set_host, base_dir, labs_def)
            return
        elif args.update_ip:
            auto_update_ip(base_dir, labs_def)
            return
        elif args.all:
            action_deploy_all(base_dir, script_path, labs_def)
        elif args.lab:
            if not action_deploy_single(args.lab.strip(), base_dir, script_path, labs_def):
                sys.exit(1)
        elif args.status:
            show_all_labs_summary(labs_def, base_dir)
        elif args.info:
            action_show_info(args.info.strip(), base_dir, labs_def)
        elif args.connect:
            handle_connect_command(args.connect.strip(), base_dir)
        elif args.disconnect:
            handle_disconnect_command(args.disconnect.strip(), base_dir)
        elif args.stop_all:
            action_stop_all(base_dir, labs_def)
        elif args.stop:
            if not action_stop_single(args.stop.strip(), base_dir, labs_def):
                sys.exit(1)
        elif args.clean_all:
            action_clean_all(base_dir, labs_def)
        elif args.clean:
            if not action_clean_single(args.clean.strip(), base_dir, labs_def):
                sys.exit(1)
        elif args.test_all:
            action_test_all(labs_def)
        elif args.test:
            if not action_test_single(args.test.strip(), labs_def):
                sys.exit(1)
        elif args.generate_wordlists:
            run_wordlist_generation(base_dir, randomize=args.randomize)
        elif args.gen_vpn:
            action_gen_vpn(args.gen_vpn.strip(), base_dir, labs_def)
        return


    if not acquire_deploy_lock(base_dir):
        sys.exit(1)
    atexit.register(release_deploy_lock, base_dir)
    while True:
        show_banner()
        print(f"  {BOLD}[1]{RESET}  Deploy & Provision {BOLD}ALL{RESET} {TOTAL_LABS} labs {YELLOW}(Warning: Resource Intensive){RESET}")
        print(f"  {BOLD}[2]{RESET}  Select a specific lab to Deploy & Provision")
        print(f"  {BOLD}[3]{RESET}  Stop {BOLD}ALL{RESET} active labs")
        print(f"  {BOLD}[4]{RESET}  Stop a specific active lab")
        print(f"  {BOLD}[5]{RESET}  Clean {BOLD}ALL{RESET} labs (Stop & Remove local docker volumes)")
        print(f"  {BOLD}[6]{RESET}  Clean a specific lab (Stop & Remove volumes)")
        print(f"  {BOLD}[7]{RESET}  Show Live Status Overview of {BOLD}ALL{RESET} labs")
        print(f"  {BOLD}[8]{RESET}  Show Detailed Info & Credentials for a specific lab")
        print(f"  {BOLD}[9]{RESET}  Test Connectivity of {BOLD}ALL{RESET} labs")
        print(f"  {BOLD}[10]{RESET} Test Connectivity of a specific lab")
        print(f"  {BOLD}[11]{RESET} Generate / Recreate wordlists (users.txt & pass.txt) for all labs")
        print(f"  {BOLD}[12]{RESET} Generate / Regenerate VPN profiles (Update Host IP)")
        print(f"  {BOLD}[13]{RESET} Dynamic IP & Server Host Setup (Auto-Detect WAN / Set DDNS Domain)")
        print(f"  {BOLD}[14]{RESET} Connect WireGuard VPN tunnel for a lab (Cross-Platform)")
        print(f"  {BOLD}[15]{RESET} Disconnect WireGuard VPN tunnel for a lab")
        print(f"  {BOLD}[16]{RESET} Submit Flag (local.txt or proof.txt)")
        print(f"  {BOLD}[17]{RESET} Request Progressive Hint for a Lab (Tier 1-4)")
        print(f"  {BOLD}[18]{RESET} Show Flag Scoreboard & Solved Challenges")
        print(f"  {BOLD}[19]{RESET} OSCP Mock Exam Simulator (24-Hour Blind Challenge)")
        print(f"  {BOLD}[20]{RESET} Exit")
        print(f"{CYAN} ──────────────────────────────────────────────────────{RESET}")

        choice = input(f"{BOLD}Enter choice (1-20): {RESET}").strip()

        if choice == "1":
            confirm = input(f"{YELLOW}{BOLD}[!] Are you sure you want to run all {TOTAL_LABS} labs? This requires significant RAM. (y/n): {RESET}").strip().lower()
            if confirm == 'y':
                action_deploy_all(base_dir, script_path, labs_def)
        elif choice == "2":
            print(f"\n{BOLD}{CYAN}--- Available Labs ---{RESET}")
            for lab in labs_def:
                print(f"  {BOLD}{lab['index']}){RESET} {lab['dir']}")
            lab_choice = input(f"\n{BOLD}Enter lab index (1-{len(labs_def)}): {RESET}").strip()
            action_deploy_single(lab_choice, base_dir, script_path, labs_def)
            input(f"\nPress Enter to return to main menu...")
        elif choice == "3":
            confirm = input(f"{YELLOW}{BOLD}[!] Are you sure you want to stop all labs? (y/n): {RESET}").strip().lower()
            if confirm == 'y':
                action_stop_all(base_dir, labs_def)
            input(f"\nPress Enter to return to main menu...")
        elif choice == "4":
            print(f"\n{BOLD}{CYAN}--- Active Labs ---{RESET}")
            for lab in labs_def:
                print(f"  {BOLD}{lab['index']}){RESET} {lab['dir']}")
            lab_choice = input(f"\n{BOLD}Enter lab index to stop (1-{len(labs_def)}): {RESET}").strip()
            action_stop_single(lab_choice, base_dir, labs_def)
            input(f"\nPress Enter to return to main menu...")
        elif choice == "5":
            confirm = input(f"{RED}{BOLD}[!] WARNING: This will destroy all databases and AD states for all labs. Proceed? (y/n): {RESET}").strip().lower()
            if confirm == 'y':
                action_clean_all(base_dir, labs_def)
            input(f"\nPress Enter to return to main menu...")
        elif choice == "6":
            print(f"\n{BOLD}{CYAN}--- Available Labs ---{RESET}")
            for lab in labs_def:
                print(f"  {BOLD}{lab['index']}){RESET} {lab['dir']}")
            lab_choice = input(f"\n{BOLD}Enter lab index to clean (1-{len(labs_def)}): {RESET}").strip()
            action_clean_single(lab_choice, base_dir, labs_def)
            input(f"\nPress Enter to return to main menu...")
        elif choice == "7":
            show_all_labs_summary(labs_def, base_dir)
            input(f"\nPress Enter to return to main menu...")
        elif choice == "8":
            print(f"\n{BOLD}{CYAN}--- Available Labs ---{RESET}")
            print(f"  {BOLD}0){RESET} ALL Labs")
            for lab in labs_def:
                print(f"  {BOLD}{lab['index']}){RESET} {lab['dir']}")
            lab_choice = input(f"\n{BOLD}Enter lab index for detailed info (0-{len(labs_def)}): {RESET}").strip()
            action_show_info(lab_choice, base_dir, labs_def)
            input(f"\nPress Enter to return to main menu...")
        elif choice == "9":
            action_test_all(labs_def)
            input(f"\nPress Enter to return to main menu...")
        elif choice == "10":
            print(f"\n{BOLD}{CYAN}--- Available Labs ---{RESET}")
            for lab in labs_def:
                print(f"  {BOLD}{lab['index']}){RESET} {lab['dir']}")
            lab_choice = input(f"\n{BOLD}Enter lab index to test (1-{len(labs_def)}): {RESET}").strip()
            action_test_single(lab_choice, labs_def)
            input(f"\nPress Enter to return to main menu...")
        elif choice == "11":
            run_wordlist_generation(base_dir)
            input(f"\nPress Enter to return to main menu...")
        elif choice == "12":
            print(f"\n{BOLD}{CYAN}--- Available Labs ---{RESET}")
            print(f"  {BOLD}0){RESET} ALL Labs")
            for lab in labs_def:
                print(f"  {BOLD}{lab['index']}){RESET} {lab['dir']}")
            lab_choice = input(f"\n{BOLD}Enter lab index to generate VPN for (0-{len(labs_def)}): {RESET}").strip()
            action_gen_vpn(lab_choice, base_dir, labs_def)
            input(f"\nPress Enter to return to main menu...")
        elif choice == "13":
            print(f"\n{BOLD}{CYAN}--- Dynamic IP & Server Host Configuration ---{RESET}")
            print(f"  Current Configured Host: {BOLD}{get_host_ip()}{RESET}")
            print(f"  {BOLD}[1]{RESET} Auto-detect Public / WAN IP (via api.ipify.org)")
            print(f"  {BOLD}[2]{RESET} Auto-detect Local LAN Interface IP")
            print(f"  {BOLD}[3]{RESET} Set Custom Static IP or DDNS Domain (e.g. 'mylab.duckdns.org')")
            print(f"  {BOLD}[4]{RESET} Reset to Default LAN auto-detection")
            print(f"  {BOLD}[5]{RESET} Return to main menu")
            sub_c = input(f"\n{BOLD}Enter choice (1-5): {RESET}").strip()
            if sub_c == "1":
                auto_update_ip(base_dir, labs_def)
            elif sub_c == "2":
                local_ip = get_host_ip(override="").strip()
                set_persistent_host(local_ip, base_dir, labs_def)
            elif sub_c == "3":
                custom_h = input(f"{BOLD}Enter new IP or DDNS Domain: {RESET}").strip()
                if custom_h:
                    set_persistent_host(custom_h, base_dir, labs_def)
                else:
                    print_error("Invalid input.")
            elif sub_c == "4":
                cfg = os.path.join(base_dir, CONFIG_HOST_FILE)
                if os.path.exists(cfg):
                    os.remove(cfg)
                print_success("Reset host configuration to automatic LAN detection.")
                for lab in labs_def:
                    generate_vpn_profile(lab, base_dir)
            input(f"\nPress Enter to return to main menu...")
        elif choice == "14":
            print(f"\n{BOLD}{CYAN}--- Available Labs ---{RESET}")
            for lab in labs_def:
                print(f"  {BOLD}{lab['index']}){RESET} {lab['dir']}")
            lab_choice = input(f"\n{BOLD}Enter lab index to connect VPN (1-{len(labs_def)}): {RESET}").strip()
            matched = find_lab(labs_def, lab_choice)
            if matched:
                connect_wireguard(matched, base_dir)
            else:
                print_error("Invalid selection.")
            input(f"\nPress Enter to return to main menu...")
        elif choice == "15":
            print(f"\n{BOLD}{CYAN}--- Available Labs ---{RESET}")
            for lab in labs_def:
                print(f"  {BOLD}{lab['index']}){RESET} {lab['dir']}")
            lab_choice = input(f"\n{BOLD}Enter lab index to disconnect VPN (1-{len(labs_def)}): {RESET}").strip()
            matched = find_lab(labs_def, lab_choice)
            if matched:
                disconnect_wireguard(matched, base_dir)
            else:
                print_error("Invalid selection.")
            input(f"\nPress Enter to return to main menu...")
        elif choice == "16":
            flag_input = input(f"\n{BOLD}Enter captured flag (OSCP{{...}}): {RESET}").strip()
            if flag_input:
                handle_submit_flag(flag_input)
            input(f"\nPress Enter to return to main menu...")
        elif choice == "17":
            print(f"\n{BOLD}{CYAN}--- Available Labs for Hints ---{RESET}")
            for lab in labs_def:
                print(f"  {BOLD}{lab['index']}){RESET} {lab['dir']}")
            lab_choice = input(f"\n{BOLD}Enter lab index (1-{len(labs_def)}): {RESET}").strip()
            if lab_choice:
                handle_show_hint(lab_choice)
            input(f"\nPress Enter to return to main menu...")
        elif choice == "18":
            handle_show_flags()
            input(f"\nPress Enter to return to main menu...")
        elif choice == "19":
            print(f"\n{BOLD}{CYAN}--- OSCP Mock Exam Simulator ---{RESET}")
            print(f"  {BOLD}[1]{RESET} View Active Exam Status & Remaining Time")
            print(f"  {BOLD}[2]{RESET} Start New 24-Hour Mock Exam (Blind Challenges)")
            print(f"  {BOLD}[3]{RESET} Stop / Forfeit Current Exam Session")
            print(f"  {BOLD}[4]{RESET} Return to main menu")
            sub_e = input(f"\n{BOLD}Enter choice (1-4): {RESET}").strip()
            if sub_e == "1":
                handle_exam_command("status")
            elif sub_e == "2":
                handle_exam_command("start")
            elif sub_e == "3":
                handle_exam_command("stop")
            input(f"\nPress Enter to return to main menu...")
        elif choice == "20":
            print_info("Exiting...")
            break
        else:
            print_error("Invalid option. Please try again.")
            time.sleep(1)

if __name__ == '__main__':
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        print(f"\n{YELLOW}{BOLD}Interrupted by user. Exiting...{RESET}")
        sys.exit(130)
