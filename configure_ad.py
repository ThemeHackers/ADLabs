import sys
import os
import argparse
import glob
import subprocess
import samba
from samba.samdb import SamDB
import samba.param
import samba.dsdb as dsdb
from samba.auth import system_session
from ldb import Message, MessageElement, FLAG_MOD_REPLACE, Dn, SCOPE_SUBTREE

def run_samba_tool(args_list):
    cmd = ["samba-tool"] + args_list + ["--configfile=/samba/etc/smb.conf"]
    print(f"Running command: {' '.join(cmd)}", flush=True)
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print(f"Command failed with code {res.returncode}. Stderr: {res.stderr.strip()}", flush=True)
    else:
        print(f"Command succeeded. Stdout: {res.stdout.strip()}", flush=True)
    return res.returncode == 0

def create_user_if_not_exists(samdb, username, password, realm):
    search_filter = f"sAMAccountName={username}"
    res = samdb.search(base=samdb.domain_dn(), scope=SCOPE_SUBTREE, expression=search_filter)
    if len(res) > 0:
        print(f"User {username} already exists.", flush=True)
        return True
    
    print(f"Creating user {username}...", flush=True)
    return run_samba_tool(["user", "create", username, password, f"--realm={realm}"])

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--role', required=True, choices=['parent', 'child', 'tree'])
    parser.add_argument('--realm', required=True)
    parser.add_argument('--practice-users', help='Space-separated list of practice users to create')
    args = parser.parse_args()

    print(f"Starting AD configuration script. Role={args.role}, Realm={args.realm}", flush=True)


    lp = samba.param.LoadParm()
    lp.load('/samba/etc/smb.conf')
    samdb = SamDB(url='/samba/private/sam.ldb', lp=lp, session_info=system_session())
    domain_dn = samdb.domain_dn()
    print(f"Connected to SamDB for domain DN: {domain_dn}", flush=True)


    print("=== 1. Setting Password Policy ===", flush=True)
    run_samba_tool(["domain", "passwordsettings", "set", "--complexity=off"])
    run_samba_tool(["domain", "passwordsettings", "set", "--min-pwd-length=4"])
    run_samba_tool(["domain", "passwordsettings", "set", "--history-length=0"])

    if args.role == 'parent':

        print("=== 2. Creating AS-REP Roasting User ===", flush=True)
        create_user_if_not_exists(samdb, "svc_backups", "BackupPassword123!", args.realm)
        samdb.toggle_userAccountFlags("sAMAccountName=svc_backups", dsdb.UF_DONT_REQUIRE_PREAUTH, "dont-require-preauth", on=True, strict=False)
        samdb.toggle_userAccountFlags("sAMAccountName=svc_backups", dsdb.UF_DONT_EXPIRE_PASSWD, "dont-expire-passwd", on=True, strict=False)

      
        print("=== 3. Creating Unconstrained Delegation User ===", flush=True)
        create_user_if_not_exists(samdb, "svc_delegate", "DelegatePass123!", args.realm)
        samdb.toggle_userAccountFlags("sAMAccountName=svc_delegate", dsdb.UF_TRUSTED_FOR_DELEGATION, "trusted-for-delegation", on=True, strict=False)
        samdb.toggle_userAccountFlags("sAMAccountName=svc_delegate", dsdb.UF_DONT_EXPIRE_PASSWD, "dont-expire-passwd", on=True, strict=False)


        print("=== 4. Injecting GPP Password Leak to SYSVOL ===", flush=True)
        policies_path = f"/samba/state/sysvol/{args.realm.lower()}/Policies"
        policy_dirs = glob.glob(os.path.join(policies_path, "*{*}*"))
        if policy_dirs:
            target_dir = policy_dirs[0]
            pref_dir = os.path.join(target_dir, "Machine", "Preferences", "Groups")
            os.makedirs(pref_dir, exist_ok=True)
            groups_xml_path = os.path.join(pref_dir, "Groups.xml")
            
            xml_content = """<?xml version="1.0" encoding="utf-8"?>
<Groups clsid="{3137632E-FA86-4d0f-A02F-A5C94B3C53F7}">
  <User clsid="{574cc713-398b-4c1e-9119-77a3d3170E38}" name="local_admin" image="2" changed="2026-06-14 10:00:00" uid="{D1240182-1D47-49f5-A4F7-94DF8E96541D}">
    <Properties action="U" newName="local_admin" fullName="" description="" cpassword="j1UyjF5pi7W8Y6fL5xV49V2nU48V392473489" changeLogon="0" noChangeLogon="1" neverExpires="1" disabled="0" userName="local_admin"/>
  </User>
</Groups>"""
            with open(groups_xml_path, "w", encoding="utf-8") as f:
                f.write(xml_content)
            print(f"SYSVOL GPP injected successfully at {groups_xml_path}", flush=True)
        else:
            print("WARNING: No GPO Policy directories found to inject GPP XML.", flush=True)

    elif args.role == 'child':

        print("=== 2. Creating Kerberoasting User ===", flush=True)
        create_user_if_not_exists(samdb, "sql_service", "SQLServicePass123!", args.realm)
       
        spn_str = f"MSSQLSvc/sql-db.{args.realm.lower()}:1433"
        print(f"Adding SPN {spn_str} to sql_service...", flush=True)
        run_samba_tool(["spn", "add", spn_str, "sql_service"])


        if args.practice_users:
            print("=== 3. Creating Practice Users ===", flush=True)
            users_list = args.practice_users.split()
           
            cred_file = "/tmp/credentials_generated.txt"
            with open(cred_file, "w") as f:
                for idx, username in enumerate(users_list, start=1):
                    password = f"CorpSecurePass2026!{idx}"
                    create_user_if_not_exists(samdb, username, password, args.realm)
                    f.write(f"{username}:{password}\n")
            print(f"Created {len(users_list)} practice users. Saved details to {cred_file}", flush=True)

    print("Configuration finished successfully!", flush=True)

if __name__ == '__main__':
    main()
