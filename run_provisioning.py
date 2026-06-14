import subprocess
import os
import sys
import time
import argparse


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
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print_error(f"Error executing command: {res.stderr.strip()}")
        if check:
            sys.exit(res.returncode)
    else:
        if res.stdout:
            print(res.stdout.strip())
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

def process_wg_config(src_path, dest_path):
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
        if "ListenPort" not in line:
            filtered.append(line)
            
    with open(dest_path, "w") as f:
        f.writelines(filtered)
    print_success(f"Processed and wrote: {dest_path}")
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
    run_cmd(["docker", "cp", "delegation-s4u-lab/configure_delegation.py", "deleg-dc:/tmp/configure_delegation.py"])
    run_cmd(["docker", "exec", "deleg-dc", "python3", "/tmp/configure_delegation.py"])
    run_cmd(["docker", "exec", "deleg-dc", "samba-tool", "user", "setpassword", "Administrator", "--newpassword=DelegationAdminPass2026!", "--configfile=/samba/etc/smb.conf"])

def deploy_lab(lab, base_dir, script_path):
    print(f"\n{BLUE}{BOLD}---------------------------------------------------{RESET}")
    print(f"{BLUE}{BOLD}🚀 Deploying & Provisioning: {lab['dir']}{RESET}")
    print(f"{BLUE}{BOLD}---------------------------------------------------{RESET}")
    

    os.chdir(os.path.join(base_dir, lab["dir"]))
    run_cmd(["docker", "compose", "up", "-d"])
    os.chdir(base_dir)
    
  
    for dc in lab["dcs"]:
        wait_for_healthy(dc)
        
    print_info("Sleeping 5s for services stabilization...")
    time.sleep(5)
    

    lab["prov_fn"](base_dir, script_path)
    
 
    for wg_src_sub, wg_dest_name in lab["wg"]:
        src_path = os.path.join(base_dir, lab["dir"], wg_src_sub, "peer1", "peer1.conf")
        dest_path = os.path.join(base_dir, lab["dir"], wg_dest_name)
        process_wg_config(src_path, dest_path)
        
    print_success(f"{lab['dir']} is fully deployed and provisioned.\n")

def stop_lab(lab, base_dir):
    print(f"\n{YELLOW}[*] Stopping lab: {lab['dir']}...{RESET}")
    os.chdir(os.path.join(base_dir, lab["dir"]))
    run_cmd(["docker", "compose", "down"])
    os.chdir(base_dir)
    print_success(f"Lab {lab['dir']} has stopped.")

def clean_lab(lab, base_dir):
    print(f"\n{RED}[*] Cleaning (removing volumes) lab: {lab['dir']}...{RESET}")
    os.chdir(os.path.join(base_dir, lab["dir"]))
    run_cmd(["docker", "compose", "down", "-v"])
    os.chdir(base_dir)
    print_success(f"Lab {lab['dir']} has been cleaned.")

def show_banner():
    banner = f"""{CYAN}{BOLD}
------------------------------------------------------
 █████╗ ██████╗ ██╗      █████╗ ██████╗ ███████╗
██╔══██╗██╔══██╗██║     ██╔══██╗██╔══██╗██╔════╝
███████║██║  ██║██║     ███████║██████╔╝███████╗
██╔══██║██║  ██║██║     ██╔══██║██╔══██╗╚════██║
██║  ██║██████╔╝███████╗██║  ██║██████╔╝███████║
╚═╝  ╚═╝╚═════╝ ╚══════╝╚═╝  ╚═╝╚═════╝ ╚══════╝
{RESET}{BLUE} Active Directory Pentesting Lab Suite Manager{RESET}
{CYAN}------------------------------------------------------{RESET}"""
    print(banner)

def main():
    base_dir = os.getcwd()
    script_path = os.path.join(base_dir, "configure_ad.py")

    labs_def = [
        {
            "index": 1,
            "dir": "oscp-network-pivot-lab",
            "dcs": ["ad-forest-parent", "ad-forest-child"],
            "wg": [("wireguard_oscp", "oscp-pivot-lab.conf")],
            "prov_fn": provision_lab1
        },
        {
            "index": 2,
            "dir": "multi-domain-forest-lab",
            "dcs": ["mega-dc-parent", "mega-dc-child", "mega-dc-tree"],
            "wg": [("wireguard_forest", "multi-domain-forest-lab.conf")],
            "prov_fn": provision_lab2
        },
        {
            "index": 3,
            "dir": "adcs-abuse-lab",
            "dcs": ["adcs-dc"],
            "wg": [("wireguard_adcs", "oscp-adcs-lab.conf")],
            "prov_fn": provision_lab3
        },
        {
            "index": 4,
            "dir": "trust-pivoting-lab",
            "dcs": ["dc-foresta", "dc-forestb"],
            "wg": [("wireguard_trust", "oscp-trust-lab.conf")],
            "prov_fn": provision_lab4
        },
        {
            "index": 5,
            "dir": "gpo-admin-pivot-lab",
            "dcs": ["gpo-dc"],
            "wg": [("wireguard_gpo", "oscp-gpo-lab.conf")],
            "prov_fn": provision_lab5
        },
        {
            "index": 6,
            "dir": "rbcd-lab",
            "dcs": ["rbcd-dc"],
            "wg": [("wireguard_rbcd", "oscp-rbcd-lab.conf")],
            "prov_fn": provision_lab6
        },
        {
            "index": 7,
            "dir": "sql-pivot-lab",
            "dcs": ["sql-dc"],
            "wg": [("wireguard_sql", "oscp-sql-lab.conf")],
            "prov_fn": provision_lab7
        },
        {
            "index": 8,
            "dir": "laps-lab",
            "dcs": ["laps-dc"],
            "wg": [("wireguard_laps", "oscp-laps-lab.conf")],
            "prov_fn": provision_lab8
        },
        {
            "index": 9,
            "dir": "esc8-relay-lab",
            "dcs": ["esc8-dc"],
            "wg": [("wireguard_esc8", "oscp-esc8-lab.conf")],
            "prov_fn": provision_lab9
        },
        {
            "index": 10,
            "dir": "delegation-s4u-lab",
            "dcs": ["deleg-dc"],
            "wg": [("wireguard_deleg", "oscp-delegation-lab.conf")],
            "prov_fn": provision_lab10
        }
    ]

    parser = argparse.ArgumentParser(description="Manage AD Labs setup and provisioning.")
    parser.add_argument("--all", action="store_true", help="Start and provision all 10 labs")
    parser.add_argument("--lab", type=str, help="Start and provision a specific lab (by name or 1-10 index)")
    parser.add_argument("--stop-all", action="store_true", help="Stop all labs")
    parser.add_argument("--stop", type=str, help="Stop a specific lab (by name or 1-10 index)")
    parser.add_argument("--clean-all", action="store_true", help="Stop and remove volumes for all labs")
    parser.add_argument("--clean", type=str, help="Stop and remove volumes for a specific lab")
    
    args = parser.parse_args()

  
    has_args = any([args.all, args.lab, args.stop_all, args.stop, args.clean_all, args.clean])

    if has_args:
        show_banner()
        if args.all:
            for lab in labs_def:
                deploy_lab(lab, base_dir, script_path)
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
                deploy_lab(matched, base_dir, script_path)
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
        return


    while True:
        show_banner()
        print(f" {GREEN}🚀{RESET} {BOLD}[1]{RESET} Deploy & Provision {BOLD}ALL{RESET} 10 labs {YELLOW}(Warning: Resource Intensive){RESET}")
        print(f" {CYAN}🧪{RESET} {BOLD}[2]{RESET} Select a specific lab to Deploy & Provision")
        print(f" {RED}⏹️ {RESET} {BOLD}[3]{RESET} Stop {BOLD}ALL{RESET} active labs")
        print(f" {YELLOW}⏸️ {RESET} {BOLD}[4]{RESET} Stop a specific active lab")
        print(f" {RED}🧹{RESET} {BOLD}[5]{RESET} Clean {BOLD}ALL{RESET} labs (Stop & Remove local docker volumes)")
        print(f" {RED}🗑️ {RESET} {BOLD}[6]{RESET} Clean a specific lab (Stop & Remove volumes)")
        print(f" {BLUE}🚪{RESET} {BOLD}[7]{RESET} Exit")
        print(f"{CYAN}------------------------------------------------------{RESET}")
        
        choice = input(f"{BOLD}Enter choice (1-7): {RESET}").strip()
        
        if choice == "1":
            confirm = input(f"{YELLOW}{BOLD}[!] Are you sure you want to run all 10 labs? This requires significant RAM. (y/n): {RESET}").strip().lower()
            if confirm == 'y':
                for lab in labs_def:
                    deploy_lab(lab, base_dir, script_path)
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
                deploy_lab(matched, base_dir, script_path)
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
            print_info("Exiting...")
            break
        else:
            print_error("Invalid option. Please try again.")
            time.sleep(1)

if __name__ == '__main__':
    main()
