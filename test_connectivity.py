import socket
import subprocess
import sys
import argparse


GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"

LABS = [
    {
        "index": 1,
        "name": "oscp-network-pivot-lab",
        "vpn_port": "51820/UDP",
        "vpn_profile": "oscp-pivot-lab.conf",
        "targets": [
            {"name": "Perimeter Web UI", "ip": "10.10.10.80", "port": 80, "protocol": "TCP"},
            {"name": "Postgres Database", "ip": "10.20.20.20", "port": 5432, "protocol": "TCP"},
            {"name": "Parent Domain Controller (MEGACORP.LOCAL)", "ip": "10.100.10.10", "port": 445, "protocol": "TCP"},
            {"name": "Child Domain Controller (HQ.MEGACORP.LOCAL)", "ip": "10.100.20.10", "port": 389, "protocol": "TCP"}
        ],
        "containers": ["perimeter-nginx-ui", "internal-postgres-db", "ad-forest-parent", "ad-forest-child"]
    },
    {
        "index": 2,
        "name": "multi-domain-forest-lab",
        "vpn_port": "51821/UDP",
        "vpn_profile": "multi-domain-forest-lab.conf",
        "targets": [
            {"name": "Parent DC (MEGACORP.LOCAL)", "ip": "10.101.10.10", "port": 445, "protocol": "TCP"},
            {"name": "Child DC (HQ.MEGACORP.LOCAL)", "ip": "10.101.20.10", "port": 389, "protocol": "TCP"},
            {"name": "Tree DC (CYBERTECH.LOCAL)", "ip": "10.101.30.10", "port": 88, "protocol": "TCP"}
        ],
        "containers": ["mega-dc-parent", "mega-dc-child", "mega-dc-tree"]
    },
    {
        "index": 3,
        "name": "adcs-abuse-lab",
        "vpn_port": "51822/UDP",
        "vpn_profile": "oscp-adcs-lab.conf",
        "targets": [
            {"name": "Domain Controller (ADCSLAB.LOCAL)", "ip": "10.102.10.10", "port": 445, "protocol": "TCP"},
            {"name": "CA Mock Enrollment Web", "ip": "10.102.20.20", "port": 80, "protocol": "TCP"}
        ],
        "containers": ["adcs-dc", "adcs-ca-mock"]
    },
    {
        "index": 4,
        "name": "trust-pivoting-lab",
        "vpn_port": "51823/UDP",
        "vpn_profile": "oscp-trust-lab.conf",
        "targets": [
            {"name": "Forest A DC (FORESTA.LOCAL)", "ip": "10.103.10.10", "port": 445, "protocol": "TCP"},
            {"name": "Forest B DC (FORESTB.LOCAL)", "ip": "10.103.20.10", "port": 389, "protocol": "TCP"},
            {"name": "WinRM Target Machine", "ip": "10.103.20.20", "port": 5985, "protocol": "TCP"}
        ],
        "containers": ["dc-foresta", "dc-forestb", "trust-winrm-target"]
    },
    {
        "index": 5,
        "name": "gpo-admin-pivot-lab",
        "vpn_port": "51824/UDP",
        "vpn_profile": "oscp-gpo-lab.conf",
        "targets": [
            {"name": "Domain Controller (GPOLAB.LOCAL)", "ip": "10.104.10.10", "port": 445, "protocol": "TCP"}
        ],
        "containers": ["gpo-dc", "gpo-client-sim"]
    },
    {
        "index": 6,
        "name": "rbcd-lab",
        "vpn_port": "51825/UDP",
        "vpn_profile": "oscp-rbcd-lab.conf",
        "targets": [
            {"name": "Domain Controller (RBCDLAB.LOCAL)", "ip": "10.105.10.10", "port": 445, "protocol": "TCP"},
            {"name": "RBCD Target Server SSH", "ip": "10.105.20.20", "port": 22, "protocol": "TCP"}
        ],
        "containers": ["rbcd-dc", "rbcd-target-srv"]
    },
    {
        "index": 7,
        "name": "sql-pivot-lab",
        "vpn_port": "51826/UDP",
        "vpn_profile": "oscp-sql-lab.conf",
        "targets": [
            {"name": "Domain Controller (SQLPIVOT.LOCAL)", "ip": "10.106.10.10", "port": 445, "protocol": "TCP"},
            {"name": "Frontend Database (PostgreSQL)", "ip": "10.106.20.20", "port": 5432, "protocol": "TCP"},
            {"name": "Backend Database (PostgreSQL)", "ip": "10.106.10.20", "port": 5432, "protocol": "TCP"}
        ],
        "containers": ["sql-dc", "sql-front", "sql-back"]
    },
    {
        "index": 8,
        "name": "laps-lab",
        "vpn_port": "51827/UDP",
        "vpn_profile": "oscp-laps-lab.conf",
        "targets": [
            {"name": "Domain Controller (LAPSLAB.LOCAL)", "ip": "10.107.10.10", "port": 445, "protocol": "TCP"},
            {"name": "LAPS Target Server SSH", "ip": "10.107.20.20", "port": 22, "protocol": "TCP"}
        ],
        "containers": ["laps-dc", "laps-finance-srv"]
    },
    {
        "index": 9,
        "name": "esc8-relay-lab",
        "vpn_port": "51828/UDP",
        "vpn_profile": "oscp-esc8-lab.conf",
        "targets": [
            {"name": "Domain Controller (ESC8LAB.LOCAL)", "ip": "10.108.10.10", "port": 445, "protocol": "TCP"},
            {"name": "Web CA ADCS Enrollment", "ip": "10.108.20.20", "port": 80, "protocol": "TCP"}
        ],
        "containers": ["esc8-dc", "esc8-ca-web"]
    },
    {
        "index": 10,
        "name": "delegation-s4u-lab",
        "vpn_port": "51829/UDP",
        "vpn_profile": "oscp-delegation-lab.conf",
        "targets": [
            {"name": "Domain Controller (DELEGATELAB.LOCAL)", "ip": "10.109.10.10", "port": 445, "protocol": "TCP"},
            {"name": "Database Server SSH", "ip": "10.109.20.20", "port": 22, "protocol": "TCP"}
        ],
        "containers": ["deleg-dc", "deleg-db"]
    }
]

def check_container_status(container_name):
    """Checks the status and health of a docker container."""
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
    """Tests if a TCP port is open."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        s.connect((ip, port))
        s.close()
        return True
    except Exception:
        return False

def show_banner():
    banner = f"""{CYAN}{BOLD}
======================================================
     AD Pentesting Labs Suite Connectivity Tester
======================================================{RESET}"""
    print(banner)

def main():
    parser = argparse.ArgumentParser(description="AD Labs Connectivity Tester")
    parser.add_argument("--lab", type=str, help="Test a specific lab (1-10 index or folder name)")
    args = parser.parse_args()

    show_banner()
    
    selected_labs = LABS
    if args.lab:
        target = args.lab.strip()
        matched = []
        for lab in LABS:
            if target.isdigit() and int(target) == lab["index"]:
                matched.append(lab)
                break
            elif lab["name"] == target:
                matched.append(lab)
                break
        if matched:
            selected_labs = matched
        else:
            print(f"{RED}[x] Lab '{target}' not found.{RESET}")
            sys.exit(1)

    for lab in selected_labs:
        print(f"\n{BOLD}{CYAN}------------------------------------------------------{RESET}")
        print(f"{BOLD}🧪 Lab {lab['index']}: {lab['name']}{RESET}")
        print(f"   🔑 WG Port: {lab['vpn_port']} | Profile: {lab['vpn_profile']}")
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
            print(f"  python run_provisioning.py --lab {lab['index']}")
        
       
        print(f"\n{BOLD}[*] VPN Socket Connectivity (Attacker Host -> Lab Services):{RESET}")
        for target in lab["targets"]:
            success = test_port(target["ip"], target["port"])
            if success:
                print(f"  [+] {target['name']:<40} ({target['ip']}:{target['port']}): {GREEN}SUCCESS (Connected!){RESET}")
            else:
                print(f"  [-] {target['name']:<40} ({target['ip']}:{target['port']}): {RED}FAILED (Unreachable){RESET}")
                
        print(f"  {YELLOW}ℹ️  If connection failed, make sure your WireGuard Client is connected to '{lab['vpn_profile']}'{RESET}")

if __name__ == "__main__":
    main()
