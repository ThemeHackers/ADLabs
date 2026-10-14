# ADLabs: Active Directory Pentesting Suite

[![Docker](https://img.shields.io/badge/Docker-20.10%2B-2496ED?logo=docker&logoColor=white)](https://www.docker.com/)
[![Docker Compose](https://img.shields.io/badge/Docker%20Compose-v2-2496ED?logo=docker&logoColor=white)](https://docs.docker.com/compose/)
[![Python](https://img.shields.io/badge/Python-3.8%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![WireGuard](https://img.shields.io/badge/VPN-WireGuard-88171A?logo=wireguard&logoColor=white)](https://www.wireguard.com/)
[![Labs](https://img.shields.io/badge/Labs-12%20Scenarios-brightgreen)](#lab-scenarios--attack-vectors)
[![OSCP](https://img.shields.io/badge/OSCP%20Mock%20Exam-24h%20Simulator-orange)](#oscp-mock-exam-simulator)

A lightweight, containerized Active Directory laboratory suite engineered specifically for **OSCP (PEN-200)**, **OSCP+**, and enterprise red team preparation.

ADLabs replaces heavy, resource-draining Windows Virtual Machines with Samba Active Directory Domain Controllers, Debian routers, authentic web application footholds, WinRM simulation services, and dedicated WireGuard VPN gateways running entirely inside Docker containers.

---

> [!IMPORTANT]
> **Educational and Authorized Use Only**  
> These labs are intentionally configured with security misconfigurations for educational training and skill assessment. Practice only within your local, isolated environment. Never apply these attack techniques against unauthorized targets.

---

## Highlights

- **12 Comprehensive Scenarios**: Real-world Active Directory attack paths covering Kerberos abuse, AD CS exploitation (ESC1/ESC8), LAPS abuse, Cross-Forest External Trusts, Azure AD Connect sync extraction, and SCCM/MECM network pivoting.
- **Full OSCP Exam Kill Chain**: Lab 1 (`oscp-network-pivot-lab`) features an authentic DMZ perimeter web portal with SQLi and unrestricted file upload, low-privilege `www-data` shell (`local.txt`), local privilege escalation to `root` (`proof.txt`), credential discovery, and SSH/Chisel pivoting into the internal Active Directory forest.
- **24-Hour Blind OSCP Mock Exam**: Built-in exam mode that selects random target environments with anonymized identifiers (`TARGET-ALPHA`, `TARGET-BRAVO`, etc.), tracks real-time scores against a 70/100 point passing threshold, and enforces exam-condition hint locks.
- **Dynamic Wordlists & Credential Randomization**: Prevents credential memorization by dynamically generating realistic corporate usernames and passwords across all labs using customizable patterns.
- **Flag Verification & Progressive Hint Engine**: Automated submission and scoring for `local.txt` and `proof.txt` flags, accompanied by a 4-tier progressive hint system (Recon $\rightarrow$ Foothold $\rightarrow$ PrivEsc $\rightarrow$ Pivot/AD).
- **Multi-Lab WinRM Services**: Built-in WSMAN/SOAP WinRM services on port `5985` allowing realistic remote management and credential testing with **Evil-WinRM** and **NetExec (CrackMapExec)**.
- **Cross-Platform Routing**: Centralized VPN tunnel management via CLI (`adlabs connect` / `adlabs disconnect`) on both Linux and Windows.
- **Lightweight Footprint**: Zero hypervisor overhead; each Samba DC requires only ~60–90 MB of memory.
- **Auto-Timeout Daemon**: Automatically halts idle containers after 15 minutes of inactivity or 2 hours of total runtime to prevent resource exhaustion.

---

## Prerequisites

Ensure the following tools are installed on your host machine before starting:

### Required Software

| Software | Minimum Version | Notes |
| :--- | :--- | :--- |
| **Docker Engine** | 20.10+ | Docker Desktop on Windows/macOS or Docker Engine on Linux |
| **Docker Compose** | v2.0+ | Compose plugin (`docker compose`) |
| **Python** | 3.8+ | Standard `python3` runtime |
| **WireGuard Client** | Latest | [Windows](https://www.wireguard.com/install/) \| [Linux (`wireguard-tools`)](https://www.wireguard.com/install/) \| [macOS](https://apps.apple.com/app/wireguard/id1451685025) |

### Recommended Attacking Tools

Access lab targets through your WireGuard connection using standard pentesting toolsets (e.g., Kali Linux or WSL2):

- **Impacket** (`GetUserSPNs.py`, `GetNPUsers.py`, `secretsdump.py`, `getST.py`, `rbcd.py`)
- **NetExec / CrackMapExec** (`nxc smb`, `nxc winrm`, `nxc ldap`)
- **Evil-WinRM** (for Windows Remote Management shell access)
- **Certipy** (for AD CS enumeration and PKINIT authentication)
- **BloodHound / BloodHound.py** (for Active Directory permission graph mapping)
- **Chisel / SSH** (for multi-tier subnet pivoting and port forwarding)
- **Coercer / PetitPotam / PrinterBug** (for authentication coercion)

---

## Installation & Setup

You can run ADLabs directly using the Python standard library, or install it as a package for a clean system-wide `adlabs` command.

### Option 1: Quick Install (Recommended)

Clone the repository and install dependencies in editable mode:

```bash
git clone https://github.com/ThemeHackers/ADLabs.git
cd ADLabs

# Install optional dependencies and CLI entry point
pip install -e .
```

After installation, the `adlabs` command is directly available anywhere in your terminal.

### Option 2: Standalone Execution

Run directly with `python3` without installing:

```bash
python3 adlabs.py
```

---

## Quick Start

### 1. Interactive Dashboard

Launch the interactive terminal dashboard:

```bash
python3 adlabs.py
# Or with installed package:
adlabs
```

The interactive menu allows you to deploy labs, manage VPN tunnels, submit flags, view progressive hints, inspect live status, or launch the 24-hour mock exam simulator.

### 2. Command Line Interface (CLI)

ADLabs supports intuitive subcommands and standard flags:

```bash
# Check status overview of all 12 labs
python3 adlabs.py status

# Deploy a specific lab (e.g., Lab 1)
python3 adlabs.py deploy 1

# Inspect detailed info, initial credentials, and network targets
python3 adlabs.py info 1

# Connect WireGuard tunnel for a lab (Cross-platform)
python3 adlabs.py connect 1

# Disconnect active WireGuard tunnel
python3 adlabs.py disconnect

# Submit a captured flag
python3 adlabs.py submit OSCP{foothold_perimeter_breached}

# View flags progress and scoreboard
python3 adlabs.py flags

# Request progressive hint for a lab (Tier 1-4)
python3 adlabs.py hint 1

# Start or check the 24-Hour OSCP Mock Exam
python3 adlabs.py exam start
python3 adlabs.py exam status
python3 adlabs.py exam stop

# Stop or clean a lab
python3 adlabs.py stop 1
python3 adlabs.py clean 1
```

---

## WireGuard VPN Connectivity

Every lab deployment automatically allocates a dedicated, collision-free WireGuard port (`51820–51831/udp`) and subnet (`10.252.x.0/24`), generating client VPN profiles in `labs/<lab_name>/<profile>.conf` and `output/vpn/`.

### Method A: One-Click CLI Connect (Recommended)

```bash
# Connect to Lab 1
python3 adlabs.py connect 1

# Disconnect
python3 adlabs.py disconnect
```

On Linux, `adlabs connect` invokes `sudo wg-quick up`. On Windows, it automatically prompts for UAC elevation to install the tunnel service.

### Method B: Native Script Helpers

- **Linux**: `./scripts/linux/connect.sh 1` (Disconnect: `./scripts/linux/disconnect.sh 1`)
- **Windows**: `.\connect.bat 1` (Disconnect: `.\disconnect.bat 1`)

### Method C: WireGuard GUI Client

1. Open the WireGuard application.
2. Click **Add Tunnel** / **Import tunnel(s) from file** (`Ctrl + O`).
3. Select the generated `.conf` file from `output/vpn/` (or the lab folder).
4. Click **Activate**.

> [!TIP]
> **Dynamic WAN & Cloud Hosting**: If running ADLabs on a cloud VPS or dynamic IP home lab, automatically detect your public IP or configure a DDNS domain:
> ```bash
> python3 adlabs.py --update-ip
> # Or set a static IP / domain:
> python3 adlabs.py --set-host mylab.duckdns.org
> ```

---

## OSCP Mock Exam Simulator

ADLabs includes a 24-hour blind exam engine designed to recreate realistic OSCP exam conditions:

- **Blind Challenges**: Targets are assigned anonymous codes (`TARGET-ALPHA`, `TARGET-BRAVO`, `TARGET-CHARLIE`) without revealing the underlying vulnerability or attack chain.
- **Passing Threshold**: Calculated based on standard OSCP scoring (70 / 100 points required to pass).
  - External Foothold (`local.txt`): 10 points
  - Local Privilege Escalation (`proof.txt`): 10 points
  - Active Directory Domain Compromise (`proof.txt`): 40 points
- **Exam Integrity**: Progressive hints and walkthroughs are locked during active exam sessions to maintain test authenticity.

```bash
# Start a new 24-hour session
python3 adlabs.py exam start

# Check remaining time and current score
python3 adlabs.py exam status

# Submit flag during exam
python3 adlabs.py submit OSCP{...}

# Stop / forfeit exam
python3 adlabs.py exam stop
```

---

## Lab Architecture & Network Mapping

To prevent port conflicts and cross-contamination, each lab runs on isolated subnets with dedicated WireGuard endpoints:

| # | Lab Directory | Domain / Realm | Target Subnets | Default Port | VPN Profile |
| :-: | :--- | :--- | :--- | :-: | :--- |
| **1** | [`oscp-network-pivot-lab`](./labs/oscp-network-pivot-lab/) | `MEGACORP.LOCAL`<br>`HQ.MEGACORP.LOCAL` | `10.10.10.0/24` (DMZ)<br>`10.20.20.0/24` (Internal)<br>`10.100.10.0/24` (AD) | `51820/udp` | `oscp-pivot-lab.conf` |
| **2** | [`multi-domain-forest-lab`](./labs/multi-domain-forest-lab/) | `MEGACORP.LOCAL`<br>`HQ.MEGACORP.LOCAL`<br>`CYBERTECH.LOCAL` | `10.101.10.0/24` (Parent)<br>`10.101.20.0/24` (Child)<br>`10.101.30.0/24` (Tree) | `51821/udp` | `oscp-forest.conf` |
| **3** | [`adcs-abuse-lab`](./labs/adcs-abuse-lab/) | `ADCSLAB.LOCAL` | `10.102.10.0/24` (AD)<br>`10.102.20.0/24` (CA Web) | `51822/udp` | `oscp-adcs-lab.conf` |
| **4** | [`trust-pivoting-lab`](./labs/trust-pivoting-lab/) | `FORESTA.LOCAL`<br>`FORESTB.LOCAL` | `10.103.10.0/24` (Forest A)<br>`10.103.20.0/24` (Forest B) | `51823/udp` | `oscp-trust-lab.conf` |
| **5** | [`gpo-admin-pivot-lab`](./labs/gpo-admin-pivot-lab/) | `GPOLAB.LOCAL` | `10.104.10.0/24` (AD)<br>`10.104.20.0/24` (Client) | `51824/udp` | `oscp-gpo-lab.conf` |
| **6** | [`rbcd-lab`](./labs/rbcd-lab/) | `RBCDLAB.LOCAL` | `10.105.10.0/24` (AD)<br>`10.105.20.0/24` (Server) | `51825/udp` | `oscp-rbcd-lab.conf` |
| **7** | [`sql-pivot-lab`](./labs/sql-pivot-lab/) | `SQLPIVOT.LOCAL` | `10.106.10.0/24` (AD)<br>`10.106.20.0/24` (SQL) | `51826/udp` | `oscp-sql-lab.conf` |
| **8** | [`laps-lab`](./labs/laps-lab/) | `LAPSLAB.LOCAL` | `10.107.10.0/24` (AD)<br>`10.107.20.0/24` (Server) | `51827/udp` | `oscp-laps-lab.conf` |
| **9** | [`esc8-relay-lab`](./labs/esc8-relay-lab/) | `ESC8LAB.LOCAL` | `10.108.10.0/24` (AD)<br>`10.108.20.0/24` (Web) | `51828/udp` | `oscp-esc8-lab.conf` |
| **10** | [`delegation-s4u-lab`](./labs/delegation-s4u-lab/) | `DELEGATELAB.LOCAL` | `10.109.10.0/24` (AD)<br>`10.109.20.0/24` (DB) | `51829/udp` | `oscp-deleg.conf` |
| **11** | [`hybrid-cloud-aad-lab`](./labs/hybrid-cloud-aad-lab/) | `MEGACORP-CLOUD.LOCAL` | `10.110.10.0/24` (AD)<br>`10.110.20.0/24` (Sync) | `51830/udp` | `oscp-hybrid.conf` |
| **12** | [`sccm-mecm-pivot-lab`](./labs/sccm-mecm-pivot-lab/) | `CORP-MANAGEMENT.LOCAL` | `10.112.10.0/24` (AD)<br>`10.112.20.0/24` (Mgmt) | `51831/udp` | `oscp-sccm-lab.conf` |

---

## Lab Scenarios & Attack Vectors

### Lab 1: OSCP Multi-Tier Network Pivot & Full Attack Loop

- **Domains**: `MEGACORP.LOCAL` / `HQ.MEGACORP.LOCAL`
- **Initial Foothold**: External DMZ Web Gateway at `http://10.10.10.80:80`
- **Attack Chain**:
  1. **Perimeter Foothold**: Enumerate login portal $\rightarrow$ SQL Injection authentication bypass $\rightarrow$ Unrestricted file upload via document drop $\rightarrow$ obtain low-privilege `www-data` shell (`/home/www-data/local.txt`).
  2. **Local Privilege Escalation**: Enumerate sudo misconfigurations / writable internal backup scripts $\rightarrow$ elevate to `root` (`/root/proof.txt`).
  3. **Network Pivoting**: Discover pivot notes and credentials in `/root/pivot_notes.txt` $\rightarrow$ configure SSH dynamic port forwarding (`ssh -D 1080`) or Chisel tunnel into `10.20.20.0/24` and `10.100.10.0/24`.
  4. **Database Credential Discovery**: Connect to PostgreSQL (`10.20.20.20:5432`) $\rightarrow$ extract Active Directory LDAP sync service account credentials.
  5. **Active Directory Exploitation**: AS-REP Roasting & Kerberoasting against HQ Child DC $\rightarrow$ exploit bidirectional forest trust $\rightarrow$ achieve Domain / Enterprise Admin compromise on Parent DC (`10.100.10.10`).
- **Key Targets**:
  - DMZ Web Server: `10.10.10.80:80` (HTTP) & `:22` (SSH Pivot)
  - Internal PostgreSQL DB: `10.20.20.20:5432`
  - Internal Redis Cache: `10.20.20.30:6379`
  - Parent Forest DC: `10.100.10.10:445` (SMB)
  - Child Forest DC: `10.100.10.20:389` (LDAP)

### Lab 2: Multi-Domain Forest & Trust Pivoting

- **Domains**: `MEGACORP.LOCAL` / `HQ.MEGACORP.LOCAL` / `CYBERTECH.LOCAL`
- **Initial Access**: Low-privilege child domain user via dynamic wordlists
- **Key Vectors**: Bidirectional Parent-Child trust enumeration $\rightarrow$ Enterprise Admins escalation $\rightarrow$ External Forest Trust boundary traversal to partner tree domain.
- **Key Targets**:
  - Forest Root DC (`MEGACORP.LOCAL`): `10.101.10.10:445`
  - Child DC (`HQ.MEGACORP.LOCAL`): `10.101.20.10:389`
  - Partner Tree DC (`CYBERTECH.LOCAL`): `10.101.30.10:88`

### Lab 3: AD CS Certificate Abuse (ESC1)

- **Domain**: `ADCSLAB.LOCAL`
- **Initial Access**: `l3_j.doe` / `StudentPass2026!`
- **Key Vectors**: AD CS certificate template discovery (`Certipy find`) $\rightarrow$ Misconfigured `ENROLLEE_SUPPLIES_SUBJECT` (ESC1) $\rightarrow$ Request certificate with custom SAN for Domain Admin $\rightarrow$ Kerberos PKINIT authentication for TGT and NT hash retrieval.
- **Key Targets**:
  - Domain Controller: `10.102.10.10:445`
  - CA Web Enrollment Service: `10.102.20.20:80`

### Lab 4: External Forest Trust & Foreign Security Principal (FSP) Abuse

- **Domain**: `FORESTA.LOCAL` $\leftrightarrow$ `FORESTB.LOCAL`
- **Initial Access**: `l4b_student` / `SimpleStudentPass2026!` (Forest B)
- **Key Vectors**: Cross-forest trust enumeration $\rightarrow$ Locate Foreign Security Principal (FSP) memberships in Forest A $\rightarrow$ Abuse `GenericWrite` permissions over administrative groups $\rightarrow$ WinRM remote command execution via Evil-WinRM (`10.103.20.30:5985`) $\rightarrow$ Domain takeover.
- **Key Targets**:
  - Forest A DC (`FORESTA.LOCAL`): `10.103.10.10:445`
  - Forest B DC (`FORESTB.LOCAL`): `10.103.20.10:389`
  - WinRM Target Server: `10.103.20.30:5985` (HTTP WinRM)

### Lab 5: Group Policy Object (GPO) Abuse & Workstation RCE

- **Domain**: `GPOLAB.LOCAL`
- **Initial Access**: `l5_operator` / `OperatorPass2026!`
- **Key Vectors**: Inspect GPO permissions $\rightarrow$ Write access over GPO startup scripts on `SYSVOL` $\rightarrow$ Inject administrative command payload $\rightarrow$ Capture reverse shell from client workstation simulator (`10.104.20.20:5985`).
- **Key Targets**:
  - Domain Controller: `10.104.10.10:445`
  - Workstation Simulator: `10.104.20.20:5985` (WinRM)

### Lab 6: Resource-Based Constrained Delegation (RBCD)

- **Domain**: `RBCDLAB.LOCAL`
- **Initial Access**: Low-privileged domain user
- **Key Vectors**: Write access over computer objects $\rightarrow$ MachineAccountQuota account registration $\rightarrow$ Configure `msDS-AllowedToActOnBehalfOfOtherIdentity` $\rightarrow$ S4U2self + S4U2proxy impersonation $\rightarrow$ Host compromise.
- **Key Targets**:
  - Domain Controller: `10.105.10.10:445`
  - Target Server: `10.105.20.20:22`

### Lab 7: SQL Database Link Pivoting

- **Domain**: `SQLPIVOT.LOCAL`
- **Initial Access**: Frontend database network segment (`10.106.20.20:5432`)
- **Key Vectors**: Authenticate to frontend PostgreSQL $\rightarrow$ Enumerate Foreign Data Wrapper (`postgres_fdw`) links $\rightarrow$ Cross-subnet query execution to isolated backend database (`10.106.10.20`) $\rightarrow$ Flag exfiltration.
- **Key Targets**:
  - Domain Controller: `10.106.10.10:445`
  - Frontend Database: `10.106.20.20:5432`
  - Isolated Backend Database: `10.106.10.20:5432`

### Lab 8: LAPS & Local Administrator Password Leakage

- **Domain**: `LAPSLAB.LOCAL`
- **Initial Access**: Low-privileged audit account
- **Key Vectors**: LDAP search across computer objects $\rightarrow$ Extract cleartext passwords stored in legacy/custom attributes $\rightarrow$ WinRM / Evil-WinRM access to finance server (`10.107.20.20:5985`) $\rightarrow$ Kerberos ticket caching abuse.
- **Key Targets**:
  - Domain Controller: `10.107.10.10:445`
  - Target Finance Server: `10.107.20.20:5985` (WinRM) & `:22` (SSH)

### Lab 9: AD CS NTLM Relay (ESC8) & Coercion

- **Domain**: `ESC8LAB.LOCAL`
- **Initial Access**: Low-privileged student account
- **Key Vectors**: Unencrypted HTTP CA Web Enrollment (`/certsrv`) $\rightarrow$ Coerce DC authentication via PetitPotam/PrinterBug $\rightarrow$ Relay NTLM authentication to CA $\rightarrow$ Acquire DC machine certificate for DCSync.
- **Key Targets**:
  - Domain Controller: `10.108.10.10:445`
  - Certificate Authority Web Enrollment: `10.108.20.20:80`

### Lab 10: Kerberos Constrained Delegation (S4U)

- **Domain**: `DELEGATELAB.LOCAL`
- **Initial Access**: `l10_web_service` service account
- **Key Vectors**: Kerberos Constrained Delegation with Protocol Transition $\rightarrow$ S4U2self to forge TGS as Domain Admin $\rightarrow$ S4U2proxy to access backend database service.
- **Key Targets**:
  - Domain Controller: `10.109.10.10:445`
  - Backend Database Server: `10.109.20.20:22`

### Lab 11: Hybrid Cloud Identity & Azure AD Connect Sync Abuse

- **Domain**: `MEGACORP-CLOUD.LOCAL`
- **Initial Access**: HelpDesk Intern credentials (`l11_t.intern:InternPass2026!`) + Web Manager at `10.110.20.20:80`
- **Key Vectors**: BloodHound ACL abuse $\rightarrow$ Local Administrator pivot on `hybrid-sync-srv` $\rightarrow$ Extract Azure AD Connect LocalDB $\rightarrow$ Decrypt MSOL sync service account password $\rightarrow$ DCSync against Domain Controller.
- **Key Targets**:
  - Domain Controller SMB: `10.110.10.10:445`
  - Entra Connect Sync Web Portal: `10.110.20.20:80`
  - Entra Connect Sync SSH: `10.110.20.20:22`

### Lab 12: SCCM/MECM Site Server Abuse & Multi-Tier Pivot

- **Domain**: `CORP-MANAGEMENT.LOCAL`
- **Initial Access**: HelpDesk Intern credentials + SMB Distribution Share (`\\10.112.20.20\SMSPKGD$`) + Web Portal at `10.112.20.20:80`
- **Key Vectors**: Perimeter firewall bypass $\rightarrow$ SCCM distribution share enumeration $\rightarrow$ Extract Network Access Account (NAA) credentials from `TSConfig.xml` $\rightarrow$ Foothold on `sccm-site-srv` $\rightarrow$ Dynamic SSH SOCKS pivoting (`-D 1080`) $\rightarrow$ Client Push installation account discovery $\rightarrow$ Domain takeover.
- **Key Targets**:
  - Domain Controller SMB: `10.112.10.10:445` (Firewalled from perimeter)
  - SCCM Distribution Point SMB: `10.112.20.20:445`
  - MECM Management Web Portal: `10.112.20.20:80`
  - SCCM Site Server SSH (Pivot Host): `10.112.20.20:22`

---

## CLI Reference

### Subcommands

```bash
adlabs [command] [arguments]
```

| Subcommand | Description | Example |
| :--- | :--- | :--- |
| `status` | Display live status table of all 12 labs | `python3 adlabs.py status` |
| `deploy <id\|all>` | Start and provision containers for a lab | `python3 adlabs.py deploy 1` |
| `stop <id\|all>` | Halt running containers (preserves volume state) | `python3 adlabs.py stop 1` |
| `clean <id\|all>` | Destroy containers and wipe data volumes | `python3 adlabs.py clean 1` |
| `info <id\|all>` | Display detailed lab objectives, targets, and credentials | `python3 adlabs.py info 1` |
| `test <id\|all>` | Probe service reachability and container health | `python3 adlabs.py test 1` |
| `connect <id>` | Connect WireGuard tunnel for a lab | `python3 adlabs.py connect 1` |
| `disconnect` | Disconnect active WireGuard tunnel | `python3 adlabs.py disconnect` |
| `submit <flag>` | Submit captured `local.txt` or `proof.txt` flag | `python3 adlabs.py submit OSCP{...}` |
| `flags` | Display flags scoreboard and earned points | `python3 adlabs.py flags` |
| `hint <id> [tier]` | Request progressive hints for a lab (Tier 1-4) | `python3 adlabs.py hint 1` |
| `exam <action>` | Manage 24-hour OSCP Mock Exam (`start`, `status`, `stop`) | `python3 adlabs.py exam status` |
| `wordlists` | Regenerate dynamic wordlists (`--randomize` for fresh passwords) | `python3 adlabs.py wordlists -r` |

### Command Flags

```
options:
  -h, --help            Show this help message and exit
  --all, -a             Start and provision all 12 labs simultaneously
  --lab, -l LAB         Start and provision a specific lab (by name or 1-12 index)
  --status, -s          Show live status summary overview of all 12 labs
  --info, -i INFO       Show detailed info, credentials, and targets for a lab
  --stop-all            Stop all running labs
  --stop STOP           Stop a specific lab (by name or 1-12 index)
  --clean-all           Stop and remove volumes for all labs (complete data reset)
  --clean CLEAN         Stop and remove volumes for a specific lab
  --test-all            Test network connectivity and health of all labs
  --test TEST           Test connectivity and health of a specific lab
  --connect, -c CONN    Connect WireGuard VPN tunnel for a lab
  --disconnect, -d DISC Disconnect WireGuard VPN tunnel for a lab
  --submit FLAG         Submit a captured flag (local.txt or proof.txt)
  --hint HINT           Request progressive hint for a lab (1-12 or name)
  --flags               Show flag progress and score breakdown
  --exam [ACTION]       OSCP Mock Exam simulator (start, status, stop)
  --generate-wordlists  Generate or recreate user and password wordlists
  --randomize, -r       Randomize credentials when generating wordlists
  --gen-vpn GEN_VPN     Generate or regenerate VPN profiles (or 'all')
  --set-host SET_HOST   Set persistent Host IP or DDNS Domain and update profiles
  --update-ip           Auto-detect current public/local IP and update all deployed labs
  --host HOST           Override Host IP/Domain for current command
  --list-labs           Print available labs list cleanly
  --count-labs          Print total lab count (12)
```

---

## Troubleshooting & FAQ

> [!WARNING]
> **Resource Limits on Docker Desktop / WSL2**  
> Running all 12 labs simultaneously requires at least **6–8 GB of RAM** allocated to Docker/WSL2. For typical practice sessions, deploy labs individually (`python3 adlabs.py deploy <id>`) to conserve system resources.

### WireGuard Handshake Fails

- Verify that your host's local IP address matches the `Endpoint` in your `.conf` file.
- If your IP changed (e.g. Wi-Fi switch), run:
  ```bash
  python3 adlabs.py --gen-vpn <lab_number>
  ```
- Ensure UDP traffic on the assigned port (`51820–51831`) is permitted through your host firewall.

### Cannot Reach Domain Names

- The WireGuard `.conf` configuration includes an automated DNS router container (`adlabs-dns`).
- If domain resolution fails on your attacker system, use the target's direct IP address or append the entry to `/etc/hosts`:
  ```
  10.100.10.10 megacorp.local dc.megacorp.local
  ```

### Resetting a Corrupted Lab

If an interrupted setup leaves a container in an inconsistent state, completely clean and redeploy the specific lab:

```bash
python3 adlabs.py clean 1
python3 adlabs.py deploy 1
```