import subprocess
import os
import sys
import time

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

def main():
    print("=== UNIFIED OSCP / OSCP+ AD LABS PROVISIONING MANAGER ===")
    base_dir = os.getcwd()
    script_name = "configure_ad.py"
    script_path = os.path.join(base_dir, script_name)

    labs = [
        ("oscp-network-pivot-lab", ["ad-forest-parent", "ad-forest-child"]),
        ("multi-domain-forest-lab", ["mega-dc-parent", "mega-dc-child", "mega-dc-tree"]),
        ("adcs-abuse-lab", ["adcs-dc"]),
        ("trust-pivoting-lab", ["dc-foresta", "dc-forestb"]),
        ("gpo-admin-pivot-lab", ["gpo-dc"]),
        ("rbcd-lab", ["rbcd-dc"]),
        ("sql-pivot-lab", ["sql-dc"]),
        ("laps-lab", ["laps-dc"]),
        ("esc8-relay-lab", ["esc8-dc"]),
        ("delegation-s4u-lab", ["deleg-dc"])
    ]

    print("\n--- 1. STARTING ALL DOCKER COMPOSE STACKS ---")
    for lab_dir, _ in labs:
        print(f"\nStarting {lab_dir}...")
        os.chdir(os.path.join(base_dir, lab_dir))
        run_cmd(["docker", "compose", "up", "-d"])
        
    os.chdir(base_dir)

    print("\n--- 2. WAITING FOR DOMAIN CONTROLLERS TO RUN ---")
    for _, dc_containers in labs:
        for dc in dc_containers:
            wait_for_healthy(dc)

    print("Sleeping 10s extra for services initialization...", flush=True)
    time.sleep(10)

    print("\n--- 3. PROVISIONING ACTIVE DIRECTORY CONTROLLERS ---")

    # Lab 1
    print("\nProvisioning Lab 1 (oscp-network-pivot-lab)...")
    run_cmd(["docker", "exec", "perimeter-nginx-ui", "sh", "-c", "echo 'OSCP{foothold_perimeter_breached}' > /var/flag.txt"], check=False)
    run_cmd(["docker", "exec", "perimeter-nginx-ui", "sh", "-c", "echo 'ad_audit_user:AuditServicePass2026!' > /tmp/domain_hint.txt"], check=False)
    run_cmd(["docker", "cp", script_path, "ad-forest-parent:/tmp/configure_ad.py"])
    run_cmd(["docker", "exec", "ad-forest-parent", "python3", "/tmp/configure_ad.py", "--role", "parent", "--realm", "MEGACORP.LOCAL"])
    run_cmd(["docker", "cp", script_path, "ad-forest-child:/tmp/configure_ad.py"])
    practice_users_l1 = "j.smith r.jones m.brown t.taylor d.miller j.wilson b.moore s.taylor a.anderson k.thomas c.jackson m.white l.harris e.martin r.clark s.lewis g.robinson j.walker k.young p.allen"
    run_cmd(["docker", "exec", "ad-forest-child", "python3", "/tmp/configure_ad.py", "--role", "child", "--realm", "HQ.MEGACORP.LOCAL", "--practice-users", practice_users_l1])
    process_generated_creds("ad-forest-child", os.path.join(base_dir, "oscp-network-pivot-lab", "oscp_exam_assets"))

    # Lab 2
    print("\nProvisioning Lab 2 (multi-domain-forest-lab)...")
    run_cmd(["docker", "cp", script_path, "mega-dc-parent:/tmp/configure_ad.py"])
    run_cmd(["docker", "exec", "mega-dc-parent", "python3", "/tmp/configure_ad.py", "--role", "parent", "--realm", "MEGACORP.LOCAL"])
    run_cmd(["docker", "cp", script_path, "mega-dc-child:/tmp/configure_ad.py"])
    practice_users_l2 = "j.doe a.smith b.gates l.torvalds s.jobs"
    run_cmd(["docker", "exec", "mega-dc-child", "python3", "/tmp/configure_ad.py", "--role", "child", "--realm", "HQ.MEGACORP.LOCAL", "--practice-users", practice_users_l2])
    process_generated_creds("mega-dc-child", os.path.join(base_dir, "multi-domain-forest-lab"))
    run_cmd(["docker", "cp", script_path, "mega-dc-tree:/tmp/configure_ad.py"])
    run_cmd(["docker", "exec", "mega-dc-tree", "python3", "/tmp/configure_ad.py", "--role", "tree", "--realm", "CYBERTECH.LOCAL"])

    # Lab 3
    print("\nProvisioning Lab 3 (adcs-abuse-lab)...")
    run_cmd(["docker", "cp", script_path, "adcs-dc:/tmp/configure_ad.py"])
    run_cmd(["docker", "exec", "adcs-dc", "python3", "/tmp/configure_ad.py", "--role", "parent", "--realm", "ADCSLAB.LOCAL"])
    run_cmd(["docker", "exec", "adcs-dc", "samba-tool", "user", "create", "j.doe", "StudentPass2026!", "--realm=ADCSLAB.LOCAL", "--configfile=/samba/etc/smb.conf"], check=False)
    run_cmd(["docker", "exec", "adcs-dc", "samba-tool", "user", "setpassword", "Administrator", "--newpassword=ADCSLabAdminPass2026!", "--configfile=/samba/etc/smb.conf"])
    run_cmd(["docker", "exec", "adcs-dc", "mkdir", "-p", "/tmp/ca"])

    # Lab 4
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

    # Lab 5
    print("\nProvisioning Lab 5 (gpo-admin-pivot-lab)...")
    run_cmd(["docker", "cp", script_path, "gpo-dc:/tmp/configure_ad.py"])
    run_cmd(["docker", "exec", "gpo-dc", "python3", "/tmp/configure_ad.py", "--role", "parent", "--realm", "GPOLAB.LOCAL"])
    run_cmd(["docker", "exec", "gpo-dc", "samba-tool", "user", "setpassword", "Administrator", "--newpassword=GPOLabAdminPass2026!", "--configfile=/samba/etc/smb.conf"])
    run_cmd(["docker", "exec", "gpo-dc", "samba-tool", "user", "create", "operator", "OperatorPass2026!", "--realm=GPOLAB.LOCAL", "--configfile=/samba/etc/smb.conf"], check=False)
    run_cmd(["docker", "exec", "gpo-dc", "mkdir", "-p", "/samba/state/sysvol/gpolab.local/scripts"])
    run_cmd(["docker", "exec", "gpo-dc", "chmod", "-R", "777", "/samba/state/sysvol/gpolab.local/scripts"])
    run_cmd(["docker", "exec", "gpo-dc", "sh", "-c", "echo '#!/bin/sh\necho \"System update checked\"' > /samba/state/sysvol/gpolab.local/scripts/update.sh"])
    run_cmd(["docker", "exec", "gpo-dc", "chmod", "+x", "/samba/state/sysvol/gpolab.local/scripts/update.sh"])

    # Lab 6
    print("\nProvisioning Lab 6 (rbcd-lab)...")
    run_cmd(["docker", "cp", "rbcd-lab/configure_rbcd.py", "rbcd-dc:/tmp/configure_rbcd.py"])
    run_cmd(["docker", "exec", "rbcd-dc", "python3", "/tmp/configure_rbcd.py"])
    run_cmd(["docker", "exec", "rbcd-dc", "samba-tool", "user", "setpassword", "Administrator", "--newpassword=RBCDAccessAdminPass2026!", "--configfile=/samba/etc/smb.conf"])

    # Lab 7
    print("\nProvisioning Lab 7 (sql-pivot-lab)...")
    run_cmd(["docker", "cp", "sql-pivot-lab/configure_sql.py", "sql-dc:/tmp/configure_sql.py"])
    run_cmd(["docker", "exec", "sql-dc", "python3", "/tmp/configure_sql.py"])
    run_cmd(["docker", "exec", "sql-dc", "samba-tool", "user", "setpassword", "Administrator", "--newpassword=SQLPivotAdminPass2026!", "--configfile=/samba/etc/smb.conf"])

    # Lab 8
    print("\nProvisioning Lab 8 (laps-lab)...")
    run_cmd(["docker", "cp", "laps-lab/configure_laps.py", "laps-dc:/tmp/configure_laps.py"])
    run_cmd(["docker", "exec", "laps-dc", "python3", "/tmp/configure_laps.py"])
    run_cmd(["docker", "exec", "laps-dc", "samba-tool", "user", "setpassword", "Administrator", "--newpassword=LAPSAdminPass2026!", "--configfile=/samba/etc/smb.conf"])

    # Lab 9
    print("\nProvisioning Lab 9 (esc8-relay-lab)...")
    run_cmd(["docker", "cp", "esc8-relay-lab/configure_esc8.py", "esc8-dc:/tmp/configure_esc8.py"])
    run_cmd(["docker", "exec", "esc8-dc", "python3", "/tmp/configure_esc8.py"])
    run_cmd(["docker", "exec", "esc8-dc", "samba-tool", "user", "setpassword", "Administrator", "--newpassword=ESC8AdminPass2026!", "--configfile=/samba/etc/smb.conf"])

    # Lab 10
    print("\nProvisioning Lab 10 (delegation-s4u-lab)...")
    run_cmd(["docker", "cp", "delegation-s4u-lab/configure_delegation.py", "deleg-dc:/tmp/configure_delegation.py"])
    run_cmd(["docker", "exec", "deleg-dc", "python3", "/tmp/configure_delegation.py"])
    run_cmd(["docker", "exec", "deleg-dc", "samba-tool", "user", "setpassword", "Administrator", "--newpassword=DelegationAdminPass2026!", "--configfile=/samba/etc/smb.conf"])

    print("\n--- 4. EXPORTING AND CLEANING WIREGUARD VPN CONFIGURATIONS ---")
    process_wg_config(
        os.path.join(base_dir, "oscp-network-pivot-lab", "wireguard_oscp", "peer1", "peer1.conf"),
        os.path.join(base_dir, "oscp-network-pivot-lab", "oscp-pivot-lab.conf")
    )
    process_wg_config(
        os.path.join(base_dir, "multi-domain-forest-lab", "wireguard_forest", "peer1", "peer1.conf"),
        os.path.join(base_dir, "multi-domain-forest-lab", "multi-domain-forest-lab.conf")
    )
    process_wg_config(
        os.path.join(base_dir, "adcs-abuse-lab", "wireguard_adcs", "peer1", "peer1.conf"),
        os.path.join(base_dir, "adcs-abuse-lab", "oscp-adcs-lab.conf")
    )
    process_wg_config(
        os.path.join(base_dir, "trust-pivoting-lab", "wireguard_trust", "peer1", "peer1.conf"),
        os.path.join(base_dir, "trust-pivoting-lab", "oscp-trust-lab.conf")
    )
    process_wg_config(
        os.path.join(base_dir, "gpo-admin-pivot-lab", "wireguard_gpo", "peer1", "peer1.conf"),
        os.path.join(base_dir, "gpo-admin-pivot-lab", "oscp-gpo-lab.conf")
    )
    process_wg_config(
        os.path.join(base_dir, "rbcd-lab", "wireguard_rbcd", "peer1", "peer1.conf"),
        os.path.join(base_dir, "rbcd-lab", "oscp-rbcd-lab.conf")
    )
    process_wg_config(
        os.path.join(base_dir, "sql-pivot-lab", "wireguard_sql", "peer1", "peer1.conf"),
        os.path.join(base_dir, "sql-pivot-lab", "oscp-sql-lab.conf")
    )
    process_wg_config(
        os.path.join(base_dir, "laps-lab", "wireguard_laps", "peer1", "peer1.conf"),
        os.path.join(base_dir, "laps-lab", "oscp-laps-lab.conf")
    )
    process_wg_config(
        os.path.join(base_dir, "esc8-relay-lab", "wireguard_esc8", "peer1", "peer1.conf"),
        os.path.join(base_dir, "esc8-relay-lab", "oscp-esc8-lab.conf")
    )
    process_wg_config(
        os.path.join(base_dir, "delegation-s4u-lab", "wireguard_deleg", "peer1", "peer1.conf"),
        os.path.join(base_dir, "delegation-s4u-lab", "oscp-delegation-lab.conf")
    )

    print("\n=== PROVISIONING COMPLETED FOR ALL 10 LABS ===")

if __name__ == '__main__':
    main()
