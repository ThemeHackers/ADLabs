import subprocess
import os
import sys
import time
import argparse
import socket
import re


BLUE = "\033[94m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
MAGENTA = "\033[95m"
CYAN = "\033[96m"
BOLD = "\033[1m"
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
    print(f"\n{MAGENTA}{BOLD}--- {msg} ---{RESET}")

def run_cmd(cmd, check=True):
    print_info(f"Executing: {' '.join(cmd)}")
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )
    stdout_lines = []
    for line in iter(process.stdout.readline, ''):
        print(line, end='', flush=True)
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
        print_error(f"Error executing command: exit code {res.returncode}")
        if check:
            sys.exit(res.returncode)
    return res

def wait_for_healthy(container_name, timeout=120):
    print_info(f"Waiting for {container_name} to become healthy...")
    start_time = time.time()
    while time.time() - start_time < timeout:
        res = subprocess.run(["docker", "inspect", "--format", "{{.State.Health.Status}}", container_name], capture_output=True, text=True)
        status = res.stdout.strip()
        if status == "healthy":
            print_success(f"{container_name} is HEALTHY.")
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
            filtered.append(f"Address = {allocated_client_ip}\n")
        elif line.strip().startswith("Endpoint"):
            filtered.append(f"Endpoint = {host_ip}:{allocated_port}\n")
        else:
            filtered.append(line)
            
    with open(dest_path, "w") as f:
        f.writelines(filtered)
    print_success(f"Processed and wrote: {dest_path} (Endpoint={host_ip}:{allocated_port}, Address={allocated_client_ip})")
    return True

def process_generated_creds(src_container, dest_dir):
    os.makedirs(dest_dir, exist_ok=True)
    cred_host_path = os.path.join(dest_dir, "credentials.txt")
    run_cmd(["docker", "cp", f"{src_container}:/tmp/credentials_generated.txt", cred_host_path])
    
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

    if db_ready:
        run_cmd(["docker", "exec", "-u", "postgres", "internal-postgres-db", "psql", "-d", "postgres", "-c", "CREATE TABLE IF NOT EXISTS ad_sync_credentials (id SERIAL PRIMARY KEY, service_name VARCHAR(100), ad_username VARCHAR(100), ad_password VARCHAR(100), description TEXT);"], check=False)
        run_cmd(["docker", "exec", "-u", "postgres", "internal-postgres-db", "psql", "-d", "postgres", "-c", "INSERT INTO ad_sync_credentials (service_name, ad_username, ad_password, description) VALUES ('LDAP User Sync', 'l1_j.doe', 'SimplePass2026!', 'AD Bind account for synchronizing users');"], check=False)
    else:
        print_warning("Could not verify internal-postgres-db readiness. Attempting queries anyway...")
        run_cmd(["docker", "exec", "-u", "postgres", "internal-postgres-db", "psql", "-d", "postgres", "-c", "CREATE TABLE IF NOT EXISTS ad_sync_credentials (id SERIAL PRIMARY KEY, service_name VARCHAR(100), ad_username VARCHAR(100), ad_password VARCHAR(100), description TEXT);"], check=False)
        run_cmd(["docker", "exec", "-u", "postgres", "internal-postgres-db", "psql", "-d", "postgres", "-c", "INSERT INTO ad_sync_credentials (service_name, ad_username, ad_password, description) VALUES ('LDAP User Sync', 'l1_j.doe', 'SimplePass2026!', 'AD Bind account for synchronizing users');"], check=False)

    run_cmd(["docker", "cp", script_path, "ad-forest-parent:/tmp/configure_ad.py"])
    run_cmd(["docker", "exec", "ad-forest-parent", "python3", "/tmp/configure_ad.py", "--role", "parent", "--realm", "MEGACORP.LOCAL", "--user-prefix", "l1_"])
    run_cmd(["docker", "cp", script_path, "ad-forest-child:/tmp/configure_ad.py"])
    practice_users_l1 = "j.smith r.jones m.brown t.taylor d.miller j.wilson b.moore s.taylor a.anderson k.thomas c.jackson m.white l.harris e.martin r.clark s.lewis g.robinson j.walker k.young p.allen"
    run_cmd(["docker", "exec", "ad-forest-child", "python3", "/tmp/configure_ad.py", "--role", "child", "--realm", "HQ.MEGACORP.LOCAL", "--practice-users", practice_users_l1, "--user-prefix", "l1_"])
    process_generated_creds("ad-forest-child", os.path.join(base_dir, "oscp-network-pivot-lab", "oscp_exam_assets"))
    
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
    process_generated_creds("mega-dc-child", os.path.join(base_dir, "multi-domain-forest-lab"))
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
    run_cmd(["docker", "cp", "rbcd-lab/configure_rbcd.py", "rbcd-dc:/tmp/configure_rbcd.py"])
    run_cmd(["docker", "exec", "rbcd-dc", "python3", "/tmp/configure_rbcd.py"])
    run_cmd(["docker", "exec", "rbcd-dc", "samba-tool", "user", "setpassword", "Administrator", "--newpassword=RBCDAccessAdminPass2026!", "--configfile=/samba/etc/smb.conf"])

def provision_lab7(base_dir, script_path):
    print_header("Provisioning Lab 7 (sql-pivot-lab)")
    run_cmd(["docker", "cp", "sql-pivot-lab/configure_sql.py", "sql-dc:/tmp/configure_sql.py"])
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
    run_cmd(["docker", "cp", "laps-lab/configure_laps.py", "laps-dc:/tmp/configure_laps.py"])
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
    run_cmd(["docker", "cp", "esc8-relay-lab/configure_esc8.py", "esc8-dc:/tmp/configure_esc8.py"])
    run_cmd(["docker", "exec", "esc8-dc", "python3", "/tmp/configure_esc8.py"])
    run_cmd(["docker", "exec", "esc8-dc", "samba-tool", "user", "setpassword", "Administrator", "--newpassword=ESC8AdminPass2026!", "--configfile=/samba/etc/smb.conf"])

def provision_lab10(base_dir, script_path):
    print_header("Provisioning Lab 10 (delegation-s4u-lab)")
    run_cmd(["docker", "exec", "deleg-dc", "python3", "/tmp/configure_delegation.py"])
    run_cmd(["docker", "exec", "deleg-dc", "samba-tool", "user", "setpassword", "Administrator", "--newpassword=DelegationAdminPass2026!", "--configfile=/samba/etc/smb.conf"])

def get_host_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = '127.0.0.1'
    finally:
        s.close()
    return ip

def get_free_udp_port(start_port=51820):
    port = start_port
    while True:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            try:
                s.bind(('0.0.0.0', port))
                return port
            except socket.error:
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
    
    with open(compose_path, 'w', encoding='utf-8') as f:
        f.write(content)

def generate_vpn_profile(lab, base_dir):
    print_header(f"Generating/Regenerating VPN Profile for {lab['dir']}")
    compose_path = os.path.join(base_dir, lab["dir"], "docker-compose.yml")
    if not os.path.exists(compose_path):
        print_error(f"docker-compose.yml not found at {compose_path}")
        return False
        
    with open(compose_path, 'r', encoding='utf-8') as f:
        content = f.read()
        
    port_match = re.search(r'SERVERPORT=(\d+)', content)
    subnet_match = re.search(r'INTERNAL_SUBNET=(10\.252\.\d+\.0/24)', content)
    
    if not port_match or not subnet_match:
        print_error("Failed to parse existing SERVERPORT or INTERNAL_SUBNET from docker-compose.yml. Has the lab been deployed at least once?")
        return False
        
    allocated_port = int(port_match.group(1))
    allocated_subnet = subnet_match.group(1)
    
    subnet_prefix = allocated_subnet.split(".0/24")[0]
    allocated_client_ip = f"{subnet_prefix}.2"
    
    host_ip = get_host_ip()
    print_info(f"Using current Host IP: {host_ip}")
    print_info(f"Using parsed WG Port: {allocated_port}")
    print_info(f"Using parsed WG Subnet: {allocated_subnet} (Client IP: {allocated_client_ip})")
    
    content = re.sub(r'-\s*SERVERURL=[^\s\n]+', f'- SERVERURL={host_ip}', content)
    with open(compose_path, 'w', encoding='utf-8') as f:
        f.write(content)
        
    success = True
    for wg_src_sub, wg_dest_name in lab["wg"]:
        src_path = os.path.join(base_dir, lab["dir"], wg_src_sub, "peer1", "peer1.conf")
        dest_path = os.path.join(base_dir, lab["dir"], wg_dest_name)
        if not os.path.exists(src_path):
            print_error(f"Source config file not found: {src_path}")
            print_warning("Please deploy the lab first to generate the initial WireGuard keys and configuration files.")
            success = False
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
            os.chdir(os.path.join(base_dir, lab["dir"]))
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

def configure_central_dns(lab):
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
    
    for domain, ip in lab["dns_mappings"].items():
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
        
    for net_name in lab["dns_networks"]:
        actual_net = find_docker_network(lab["dir"], net_name)
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
             "--lab-dir", os.path.join(base_dir, lab["dir"]),
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

def deploy_lab(lab, base_dir, script_path, labs_def):
    print(f"\n{BLUE}{BOLD}---------------------------------------------------{RESET}")
    print(f"{BLUE}{BOLD}🚀 Deploying & Provisioning: {lab['dir']}{RESET}")
    print(f"{BLUE}{BOLD}---------------------------------------------------{RESET}")
    
    stop_other_labs(lab, labs_def, base_dir)
    
    host_ip = get_host_ip()
    allocated_port = get_free_udp_port(51820)
    allocated_subnet, allocated_client_ip = get_free_subnet(1)
    
    print_info(f"Dynamically allocated host IP: {host_ip}")
    print_info(f"Dynamically allocated WG port: {allocated_port}")
    print_info(f"Dynamically allocated WG subnet: {allocated_subnet} (Client IP: {allocated_client_ip})")
    
    compose_path = os.path.join(base_dir, lab["dir"], "docker-compose.yml")
    modify_docker_compose(compose_path, host_ip, allocated_port, allocated_subnet)
    
    os.chdir(os.path.join(base_dir, lab["dir"]))
    run_cmd(["docker", "compose", "up", "-d"])
    os.chdir(base_dir)
    
    for dc in lab["dcs"]:
        wait_for_healthy(dc)
        
    print_info("Sleeping 5s for services stabilization...")
    time.sleep(5)
    
    lab["prov_fn"](base_dir, script_path)
    
    configure_central_dns(lab)
    
    for wg_src_sub, wg_dest_name in lab["wg"]:
        src_path = os.path.join(base_dir, lab["dir"], wg_src_sub, "peer1", "peer1.conf")
        dest_path = os.path.join(base_dir, lab["dir"], wg_dest_name)
        process_wg_config(src_path, dest_path, host_ip, allocated_port, allocated_client_ip)
        
    start_timeout_daemon(lab, base_dir)
    print_success(f"{lab['dir']} is fully deployed and provisioned.\n")

def stop_lab(lab, base_dir):
    print(f"\n{YELLOW}[*] Stopping lab: {lab['dir']}...{RESET}")
    stop_central_dns()
    os.chdir(os.path.join(base_dir, lab["dir"]))
    run_cmd(["docker", "compose", "down"])
    os.chdir(base_dir)
    print_success(f"Lab {lab['dir']} has stopped.")

def clean_lab(lab, base_dir):
    print(f"\n{RED}[*] Cleaning (removing volumes) lab: {lab['dir']}...{RESET}")
    stop_central_dns()
    os.chdir(os.path.join(base_dir, lab["dir"]))
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

    print(f"\n{BOLD}{CYAN}------------------------------------------------------{RESET}")
    print(f"{BOLD}🧪 Lab {lab['index']}: {lab['dir']}{RESET}")
    print(f"   🔑 WG Port: {actual_port} | Profile: {lab['vpn_profile']}")
    print(f"{BOLD}{CYAN}------------------------------------------------------{RESET}")
    
    print(f"{BOLD}[*] Docker Container Status:{RESET}")
    all_containers_running = True
    for container in lab["containers"]:
        status, color_name = check_container_status(container)
        color = GREEN if color_name == "green" else (YELLOW if color_name == "yellow" else RED)
        print(f"  - {container:<25}: {color}{status}{RESET}")
        if status != "RUNNING" and "UNHEALTHY" in status:
            all_containers_running = False
        elif status == "MISSING" or "STOPPED" in status:
            all_containers_running = False

    if not all_containers_running:
        print(f"  {YELLOW}⚠️  Note: Some containers are not running. Please start this lab first via:{RESET}")
        print(f"  python adlabs.py --lab {lab['index']}")
    
    print(f"\n{BOLD}[*] VPN Socket Connectivity (Attacker Host -> Lab Services):{RESET}")
    for target in lab["targets"]:
        success = test_port(target["ip"], target["port"])
        if success:
            print(f"  [+] {target['name']:<40} ({target['ip']}:{target['port']}): {GREEN}SUCCESS (Connected!){RESET}")
        else:
            print(f"  [-] {target['name']:<40} ({target['ip']}:{target['port']}): {RED}FAILED (Unreachable){RESET}")
            
    print(f"  {YELLOW}ℹ️  Note: For pivoting labs, internal targets are expected to be FAILED (Unreachable) directly from your host. You must pivot through a compromised foothold container.{RESET}")
    print(f"  {YELLOW}ℹ️  If connection failed, make sure your WireGuard Client is connected to '{lab['vpn_profile']}'{RESET}")

def run_wordlist_generation(base_dir):
    print_header("Generating / Recreating Wordlists for all labs")
    wordlist_script = os.path.join(base_dir, "core", "generate_wordlists.py")
    try:
        res = subprocess.run([sys.executable, wordlist_script], capture_output=True, text=True)
        if res.returncode == 0:
            print(res.stdout.strip())
            print_success("Wordlists generated successfully!")
        else:
            print_error(f"Failed to generate wordlists: {res.stderr.strip()}")
    except Exception as e:
        print_error(f"Exception raised while running wordlist generator: {e}")


def show_banner():
    banner = f"""{CYAN}{BOLD}
 ------------------------------------------------------
  █████╗ ██████╗ ██╗      █████╗ ██████╗ ███████╗
 ██╔══██╗██╔══██╗██║     ██╔══██╗██╔══██╗██╔════╝
 ███████║██║  ██║██║     ███████║██████╔╝███████╗
 ██╔══██║██║  ██║██║     ██╔══██║██╔══██╗╚════██║
 ██║  ██║██████╔╝███████╗██║  ██║██████╔╝███████║
 ╚═╝  ╚═╝╚═════╝ ╚══════╝╚═╝  ╚═╝╚═════╝ ╚══════╝
{RESET}{BLUE}  Active Directory Pentesting Lab Suite Manager{RESET}
{CYAN} ------------------------------------------------------{RESET}"""
    print(banner)


def start_web_ui():
    print_info("Starting Web UI Dashboard on http://127.0.0.1:8000 ...")
    base_dir = os.getcwd()
    app_path = os.path.join(base_dir, "web", "app.py")
    try:
        subprocess.run([sys.executable, app_path], cwd=base_dir)
    except KeyboardInterrupt:
        print_info("Web UI Dashboard stopped.")

labs_def = [
        {
            "index": 1,
            "dir": "oscp-network-pivot-lab",
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
                {"name": "Perimeter Web UI", "ip": "10.10.10.80", "port": 9000, "protocol": "TCP"},
                {"name": "Postgres Database", "ip": "10.20.20.20", "port": 5432, "protocol": "TCP"},
                {"name": "Parent Domain Controller (MEGACORP.LOCAL)", "ip": "10.100.10.10", "port": 445, "protocol": "TCP"},
                {"name": "Child Domain Controller (HQ.MEGACORP.LOCAL)", "ip": "10.100.10.20", "port": 389, "protocol": "TCP"}
            ]
        },
        {
            "index": 2,
            "dir": "multi-domain-forest-lab",
            "dcs": ["mega-dc-parent", "mega-dc-child", "mega-dc-tree"],
            "wg": [("wireguard_forest", "multi-domain-forest-lab.conf")],
            "wg_container": "mega-wg-gateway",
            "dns_domains": ["megacorp.local", "hq.megacorp.local", "cybertech.local"],
            "dns_mappings": {"megacorp.local": "10.101.10.10", "hq.megacorp.local": "10.101.20.10", "cybertech.local": "10.101.30.10"},
            "dns_networks": ["parent-net", "child-net", "tree-net"],
            "prov_fn": provision_lab2,
            "vpn_port": "51821/UDP",
            "vpn_profile": "multi-domain-forest-lab.conf",
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
            "dcs": ["deleg-dc"],
            "wg": [("wireguard_deleg", "oscp-delegation-lab.conf")],
            "wg_container": "deleg-wg-gateway",
            "dns_domains": ["delegatelab.local"],
            "dns_mappings": {"delegatelab.local": "10.109.10.10"},
            "dns_networks": ["ad-net"],
            "prov_fn": provision_lab10,
            "vpn_port": "51829/UDP",
            "vpn_profile": "oscp-delegation-lab.conf",
            "containers": ["deleg-dc", "deleg-db"],
            "targets": [
                {"name": "Domain Controller (DELEGATELAB.LOCAL)", "ip": "10.109.10.10", "port": 445, "protocol": "TCP"},
                {"name": "Database Server SSH", "ip": "10.109.20.20", "port": 22, "protocol": "TCP"}
            ]
        }
    ]

def main():
    base_dir = os.getcwd()
    script_path = os.path.join(base_dir, "core", "configure_ad.py")

    parser = argparse.ArgumentParser(description="Manage AD Labs setup, provisioning, and connectivity.")
    parser.add_argument("--all", "-a", action="store_true", help="Start and provision all 10 labs")
    parser.add_argument("--lab", "-l", type=str, help="Start and provision a specific lab (by name or 1-10 index)")
    parser.add_argument("--stop-all", action="store_true", help="Stop all labs")
    parser.add_argument("--stop", type=str, help="Stop a specific lab (by name or 1-10 index)")
    parser.add_argument("--clean-all", action="store_true", help="Stop and remove volumes for all labs")
    parser.add_argument("--clean", type=str, help="Stop and remove volumes for a specific lab")
    parser.add_argument("--test-all", action="store_true", help="Test connectivity & status of all labs")
    parser.add_argument("--test", type=str, help="Test connectivity & status of a specific lab (by name or index)")
    parser.add_argument("--generate-wordlists", action="store_true", help="Generate / Recreate users.txt and pass.txt wordlists for all labs")
    parser.add_argument("--gen-vpn", type=str, help="Generate / Regenerate VPN profiles for a lab (or 'all' / index / name)")
    parser.add_argument("--web", action="store_true", help="Start the Web UI Management Dashboard")

    
    args = parser.parse_args()

    has_args = any([
        args.all, args.lab, args.stop_all, args.stop, 
        args.clean_all, args.clean, args.test_all, args.test,
        args.generate_wordlists, args.gen_vpn, args.web
    ])

    if has_args:
        show_banner()
        if args.all:
            for lab in labs_def:
                deploy_lab(lab, base_dir, script_path, labs_def)
        elif args.lab:
            target = args.lab.strip()
            matched = None
            for lab in labs_def:
                if target.isdigit() and int(target) == lab["index"]:
                    matched = lab
                    break
                elif lab["dir"] == target:
                    matched = lab
                    break
            if matched:
                deploy_lab(matched, base_dir, script_path, labs_def)
            else:
                print_error(f"Lab '{target}' not found.")
                sys.exit(1)
        elif args.stop_all:
            for lab in labs_def:
                stop_lab(lab, base_dir)
        elif args.stop:
            target = args.stop.strip()
            matched = None
            for lab in labs_def:
                if target.isdigit() and int(target) == lab["index"]:
                    matched = lab
                    break
                elif lab["dir"] == target:
                    matched = lab
                    break
            if matched:
                stop_lab(matched, base_dir)
            else:
                print_error(f"Lab '{target}' not found.")
                sys.exit(1)
        elif args.clean_all:
            for lab in labs_def:
                clean_lab(lab, base_dir)
        elif args.clean:
            target = args.clean.strip()
            matched = None
            for lab in labs_def:
                if target.isdigit() and int(target) == lab["index"]:
                    matched = lab
                    break
                elif lab["dir"] == target:
                    matched = lab
                    break
            if matched:
                clean_lab(matched, base_dir)
            else:
                print_error(f"Lab '{target}' not found.")
                sys.exit(1)
        elif args.test_all:
            for lab in labs_def:
                test_lab_connectivity(lab)
        elif args.test:
            target = args.test.strip()
            matched = None
            for lab in labs_def:
                if target.isdigit() and int(target) == lab["index"]:
                    matched = lab
                    break
                elif lab["dir"] == target:
                    matched = lab
                    break
            if matched:
                test_lab_connectivity(matched)
            else:
                print_error(f"Lab '{target}' not found.")
                sys.exit(1)
        elif args.generate_wordlists:
            run_wordlist_generation(base_dir)
        elif args.gen_vpn:
            target = args.gen_vpn.strip()
            if target.lower() == 'all':
                for lab in labs_def:
                    generate_vpn_profile(lab, base_dir)
            else:
                matched = None
                for lab in labs_def:
                    if target.isdigit() and int(target) == lab["index"]:
                        matched = lab
                        break
                    elif lab["dir"] == target:
                        matched = lab
                        break
                if matched:
                    generate_vpn_profile(matched, base_dir)
                else:
                    print_error(f"Lab '{target}' not found.")
                    sys.exit(1)
        elif args.web:
            start_web_ui()
        return


    while True:
        show_banner()
        print(f" {GREEN}🚀{RESET} {BOLD}[1]{RESET} Deploy & Provision {BOLD}ALL{RESET} 10 labs {YELLOW}(Warning: Resource Intensive){RESET}")
        print(f" {CYAN}🧪{RESET} {BOLD}[2]{RESET} Select a specific lab to Deploy & Provision")
        print(f" {RED}⏹️ {RESET} {BOLD}[3]{RESET} Stop {BOLD}ALL{RESET} active labs")
        print(f" {YELLOW}⏸️ {RESET} {BOLD}[4]{RESET} Stop a specific active lab")
        print(f" {RED}🧹{RESET} {BOLD}[5]{RESET} Clean {BOLD}ALL{RESET} labs (Stop & Remove local docker volumes)")
        print(f" {RED}🗑️ {RESET} {BOLD}[6]{RESET} Clean a specific lab (Stop & Remove volumes)")
        print(f" {CYAN}🔍{RESET} {BOLD}[7]{RESET} Test Connectivity of {BOLD}ALL{RESET} labs")
        print(f" {CYAN}📡{RESET} {BOLD}[8]{RESET} Test Connectivity of a specific lab")
        print(f" {MAGENTA}📝{RESET} {BOLD}[9]{RESET} Generate / Recreate wordlists (users.txt & pass.txt) for all labs")
        print(f" {CYAN}🔑{RESET} {BOLD}[10]{RESET} Generate / Regenerate VPN profiles (Update Host IP)")
        print(f" {CYAN}🖥️{RESET}  {BOLD}[11]{RESET} Start Web UI Management Dashboard")
        print(f" {BLUE}🚪{RESET} {BOLD}[12]{RESET} Exit")
        print(f"{CYAN} ------------------------------------------------------{RESET}")
        
        choice = input(f"{BOLD}Enter choice (1-12): {RESET}").strip()
        
        if choice == "1":
            confirm = input(f"{YELLOW}{BOLD}[!] Are you sure you want to run all 10 labs? This requires significant RAM. (y/n): {RESET}").strip().lower()
            if confirm == 'y':
                for lab in labs_def:
                    deploy_lab(lab, base_dir, script_path, labs_def)
        elif choice == "2":
            print(f"\n{BOLD}{CYAN}--- Available Labs ---{RESET}")
            for lab in labs_def:
                print(f"  {BOLD}{lab['index']}){RESET} {lab['dir']}")
            lab_choice = input(f"\n{BOLD}Enter lab index (1-{len(labs_def)}): {RESET}").strip()
            matched = None
            for lab in labs_def:
                if lab_choice.isdigit() and int(lab_choice) == lab["index"]:
                    matched = lab
                    break
            if matched:
                deploy_lab(matched, base_dir, script_path, labs_def)
            else:
                print_error("Invalid selection.")
            input(f"\nPress Enter to return to main menu...")
        elif choice == "3":
            confirm = input(f"{YELLOW}{BOLD}[!] Are you sure you want to stop all labs? (y/n): {RESET}").strip().lower()
            if confirm == 'y':
                for lab in labs_def:
                    stop_lab(lab, base_dir)
            input(f"\nPress Enter to return to main menu...")
        elif choice == "4":
            print(f"\n{BOLD}{CYAN}--- Active Labs ---{RESET}")
            for lab in labs_def:
                print(f"  {BOLD}{lab['index']}){RESET} {lab['dir']}")
            lab_choice = input(f"\n{BOLD}Enter lab index to stop (1-{len(labs_def)}): {RESET}").strip()
            matched = None
            for lab in labs_def:
                if lab_choice.isdigit() and int(lab_choice) == lab["index"]:
                    matched = lab
                    break
            if matched:
                stop_lab(matched, base_dir)
            else:
                print_error("Invalid selection.")
            input(f"\nPress Enter to return to main menu...")
        elif choice == "5":
            confirm = input(f"{RED}{BOLD}[!] WARNING: This will destroy all databases and AD states for all labs. Proceed? (y/n): {RESET}").strip().lower()
            if confirm == 'y':
                for lab in labs_def:
                    clean_lab(lab, base_dir)
            input(f"\nPress Enter to return to main menu...")
        elif choice == "6":
            print(f"\n{BOLD}{CYAN}--- Available Labs ---{RESET}")
            for lab in labs_def:
                print(f"  {BOLD}{lab['index']}){RESET} {lab['dir']}")
            lab_choice = input(f"\n{BOLD}Enter lab index to clean (1-{len(labs_def)}): {RESET}").strip()
            matched = None
            for lab in labs_def:
                if lab_choice.isdigit() and int(lab_choice) == lab["index"]:
                    matched = lab
                    break
            if matched:
                clean_lab(matched, base_dir)
            else:
                print_error("Invalid selection.")
            input(f"\nPress Enter to return to main menu...")
        elif choice == "7":
            for lab in labs_def:
                test_lab_connectivity(lab)
            input(f"\nPress Enter to return to main menu...")
        elif choice == "8":
            print(f"\n{BOLD}{CYAN}--- Available Labs ---{RESET}")
            for lab in labs_def:
                print(f"  {BOLD}{lab['index']}){RESET} {lab['dir']}")
            lab_choice = input(f"\n{BOLD}Enter lab index to test (1-{len(labs_def)}): {RESET}").strip()
            matched = None
            for lab in labs_def:
                if lab_choice.isdigit() and int(lab_choice) == lab["index"]:
                    matched = lab
                    break
            if matched:
                test_lab_connectivity(matched)
            else:
                print_error("Invalid selection.")
            input(f"\nPress Enter to return to main menu...")
        elif choice == "9":
            run_wordlist_generation(base_dir)
            input(f"\nPress Enter to return to main menu...")
        elif choice == "10":
            print(f"\n{BOLD}{CYAN}--- Available Labs ---{RESET}")
            print(f"  {BOLD}0){RESET} ALL Labs")
            for lab in labs_def:
                print(f"  {BOLD}{lab['index']}){RESET} {lab['dir']}")
            lab_choice = input(f"\n{BOLD}Enter lab index to generate VPN for (0-{len(labs_def)}): {RESET}").strip()
            if lab_choice == "0":
                for lab in labs_def:
                    generate_vpn_profile(lab, base_dir)
            else:
                matched = None
                for lab in labs_def:
                    if lab_choice.isdigit() and int(lab_choice) == lab["index"]:
                        matched = lab
                        break
                if matched:
                    generate_vpn_profile(matched, base_dir)
                else:
                    print_error("Invalid selection.")
            input(f"\nPress Enter to return to main menu...")
        elif choice == "11":
            start_web_ui()
            input(f"\nPress Enter to return to main menu...")
        elif choice == "12":
            print_info("Exiting...")
            break
        else:
            print_error("Invalid option. Please try again.")
            time.sleep(1)

if __name__ == '__main__':
    main()
