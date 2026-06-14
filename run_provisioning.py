import subprocess
import os
import sys
import time
import argparse

def run_cmd(cmd, check=True):
    print(f"Executing: {' '.join(cmd)}")
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print(f"Error executing command: {res.stderr.strip()}")
        if check:
            sys.exit(res.returncode)
    else:
        if res.stdout:
            print(res.stdout.strip())
    return res

def wait_for_healthy(container_name, timeout=120):
    print(f"Waiting for {container_name} to become healthy...", flush=True)
    start_time = time.time()
    while time.time() - start_time < timeout:
        res = subprocess.run(["docker", "inspect", "--format", "{{.State.Health.Status}}", container_name], capture_output=True, text=True)
        status = res.stdout.strip()
        if status == "healthy":
            print(f"{container_name} is HEALTHY.", flush=True)
            return True
        time.sleep(5)
    print(f"WARNING: Timeout waiting for {container_name} to become healthy. Continuing anyway...")
    return False

def process_wg_config(src_path, dest_path):
    print(f"Waiting for WG config file: {src_path} ...", flush=True)
    for _ in range(60):
        if os.path.exists(src_path):
            break
        time.sleep(1)
    if not os.path.exists(src_path):
        print(f"Error: WG config file {src_path} not found.")
        return False
    
    with open(src_path, "r") as f:
        lines = f.readlines()
    filtered = []
    for line in lines:
        if "ListenPort" not in line:
            filtered.append(line)
            
    with open(dest_path, "w") as f:
        f.writelines(filtered)
    print(f"Processed and wrote: {dest_path}")
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
        print(f"Processed credentials in {dest_dir}")

def provision_lab1(base_dir, script_path):
    print("\nProvisioning Lab 1 (oscp-network-pivot-lab)...")
    run_cmd(["docker", "exec", "perimeter-nginx-ui", "sh", "-c", "echo 'OSCP{foothold_perimeter_breached}' > /var/flag.txt"], check=False)
    run_cmd(["docker", "exec", "perimeter-nginx-ui", "sh", "-c", "echo 'ad_audit_user:AuditServicePass2026!' > /tmp/domain_hint.txt"], check=False)
    run_cmd(["docker", "cp", script_path, "ad-forest-parent:/tmp/configure_ad.py"])
    run_cmd(["docker", "exec", "ad-forest-parent", "python3", "/tmp/configure_ad.py", "--role", "parent", "--realm", "MEGACORP.LOCAL"])
    run_cmd(["docker", "cp", script_path, "ad-forest-child:/tmp/configure_ad.py"])
    practice_users_l1 = "j.smith r.jones m.brown t.taylor d.miller j.wilson b.moore s.taylor a.anderson k.thomas c.jackson m.white l.harris e.martin r.clark s.lewis g.robinson j.walker k.young p.allen"
    run_cmd(["docker", "exec", "ad-forest-child", "python3", "/tmp/configure_ad.py", "--role", "child", "--realm", "HQ.MEGACORP.LOCAL", "--practice-users", practice_users_l1])
    process_generated_creds("ad-forest-child", os.path.join(base_dir, "oscp-network-pivot-lab", "oscp_exam_assets"))

def provision_lab2(base_dir, script_path):
    print("\nProvisioning Lab 2 (multi-domain-forest-lab)...")
    run_cmd(["docker", "cp", script_path, "mega-dc-parent:/tmp/configure_ad.py"])
    run_cmd(["docker", "exec", "mega-dc-parent", "python3", "/tmp/configure_ad.py", "--role", "parent", "--realm", "MEGACORP.LOCAL"])
    run_cmd(["docker", "cp", script_path, "mega-dc-child:/tmp/configure_ad.py"])
    practice_users_l2 = "j.doe a.smith b.gates l.torvalds s.jobs"
    run_cmd(["docker", "exec", "mega-dc-child", "python3", "/tmp/configure_ad.py", "--role", "child", "--realm", "HQ.MEGACORP.LOCAL", "--practice-users", practice_users_l2])
    process_generated_creds("mega-dc-child", os.path.join(base_dir, "multi-domain-forest-lab"))
    run_cmd(["docker", "cp", script_path, "mega-dc-tree:/tmp/configure_ad.py"])
    run_cmd(["docker", "exec", "mega-dc-tree", "python3", "/tmp/configure_ad.py", "--role", "tree", "--realm", "CYBERTECH.LOCAL"])

def provision_lab3(base_dir, script_path):
    print("\nProvisioning Lab 3 (adcs-abuse-lab)...")
    run_cmd(["docker", "cp", script_path, "adcs-dc:/tmp/configure_ad.py"])
    run_cmd(["docker", "exec", "adcs-dc", "python3", "/tmp/configure_ad.py", "--role", "parent", "--realm", "ADCSLAB.LOCAL"])
    run_cmd(["docker", "exec", "adcs-dc", "samba-tool", "user", "create", "j.doe", "StudentPass2026!", "--realm=ADCSLAB.LOCAL", "--configfile=/samba/etc/smb.conf"], check=False)
    run_cmd(["docker", "exec", "adcs-dc", "samba-tool", "user", "setpassword", "Administrator", "--newpassword=ADCSLabAdminPass2026!", "--configfile=/samba/etc/smb.conf"])
    run_cmd(["docker", "exec", "adcs-dc", "mkdir", "-p", "/tmp/ca"])

def provision_lab4(base_dir, script_path):
    print("\nProvisioning Lab 4 (trust-pivoting-lab)...")
    run_cmd(["docker", "cp", script_path, "dc-foresta:/tmp/configure_ad.py"])
    run_cmd(["docker", "exec", "dc-foresta", "python3", "/tmp/configure_ad.py", "--role", "parent", "--realm", "FORESTA.LOCAL"])
    run_cmd(["docker", "cp", script_path, "dc-forestb:/tmp/configure_ad.py"])
    run_cmd(["docker", "exec", "dc-forestb", "python3", "/tmp/configure_ad.py", "--role", "parent", "--realm", "FORESTB.LOCAL"])
    run_cmd(["docker", "exec", "dc-foresta", "samba-tool", "user", "setpassword", "Administrator", "--newpassword=ForestAAdminPass2026!", "--configfile=/samba/etc/smb.conf"])
    run_cmd(["docker", "exec", "dc-forestb", "samba-tool", "user", "setpassword", "Administrator", "--newpassword=ForestBAdminPass2026!", "--configfile=/samba/etc/smb.conf"])
    run_cmd(["docker", "exec", "dc-forestb", "samba-tool", "user", "create", "student", "SimpleStudentPass2026!", "--realm=FORESTB.LOCAL", "--configfile=/samba/etc/smb.conf"], check=False)
    run_cmd([
        "docker", "exec", "dc-foresta", "samba-tool", "domain", "trust", "create", "forestb.local",
        "--type=external", "--direction=both", "--create-location=both",
        "--password=TrustPassword2026!", "-U", "Administrator@FORESTB.LOCAL%ForestBAdminPass2026!",
        "--local-dc-username=Administrator@FORESTA.LOCAL", "--local-dc-password=ForestAAdminPass2026!",
        "--configfile=/samba/etc/smb.conf"
    ], check=False)

def provision_lab5(base_dir, script_path):
    print("\nProvisioning Lab 5 (gpo-admin-pivot-lab)...")
    run_cmd(["docker", "cp", script_path, "gpo-dc:/tmp/configure_ad.py"])
    run_cmd(["docker", "exec", "gpo-dc", "python3", "/tmp/configure_ad.py", "--role", "parent", "--realm", "GPOLAB.LOCAL"])
    run_cmd(["docker", "exec", "gpo-dc", "samba-tool", "user", "setpassword", "Administrator", "--newpassword=GPOLabAdminPass2026!", "--configfile=/samba/etc/smb.conf"])
    run_cmd(["docker", "exec", "gpo-dc", "samba-tool", "user", "create", "operator", "OperatorPass2026!", "--realm=GPOLAB.LOCAL", "--configfile=/samba/etc/smb.conf"], check=False)
    run_cmd(["docker", "exec", "gpo-dc", "mkdir", "-p", "/samba/state/sysvol/gpolab.local/scripts"])
    run_cmd(["docker", "exec", "gpo-dc", "chmod", "-R", "777", "/samba/state/sysvol/gpolab.local/scripts"])
    run_cmd(["docker", "exec", "gpo-dc", "sh", "-c", "echo '#!/bin/sh\necho \"System update checked\"' > /samba/state/sysvol/gpolab.local/scripts/update.sh"])
    run_cmd(["docker", "exec", "gpo-dc", "chmod", "+x", "/samba/state/sysvol/gpolab.local/scripts/update.sh"])

def provision_lab6(base_dir, script_path):
    print("\nProvisioning Lab 6 (rbcd-lab)...")
    run_cmd(["docker", "cp", "rbcd-lab/configure_rbcd.py", "rbcd-dc:/tmp/configure_rbcd.py"])
    run_cmd(["docker", "exec", "rbcd-dc", "python3", "/tmp/configure_rbcd.py"])
    run_cmd(["docker", "exec", "rbcd-dc", "samba-tool", "user", "setpassword", "Administrator", "--newpassword=RBCDAccessAdminPass2026!", "--configfile=/samba/etc/smb.conf"])

def provision_lab7(base_dir, script_path):
    print("\nProvisioning Lab 7 (sql-pivot-lab)...")
    run_cmd(["docker", "cp", "sql-pivot-lab/configure_sql.py", "sql-dc:/tmp/configure_sql.py"])
    run_cmd(["docker", "exec", "sql-dc", "python3", "/tmp/configure_sql.py"])
    run_cmd(["docker", "exec", "sql-dc", "samba-tool", "user", "setpassword", "Administrator", "--newpassword=SQLPivotAdminPass2026!", "--configfile=/samba/etc/smb.conf"])

def provision_lab8(base_dir, script_path):
    print("\nProvisioning Lab 8 (laps-lab)...")
    run_cmd(["docker", "cp", "laps-lab/configure_laps.py", "laps-dc:/tmp/configure_laps.py"])
    run_cmd(["docker", "exec", "laps-dc", "python3", "/tmp/configure_laps.py"])
    run_cmd(["docker", "exec", "laps-dc", "samba-tool", "user", "setpassword", "Administrator", "--newpassword=LAPSAdminPass2026!", "--configfile=/samba/etc/smb.conf"])

def provision_lab9(base_dir, script_path):
    print("\nProvisioning Lab 9 (esc8-relay-lab)...")
    run_cmd(["docker", "cp", "esc8-relay-lab/configure_esc8.py", "esc8-dc:/tmp/configure_esc8.py"])
    run_cmd(["docker", "exec", "esc8-dc", "python3", "/tmp/configure_esc8.py"])
    run_cmd(["docker", "exec", "esc8-dc", "samba-tool", "user", "setpassword", "Administrator", "--newpassword=ESC8AdminPass2026!", "--configfile=/samba/etc/smb.conf"])

def provision_lab10(base_dir, script_path):
    print("\nProvisioning Lab 10 (delegation-s4u-lab)...")
    run_cmd(["docker", "cp", "delegation-s4u-lab/configure_delegation.py", "deleg-dc:/tmp/configure_delegation.py"])
    run_cmd(["docker", "exec", "deleg-dc", "python3", "/tmp/configure_delegation.py"])
    run_cmd(["docker", "exec", "deleg-dc", "samba-tool", "user", "setpassword", "Administrator", "--newpassword=DelegationAdminPass2026!", "--configfile=/samba/etc/smb.conf"])

def deploy_lab(lab, base_dir, script_path):
    print(f"\n==========================================")
    print(f"Deploying & Provisioning: {lab['dir']}")
    print(f"==========================================")
    
    # 1. Compose Up
    os.chdir(os.path.join(base_dir, lab["dir"]))
    run_cmd(["docker", "compose", "up", "-d"])
    os.chdir(base_dir)
    
    # 2. Wait for DCs to be healthy
    for dc in lab["dcs"]:
        wait_for_healthy(dc)
        
    print("Sleeping 5s for services stabilization...", flush=True)
    time.sleep(5)
    
    # 3. Provisioning
    lab["prov_fn"](base_dir, script_path)
    
    # 4. WireGuard config export
    for wg_src_sub, wg_dest_name in lab["wg"]:
        src_path = os.path.join(base_dir, lab["dir"], wg_src_sub, "peer1", "peer1.conf")
        dest_path = os.path.join(base_dir, lab["dir"], wg_dest_name)
        process_wg_config(src_path, dest_path)
        
    print(f"\n>>> SUCCESS: {lab['dir']} is fully deployed and provisioned.")

def stop_lab(lab, base_dir):
    print(f"\nStopping lab: {lab['dir']}...")
    os.chdir(os.path.join(base_dir, lab["dir"]))
    run_cmd(["docker", "compose", "down"])
    os.chdir(base_dir)

def clean_lab(lab, base_dir):
    print(f"\nCleaning (removing volumes) lab: {lab['dir']}...")
    os.chdir(os.path.join(base_dir, lab["dir"]))
    run_cmd(["docker", "compose", "down", "-v"])
    os.chdir(base_dir)

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

    # If any arguments are provided, use non-interactive mode
    has_args = any([args.all, args.lab, args.stop_all, args.stop, args.clean_all, args.clean])

    if has_args:
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
                print(f"Error: Lab '{target}' not found.")
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
                print(f"Error: Lab '{target}' not found.")
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
                print(f"Error: Lab '{target}' not found.")
                sys.exit(1)
        return

    # Interactive CLI Menu
    while True:
        print("\n=======================================================")
        print("=== UNIFIED OSCP / OSCP+ AD LABS MANAGER ===")
        print("=======================================================")
        print("1) Deploy & Provision ALL 10 labs (Warning: Resource Intensive)")
        print("2) Select a specific lab to Deploy & Provision")
        print("3) Stop ALL active labs")
        print("4) Stop a specific active lab")
        print("5) Clean ALL labs (Stop & Remove local docker volumes)")
        print("6) Clean a specific lab (Stop & Remove volumes)")
        print("7) Exit")
        
        choice = input("Enter choice (1-7): ").strip()
        
        if choice == "1":
            confirm = input("Are you sure you want to run all 10 labs? This requires significant RAM. (y/n): ").strip().lower()
            if confirm == 'y':
                for lab in labs_def:
                    deploy_lab(lab, base_dir, script_path)
        elif choice == "2":
            print("\nAvailable Labs:")
            for lab in labs_def:
                print(f"{lab['index']}. {lab['dir']}")
            lab_choice = input(f"Enter lab index (1-{len(labs_def)}): ").strip()
            matched = None
            for lab in labs_def:
                if lab_choice.isdigit() and int(lab_choice) == lab["index"]:
                    matched = lab
                    break
            if matched:
                deploy_lab(matched, base_dir, script_path)
            else:
                print("Invalid selection.")
        elif choice == "3":
            for lab in labs_def:
                stop_lab(lab, base_dir)
        elif choice == "4":
            print("\nActive Labs:")
            for lab in labs_def:
                print(f"{lab['index']}. {lab['dir']}")
            lab_choice = input(f"Enter lab index to stop (1-{len(labs_def)}): ").strip()
            matched = None
            for lab in labs_def:
                if lab_choice.isdigit() and int(lab_choice) == lab["index"]:
                    matched = lab
                    break
            if matched:
                stop_lab(matched, base_dir)
            else:
                print("Invalid selection.")
        elif choice == "5":
            confirm = input("This will destroy all databases and AD states for all labs. Proceed? (y/n): ").strip().lower()
            if confirm == 'y':
                for lab in labs_def:
                    clean_lab(lab, base_dir)
        elif choice == "6":
            print("\nAvailable Labs:")
            for lab in labs_def:
                print(f"{lab['index']}. {lab['dir']}")
            lab_choice = input(f"Enter lab index to clean (1-{len(labs_def)}): ").strip()
            matched = None
            for lab in labs_def:
                if lab_choice.isdigit() and int(lab_choice) == lab["index"]:
                    matched = lab
                    break
            if matched:
                clean_lab(matched, base_dir)
            else:
                print("Invalid selection.")
        elif choice == "7":
            print("Exiting...")
            break
        else:
            print("Invalid option. Please try again.")

if __name__ == '__main__':
    main()
