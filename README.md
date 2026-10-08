# ADLabs: Active Directory Pentesting Suite

[![Docker](https://img.shields.io/badge/Docker-20.10%2B-2496ED?logo=docker&logoColor=white)](https://www.docker.com/)
[![Docker Compose](https://img.shields.io/badge/Docker%20Compose-v2-2496ED?logo=docker&logoColor=white)](https://docs.docker.com/compose/)
[![Python](https://img.shields.io/badge/Python-3.8%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![WireGuard](https://img.shields.io/badge/VPN-WireGuard-88171A?logo=wireguard&logoColor=white)](https://www.wireguard.com/)
[![Labs](https://img.shields.io/badge/Labs-12%20Scenarios-brightgreen)](#lab-scenarios--attack-vectors)

A lightweight, containerized Active Directory laboratory suite designed for **OSCP (PEN-200)**, **OSCP+**, and enterprise red team preparation.

ADLabs replaces resource-intensive Windows Virtual Machines with Samba Active Directory Domain Controllers, Debian routers, and dedicated WireGuard VPN gateways running entirely inside Docker containers.

---

> [!IMPORTANT]
> **Educational and Authorized Use Only**  
> These labs are intentionally configured with security misconfigurations for educational training and skill assessment. Practice only within your local, isolated environment. Never apply these attack techniques against unauthorized targets.

---

## Highlights

- **12 Practical Scenarios**: Hands-on coverage of modern AD attack primitives, from Kerberos abuse to AD CS exploitation, Azure AD Connect sync abuse, and SCCM/MECM network pivoting.
- **Lightweight Footprint**: Operates without Windows licensing or heavy hypervisors; each DC runs within ~60–90 MB of memory.
- **Network Isolation**: Every lab runs on dedicated, non-overlapping Docker bridge subnets connected through software routers and isolated WireGuard gateways.
- **Zero Python Dependencies**: The orchestration CLI (`adlabs.py`) runs out-of-the-box using the Python standard library.
- **Auto-Timeout Daemon**: Automatically halts idle containers after 15 minutes of inactivity or 2 hours of total runtime to prevent resource exhaustion.
- **Dynamic Port & IP Allocation**: Automatically scans for free host UDP ports (starting at `51820/udp`) and VPN client addresses (`10.252.x.2`) to eliminate port conflicts.

---

## Prerequisites

Ensure the following tools are installed on your host machine before starting:

### Required Software

| Software | Minimum Version | Notes |
| :--- | :--- | :--- |
| **Docker Engine** | 20.10+ | Docker Desktop on Windows/macOS or Docker Engine on Linux |
| **Docker Compose** | v2.0+ | Compose plugin (`docker compose`) |
| **Python** | 3.8+ | Standard library only (no `pip install` required) |
| **WireGuard Client** | Latest | [Windows](https://www.wireguard.com/install/) \| [Linux (`wireguard-tools`)](https://www.wireguard.com/install/) \| [macOS](https://apps.apple.com/app/wireguard/id1451685025) |

### Recommended Attacking Tools

Access the lab targets through your WireGuard connection using standard pentesting toolsets (e.g., Kali Linux or WSL2):

- **Impacket** (`GetUserSPNs.py`, `GetNPUsers.py`, `secretsdump.py`, `getST.py`, `rbcd.py`)
- **Certipy** (for AD CS enumeration and PKINIT authentication)
- **BloodHound / BloodHound.py** (for graph-based permission mapping)
- **NetExec / CrackMapExec** (for credential spraying and SMB/WinRM validation)
- **Coercer / PetitPotam / PrinterBug** (for authentication coercion)

---

## Quick Start

### 1. Interactive Menu

Launch the interactive terminal dashboard:

```bash
python adlabs.py
```

Choose any option between `[1]` and `[13]` to deploy individual labs, deploy all labs simultaneously, inspect live status overview (`[7]`), view detailed lab info & credentials (`[8]`), test connectivity, or generate wordlists.

### 2. Command Line Interface (CLI)

Deploy and manage labs directly with flags:

```bash
# Check live status overview of all 10 labs
python adlabs.py --status

# Inspect comprehensive info, credentials, and targets for a specific lab
python adlabs.py --info 1
# Or inspect all labs:
python adlabs.py --info all

# Deploy a single lab (e.g., Lab 1)
python adlabs.py --lab 1

# Deploy all 10 labs at once
python adlabs.py --all

# Test connectivity and container health
python adlabs.py --test 1
python adlabs.py --test-all

# Stop a running lab (preserves volume state)
python adlabs.py --stop 1
python adlabs.py --stop-all

# Completely wipe containers and volumes for a clean reset
python adlabs.py --clean 1
python adlabs.py --clean-all
```

### 3. Connect via WireGuard

Each deployment generates a client VPN profile in the lab directory (e.g., `rbcd-lab/oscp-rbcd-lab.conf`).

#### Option A: One-Click CLI Import & Connect (Recommended)
You can directly import and manage WireGuard tunnels via CLI without using the GUI:

```powershell
# Connect / Import via batch script (triggers UAC elevation automatically):
.\connect.bat 6

# Or connect via Python CLI (Run in Administrator Terminal):
python adlabs.py --connect 6

# Disconnect when finished:
.\disconnect.bat 6
# Or:
python adlabs.py --disconnect 6
```

#### Option B: Manual GUI Import
1. Open the WireGuard Windows application.
2. Click **Import tunnel(s) from file** (`Ctrl + O`).
3. Select the `.conf` file from the target lab folder (e.g., `rbcd-lab/oscp-rbcd-lab.conf`).
4. Click **Activate**.

> [!TIP]
> **Host IP Changes**: If your host machine changes networks (e.g., switches Wi-Fi or DHCP leases), regenerate the WireGuard profile without redeploying the lab:
> ```bash
> python adlabs.py --gen-vpn 1
> # Or regenerate profiles for all labs:
> python adlabs.py --gen-vpn all
> ```

---

## Lab Architecture & Network Mapping

To prevent collisions, each lab utilizes dedicated subnets, domain names, and WireGuard host ports:

| # | Lab Directory | Domain / Realm | Target Subnets | Default Port | VPN Profile |
| :-: | :--- | :--- | :--- | :-: | :--- |
| **1** | [`oscp-network-pivot-lab`](./oscp-network-pivot-lab/) | `MEGACORP.LOCAL`<br>`HQ.MEGACORP.LOCAL` | `10.10.10.0/24` (DMZ)<br>`10.20.20.0/24` (Internal)<br>`10.100.10.0/24` (AD) | `51820/udp` | `oscp-pivot-lab.conf` |
| **2** | [`multi-domain-forest-lab`](./multi-domain-forest-lab/) | `MEGACORP.LOCAL`<br>`HQ.MEGACORP.LOCAL`<br>`CYBERTECH.LOCAL` | `10.101.10.0/24` (Parent)<br>`10.101.20.0/24` (Child)<br>`10.101.30.0/24` (Tree) | `51821/udp` | `multi-domain-forest-lab.conf` |
| **3** | [`adcs-abuse-lab`](./adcs-abuse-lab/) | `ADCSLAB.LOCAL` | `10.102.10.0/24` (AD)<br>`10.102.20.0/24` (CA Web) | `51822/udp` | `oscp-adcs-lab.conf` |
| **4** | [`trust-pivoting-lab`](./trust-pivoting-lab/) | `FORESTA.LOCAL`<br>`FORESTB.LOCAL` | `10.103.10.0/24` (Forest A)<br>`10.103.20.0/24` (Forest B) | `51823/udp` | `oscp-trust-lab.conf` |
| **5** | [`gpo-admin-pivot-lab`](./gpo-admin-pivot-lab/) | `GPOLAB.LOCAL` | `10.104.10.0/24` (AD)<br>`10.104.20.0/24` (Client) | `51824/udp` | `oscp-gpo-lab.conf` |
| **6** | [`rbcd-lab`](./rbcd-lab/) | `RBCDLAB.LOCAL` | `10.105.10.0/24` (AD)<br>`10.105.20.0/24` (Server) | `51825/udp` | `oscp-rbcd-lab.conf` |
| **7** | [`sql-pivot-lab`](./sql-pivot-lab/) | `SQLPIVOT.LOCAL` | `10.106.10.0/24` (AD)<br>`10.106.20.0/24` (SQL) | `51826/udp` | `oscp-sql-lab.conf` |
| **8** | [`laps-lab`](./laps-lab/) | `LAPSLAB.LOCAL` | `10.107.10.0/24` (AD)<br>`10.107.20.0/24` (Server) | `51827/udp` | `oscp-laps-lab.conf` |
| **9** | [`esc8-relay-lab`](./esc8-relay-lab/) | `ESC8LAB.LOCAL` | `10.108.10.0/24` (AD)<br>`10.108.20.0/24` (Web) | `51828/udp` | `oscp-esc8-lab.conf` |
| **10** | [`delegation-s4u-lab`](./delegation-s4u-lab/) | `DELEGATELAB.LOCAL` | `10.109.10.0/24` (AD)<br>`10.109.20.0/24` (DB) | `51829/udp` | `oscp-delegation-lab.conf` |
| **11** | [`hybrid-cloud-aad-lab`](./hybrid-cloud-aad-lab/) | `MEGACORP-CLOUD.LOCAL` | `10.110.10.0/24` (AD)<br>`10.110.20.0/24` (Sync) | `51830/udp` | `oscp-hybrid-cloud-lab.conf` |
| **12** | [`sccm-mecm-pivot-lab`](./sccm-mecm-pivot-lab/) | `CORP-MANAGEMENT.LOCAL` | `10.112.10.0/24` (AD)<br>`10.112.20.0/24` (Mgmt) | `51831/udp` | `oscp-sccm-lab.conf` |

---

## Lab Scenarios & Attack Vectors

### Lab 1: Network Pivoting & Multi-Tier Foothold

- **Domain**: `MEGACORP.LOCAL` / `HQ.MEGACORP.LOCAL`
- **Initial Access**: Perimeter Web Landing Portal at `10.10.10.80`
- **Key Vectors**: Web foothold $\rightarrow$ DMZ firewall bypass $\rightarrow$ PostgreSQL configuration file enumeration $\rightarrow$ Active Directory credential extraction $\rightarrow$ AS-REP Roasting & Kerberoasting $\rightarrow$ Domain takeover.
- **Targets**:
  - Perimeter Web UI: `10.10.10.80:80`
  - Internal Database: `10.20.20.20:5432`
  - Parent Domain Controller: `10.100.10.10:445`
  - Child Domain Controller: `10.100.10.20:389`

### Lab 2: Multi-Domain Forest & Cross-Forest Trust Pivoting

- **Domain**: `MEGACORP.LOCAL` / `HQ.MEGACORP.LOCAL` / `CYBERTECH.LOCAL`
- **Initial Access**: Low-privileged user in child domain (`HQ.MEGACORP.LOCAL`) via `credentials.txt`
- **Key Vectors**: Bidirectional Parent-Child trust enumeration $\rightarrow$ Enterprise Admins escalation $\rightarrow$ External Forest Trust boundary traversal to `CYBERTECH.LOCAL`.
- **Targets**:
  - Forest Root DC (`MEGACORP.LOCAL`): `10.101.10.10:445`
  - Child DC (`HQ.MEGACORP.LOCAL`): `10.101.20.10:389`
  - Partner Tree DC (`CYBERTECH.LOCAL`): `10.101.30.10:88`

### Lab 3: AD CS Certificate Abuse (ESC1)

- **Domain**: `ADCSLAB.LOCAL`
- **Initial Access**: `l3_j.doe` / `StudentPass2026!`
- **Key Vectors**: AD CS certificate template discovery (`Certipy find`) $\rightarrow$ Misconfigured `ENROLLEE_SUPPLIES_SUBJECT` (ESC1) $\rightarrow$ Requesting cert with custom SAN for Domain Admin $\rightarrow$ Kerberos PKINIT authentication for TGT / NT hash retrieval.
- **Targets**:
  - Domain Controller: `10.102.10.10:445`
  - CA Web Enrollment Service: `10.102.20.20:80`

### Lab 4: External Forest Trust & Foreign Security Principal (FSP) Abuse

- **Domain**: `FORESTA.LOCAL` $\leftrightarrow$ `FORESTB.LOCAL`
- **Initial Access**: `l4b_student` / `SimpleStudentPass2026!` (in Forest B)
- **Key Vectors**: Cross-forest trust enumeration $\rightarrow$ Locating Foreign Security Principal (FSP) memberships in Forest A $\rightarrow$ Abusing `GenericWrite` permissions over Forest A administrative groups $\rightarrow$ Domain Admin takeover on Forest A DC.
- **Targets**:
  - Forest A DC (`FORESTA.LOCAL`): `10.103.10.10:445`
  - Forest B DC (`FORESTB.LOCAL`): `10.103.20.10:389`
  - WinRM Target Machine: `10.103.20.30:5985`

### Lab 5: Group Policy Object (GPO) Abuse & Workstation RCE

- **Domain**: `GPOLAB.LOCAL`
- **Initial Access**: `l5_operator` / `OperatorPass2026!`
- **Key Vectors**: Inspecting GPO permissions $\rightarrow$ Identifying write access over GPO startup scripts on `SYSVOL` $\rightarrow$ Injecting administrative commands $\rightarrow$ Capturing reverse shell from automated workstation client.
- **Targets**:
  - Domain Controller (`GPOLAB.LOCAL`): `10.104.10.10:445`
  - Client Workstation Simulator: `10.104.20.20`

### Lab 6: Resource-Based Constrained Delegation (RBCD)

- **Domain**: `RBCDLAB.LOCAL`
- **Initial Access**: `l6_r.worker` / `WorkerPass2026!`
- **Key Vectors**: Identifying write access over computer objects $\rightarrow$ Registering an attacker machine account via MachineAccountQuota $\rightarrow$ Modifying `msDS-AllowedToActOnBehalfOfOtherIdentity` $\rightarrow$ S4U2self + S4U2proxy impersonation $\rightarrow$ Host compromise.
- **Targets**:
  - Domain Controller (`RBCDLAB.LOCAL`): `10.105.10.10:445`
  - Target Server (SSH/Web): `10.105.20.20:22`

### Lab 7: SQL Database Link Pivoting

- **Domain**: `SQLPIVOT.LOCAL`
- **Initial Access**: Access to frontend database network segment (`10.106.20.20`)
- **Key Vectors**: Authenticating to frontend PostgreSQL instance $\rightarrow$ Discovering foreign data wrapper / database link (`postgres_fdw`) to isolated backend server $\rightarrow$ Cross-subnet query execution and code execution.
- **Targets**:
  - Domain Controller (`SQLPIVOT.LOCAL`): `10.106.10.10:445`
  - Frontend Database: `10.106.20.20:5432`
  - Isolated Backend Database: `10.106.10.20:5432`

### Lab 8: LAPS & Local Administrator Password Leakage

- **Domain**: `LAPSLAB.LOCAL`
- **Initial Access**: `l8_audit_user` / `AuditPass2026!`
- **Key Vectors**: Performing LDAP search across Active Directory computer objects $\rightarrow$ Finding clear-text administrative passwords leaked in legacy description/comment attributes $\rightarrow$ Privilege escalation to local administrator.
- **Targets**:
  - Domain Controller (`LAPSLAB.LOCAL`): `10.107.10.10:445`
  - Target Finance Server: `10.107.20.20:22`

### Lab 9: AD CS NTLM Relay (ESC8) & Coercion

- **Domain**: `ESC8LAB.LOCAL`
- **Initial Access**: `l9_student` / `StudentPass2026!`
- **Key Vectors**: Locating unencrypted HTTP CA Web Enrollment endpoint (`/certsrv`) $\rightarrow$ Coercing authentication from the Domain Controller machine account $\rightarrow$ Relaying NTLM credentials to the CA $\rightarrow$ Obtaining Domain Controller certificate for DCSync.
- **Targets**:
  - Domain Controller (`ESC8LAB.LOCAL`): `10.108.10.10:445`
  - Certificate Authority Web Enrollment: `10.108.20.20:80`

### Lab 10: Kerberos Constrained Delegation (S4U)

- **Domain**: `DELEGATELAB.LOCAL`
- **Initial Access**: `l10_web_service` / `WebServPass123!`
- **Key Vectors**: Enumerating Kerberos Constrained Delegation with Protocol Transition on service account $\rightarrow$ Performing S4U2self to forge TGS as Domain Admin $\rightarrow$ Performing S4U2proxy to access backend database service $\rightarrow$ Compromising target server.
- **Targets**:
  - Domain Controller (`DELEGATELAB.LOCAL`): `10.109.10.10:445`
  - Target Database Server (SSH/Web): `10.109.20.20:22`

### Lab 11: Hybrid Cloud Identity & Azure AD Connect Sync Abuse

- **Domain**: `MEGACORP-CLOUD.LOCAL` (NetBIOS: `MEGACLOUD`)
- **Initial Access**: HelpDesk Intern credentials (`l11_t.intern:InternPass2026!`) + Web Manager at `10.110.20.20:80`
- **Key Vectors**: HelpDesk foothold $\rightarrow$ BloodHound ACL permission abuse $\rightarrow$ Local Administrator pivot on `hybrid-sync-srv` $\rightarrow$ Azure AD Connect LocalDB extraction $\rightarrow$ MSOL sync account decryption $\rightarrow$ DCSync attack against Domain Controller (`10.110.10.10`).
- **Targets**:
  - Domain Controller SMB: `10.110.10.10:445`
  - Domain Controller Kerberos: `10.110.10.10:88`
  - Entra Connect Sync Web Manager: `10.110.20.20:80`
  - Entra Connect Sync SSH: `10.110.20.20:22`

### Lab 12: SCCM/MECM Site Server Abuse & Multi-Tier Network Pivot

- **Domain**: `CORP-MANAGEMENT.LOCAL` (NetBIOS: `CORPMGMT`)
- **Initial Access**: HelpDesk Intern credentials (`l12_j.intern:InternPass2026!`) + SCCM Distribution Share at `\\10.112.20.20\SMSPKGD$` + Web Portal at `10.112.20.20:80`.
- **Key Vectors**: Network perimeter reconnaissance $\rightarrow$ Perimeter firewall drop detection on DC (`10.112.10.10`) $\rightarrow$ SCCM Distribution Point SMB enumeration $\rightarrow$ Network Access Account (NAA) extraction from `TSConfig.xml` $\rightarrow$ Foothold on `sccm-site-srv` (`10.112.20.20`) $\rightarrow$ Dynamic SSH SOCKS pivoting (`-D 1080`) bypassing network segmentation $\rightarrow$ Client Push installation account discovery $\rightarrow$ DCSync against Domain Controller $\rightarrow$ Flag capture.
- **Targets**:
  - Domain Controller SMB: `10.112.10.10:445` (Firewalled from perimeter)
  - Domain Controller Kerberos: `10.112.10.10:88` (Firewalled from perimeter)
  - SCCM Distribution Point SMB: `10.112.20.20:445`
  - MECM Management Point Web Portal: `10.112.20.20:80`
  - SCCM Site Server SSH (Pivot Host): `10.112.20.20:22`

---

## CLI Reference

The `adlabs.py` utility supports both interactive and headless CLI operations:

```
usage: adlabs.py [-h] [--all] [--lab LAB] [--stop-all] [--stop STOP]
                 [--clean-all] [--clean CLEAN] [--test-all] [--test TEST]
                 [--generate-wordlists] [--gen-vpn GEN_VPN]

Manage AD Labs setup, provisioning, and connectivity.

options:
  -h, --help            Show this help message and exit
  --all, -a             Start and provision all 10 labs simultaneously
  --lab, -l LAB         Start and provision a specific lab (by name or 1-10 index)
  --stop-all            Stop all running labs
  --stop STOP           Stop a specific lab (by name or 1-10 index)
  --clean-all           Stop and remove volumes for all labs (complete data reset)
  --clean CLEAN         Stop and remove volumes for a specific lab
  --test-all            Test network connectivity and health of all labs
  --test TEST           Test connectivity and health of a specific lab
  --generate-wordlists  Generate or recreate user and password wordlists
  --gen-vpn GEN_VPN     Generate or regenerate VPN profiles (or 'all')
```

---

## Troubleshooting & FAQ

> [!WARNING]
> **Resource Limits on Docker Desktop / WSL2**  
> Running all 10 labs simultaneously requires at least **4–6 GB of RAM** allocated to Docker/WSL2. If your Docker environment is limited to 2 GB, deploy labs individually (`python adlabs.py --lab <id>`) or increase your WSL2 memory allocation via `.wslconfig`:
> ```ini
> [wsl2]
> memory=8GB
> ```

### WireGuard Handshake Fails

- Verify that your host's local IP address matches the `Endpoint` in your `.conf` file.
- If your IP changed, run:
  ```bash
  python adlabs.py --gen-vpn <lab_number>
  ```
- Ensure UDP traffic on the assigned port (e.g., `51820–51829`) is allowed by your host firewall.

### Cannot Reach Domain Names

- The WireGuard `.conf` configuration includes an automated DNS router (`adlabs-dns`).
- If domain resolution fails on your attacker system, use the target's direct IP address or add the entry to `/etc/hosts`:
  ```
  10.100.10.10 megacorp.local dc.megacorp.local
  ```

### Container Health Check Timeouts

- Samba Domain Controllers initialize their Kerberos KDC and database during first boot, which can take up to 60–90 seconds.
- The script automatically polls until the healthcheck returns `healthy`. If a container fails to start, inspect its recent logs:
  ```bash
  docker logs --tail 50 <container_name>
  ```

### Resetting a Corrupted Lab

If an interrupted setup leaves a container in an inconsistent state, completely clean and redeploy the specific lab:

```bash
python adlabs.py --clean 4
python adlabs.py --lab 4
```