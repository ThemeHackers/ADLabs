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
import samba.dcerpc.security as security
from samba.ndr import ndr_pack, ndr_unpack

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

def get_object_sid(samdb, filter_expr):
    res = samdb.search(base=samdb.domain_dn(), scope=SCOPE_SUBTREE, expression=filter_expr)
    if not res:
        return None, None
    sid = ndr_unpack(security.dom_sid, bytes(res[0]["objectSid"][0]))
    return sid, res[0].dn

def grant_ace_on_object(samdb, target_dn, trustee_sid, access_mask):
    try:
        res = samdb.search(base=target_dn, scope=SCOPE_SUBTREE,
                           expression="(objectClass=*)",
                           attrs=["nTSecurityDescriptor"])
        if not res:
            print(f"Object not found: {target_dn}", flush=True)
            return False
        sd = ndr_unpack(security.descriptor, bytes(res[0]["nTSecurityDescriptor"][0]))
        new_ace = security.ace()
        new_ace.type = security.SEC_ACE_TYPE_ACCESS_ALLOWED
        new_ace.flags = 0
        new_ace.access_mask = access_mask
        new_ace.trustee = trustee_sid
        aces = list(sd.dacl.aces) if sd.dacl and sd.dacl.aces else []
        aces.append(new_ace)
        sd.dacl.aces = aces
        sd.dacl.num_aces = len(aces)
        msg = Message()
        msg.dn = target_dn
        msg["nTSecurityDescriptor"] = MessageElement(
            ndr_pack(sd), FLAG_MOD_REPLACE, "nTSecurityDescriptor"
        )
        samdb.modify(msg)
        print(f"ACE granted (mask=0x{access_mask:08X}) on {target_dn}", flush=True)
        return True
    except Exception as e:
        print(f"Failed to grant ACE on {target_dn}: {e}", flush=True)
        return False

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

    print("=== 1. Setting Weak Password Policy ===", flush=True)
    run_samba_tool(["domain", "passwordsettings", "set", "--complexity=off"])
    run_samba_tool(["domain", "passwordsettings", "set", "--min-pwd-length=4"])
    run_samba_tool(["domain", "passwordsettings", "set", "--history-length=0"])
    run_samba_tool(["domain", "passwordsettings", "set", "--min-pwd-age=0"])
    run_samba_tool(["domain", "passwordsettings", "set", "--account-lockout-threshold=0"])

    if args.role == 'parent':

        print("=== 2. Creating AS-REP Roasting User (svc_backups) ===", flush=True)
        create_user_if_not_exists(samdb, "svc_backups", "BackupPassword123!", args.realm)
        samdb.toggle_userAccountFlags("sAMAccountName=svc_backups", dsdb.UF_DONT_REQUIRE_PREAUTH, "dont-require-preauth", on=True, strict=False)
        samdb.toggle_userAccountFlags("sAMAccountName=svc_backups", dsdb.UF_DONT_EXPIRE_PASSWD, "dont-expire-passwd", on=True, strict=False)

        print("=== 3. Creating Unconstrained Delegation User (svc_delegate) ===", flush=True)
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
            print(f"SYSVOL GPP injected at {groups_xml_path}", flush=True)

        print("=== 5. Configuring ACL Abuse Chain ===", flush=True)

        create_user_if_not_exists(samdb, "j.doe", "SimplePass2026!", args.realm)

        jdoe_sid, _ = get_object_sid(samdb, "sAMAccountName=j.doe")
        _, svcb_dn  = get_object_sid(samdb, "sAMAccountName=svc_backups")

        if jdoe_sid and svcb_dn:
            grant_ace_on_object(samdb, svcb_dn, jdoe_sid, security.SEC_GENERIC_ALL)
            print("ACL: j.doe has GenericAll over svc_backups (Password Reset / Targeted Kerberoast)", flush=True)

        run_samba_tool(["group", "add", "HelpDesk"])
        run_samba_tool(["group", "addmembers", "HelpDesk", "j.doe"])

        helpdesk_sid, _ = get_object_sid(samdb, "sAMAccountName=HelpDesk")
        _, da_dn = get_object_sid(samdb, "sAMAccountName=Domain Admins")
        if helpdesk_sid and da_dn:
            grant_ace_on_object(samdb, da_dn, helpdesk_sid, security.SEC_GENERIC_WRITE)
            print("ACL: HelpDesk has GenericWrite over Domain Admins (Self-Add Member)", flush=True)

        run_samba_tool(["group", "add", "IT-Support"])
        run_samba_tool(["group", "addmembers", "IT-Support", "j.doe"])

        itsupport_sid, _ = get_object_sid(samdb, "sAMAccountName=IT-Support")
        if itsupport_sid:
            domain_dn_obj = Dn(samdb, domain_dn)
            grant_ace_on_object(samdb, domain_dn_obj, itsupport_sid, security.SEC_STD_WRITE_DAC)
            print("ACL: IT-Support has WriteDACL on Domain -> DCSync path via DACL rewrite", flush=True)

        print("=== 6. Creating Silver Ticket Target (svc_mssql with SPN) ===", flush=True)
        create_user_if_not_exists(samdb, "svc_mssql", "MSSQLService2026!", args.realm)
        run_samba_tool(["spn", "add", f"MSSQLSvc/db-server.{args.realm.lower()}:1433", "svc_mssql"])
        run_samba_tool(["spn", "add", f"MSSQLSvc/db-server.{args.realm.lower()}", "svc_mssql"])
        samdb.toggle_userAccountFlags("sAMAccountName=svc_mssql", dsdb.UF_DONT_EXPIRE_PASSWD, "dont-expire-passwd", on=True, strict=False)
        print("svc_mssql created with SPN - Kerberoastable -> Silver Ticket after hash crack", flush=True)

        print("=== 7. Configuring Anonymous SMB Share ===", flush=True)
        share_dir = f"/var/lib/samba/shares/public"
        os.makedirs(share_dir, exist_ok=True)
        with open(os.path.join(share_dir, "web_db_backup.cfg"), "w") as f:
            f.write("db_host=10.20.20.20\n")
            f.write("db_user=postgres\n")
            f.write("db_pass=DB_Prod_Admin_SuperSecure_Pass2026!\n")
            f.write("ad_bind_user=j.doe\n")
            f.write("ad_bind_pass=SimplePass2026!\n")
        try:
            smb_conf = "/samba/etc/smb.conf"
            with open(smb_conf, "r") as f:
                content = f.read()
            if "Public_Archive" not in content:
                share_block = """
[Public_Archive]
   path = /var/lib/samba/shares/public
   browseable = yes
   read only = yes
   guest ok = yes
"""
                with open(smb_conf, "a") as f:
                    f.write(share_block)
                print("Anonymous SMB share 'Public_Archive' added", flush=True)
        except Exception as e:
            print(f"Could not update smb.conf: {e}", flush=True)

        print("=== 8. Golden Ticket Setup (krbtgt hash extraction) ===", flush=True)
        try:
            res_krb = subprocess.run([
                "samba-tool", "user", "getpassword", "krbtgt",
                "--attributes=nthash",
                "--configfile=/samba/etc/smb.conf"
            ], capture_output=True, text=True)

            import re as _re
            krbtgt_hash = None
            if res_krb.returncode == 0:
                m = _re.search(r"nthash:\s*([a-fA-F0-9]{32})", res_krb.stdout)
                if m:
                    krbtgt_hash = m.group(1)

            golden_notes_path = os.path.join(share_dir, "golden_ticket_notes.txt")
            with open(golden_notes_path, "w") as f:
                f.write(f"Domain: {args.realm}\n")
                f.write(f"krbtgt NT Hash: {krbtgt_hash if krbtgt_hash else 'Run DCSync to obtain: impacket-secretsdump'}\n")
                f.write(f"\nGolden Ticket Attack:\n")
                f.write(f"impacket-ticketer -nthash <KRBTGT_HASH> -domain-sid <DOMAIN_SID> ")
                f.write(f"-domain {args.realm} Administrator\n")
                f.write(f"export KRB5CCNAME=Administrator.ccache\n")
                f.write(f"impacket-wmiexec -k -no-pass {args.realm}/Administrator@dc-parent.{args.realm.lower()}\n")
            print(f"Golden Ticket notes written to SMB share. krbtgt hash: {krbtgt_hash}", flush=True)
        except Exception as e:
            print(f"Golden Ticket setup warning: {e}", flush=True)

    elif args.role == 'child':

        print("=== 2. Creating Kerberoasting User (sql_service) ===", flush=True)
        create_user_if_not_exists(samdb, "sql_service", "SQLServicePass123!", args.realm)
        spn_str = f"MSSQLSvc/sql-db.{args.realm.lower()}:1433"
        run_samba_tool(["spn", "add", spn_str, "sql_service"])

        print("=== 3. Creating Shadow Credentials Target (svc_api) ===", flush=True)
        create_user_if_not_exists(samdb, "svc_api", "APIServicePass2026!", args.realm)
        sql_sid, _ = get_object_sid(samdb, "sAMAccountName=sql_service")
        _, svcapi_dn = get_object_sid(samdb, "sAMAccountName=svc_api")
        if sql_sid and svcapi_dn:
            grant_ace_on_object(samdb, svcapi_dn, sql_sid, security.SEC_GENERIC_WRITE)
            print("ACL: sql_service has GenericWrite over svc_api -> msDS-KeyCredentialLink abuse", flush=True)

        if args.practice_users:
            print("=== 4. Creating Practice Users ===", flush=True)
            users_list = args.practice_users.split()
            cred_file = "/tmp/credentials_generated.txt"
            with open(cred_file, "w") as f:
                for idx, username in enumerate(users_list, start=1):
                    password = f"CorpSecurePass2026!{idx}"
                    create_user_if_not_exists(samdb, username, password, args.realm)
                    f.write(f"{username}:{password}\n")
            print(f"Created {len(users_list)} practice users. Saved to {cred_file}", flush=True)

    elif args.role == 'tree':

        print("=== 2. Creating Kerberoasting Target in Tree Domain ===", flush=True)
        create_user_if_not_exists(samdb, "svc_tree", "TreeServicePass123!", args.realm)
        run_samba_tool(["spn", "add", f"HTTP/web.{args.realm.lower()}:80", "svc_tree"])

    print("Configuration finished successfully!", flush=True)

if __name__ == '__main__':
    main()
