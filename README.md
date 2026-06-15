# Active Directory Lab Environments (OSCP/OSCP+ Preparation)

This workspace contains ten lightweight, containerized Active Directory (AD) lab environments tailored for pentesting practice and OSCP/OSCP+ preparation. It replaces heavy Windows virtual machines with Docker containers running Samba AD Domain Controllers, Linux routers, and dedicated WireGuard VPN gateways.

---

## ⚠️ IMPORTANT WARNINGS & SECURITY CONSIDERATIONS

**READ THIS SECTION BEFORE PROCEEDING**

- **Educational Purpose Only**: These labs are designed for authorized security training and educational purposes. Never use these techniques against systems without explicit permission.
- **Isolated Environment**: All labs run in isolated Docker networks with WireGuard VPN access. Ensure your host firewall is configured appropriately.
- **Credential Security**: Default credentials are provided for lab setup only. Do not reuse these passwords in production environments.
- **Resource Usage**: Each lab consumes significant system resources (CPU, RAM, Disk). Ensure your system meets the requirements below.
- **Network Isolation**: Labs use custom subnet ranges (10.x.x.x) that may conflict with existing VPN connections. Disconnect other VPNs before starting.
- **Data Persistence**: Lab data persists in Docker volumes. Use the cleanup commands to completely remove lab data when finished.
- **Auto-Timeout**: Labs automatically shut down after 2 hours of runtime or 15 minutes of idle activity to prevent resource exhaustion.

---

## 📋 Prerequisites

Before using these labs, ensure you have the following installed:

### Required Software
- **Docker Engine**: Version 20.10 or higher
- **Docker Compose**: Version 2.0 or higher
- **Python 3**: Version 3.8 or higher (for the management script)
- **WireGuard**: Client software for VPN connection
  - **Windows**: [WireGuard for Windows](https://www.wireguard.com/install/)
  - **Linux**: `sudo apt install wireguard` or `sudo yum install wireguard-tools`
  - **macOS**: [WireGuard for macOS](https://apps.apple.com/app/wireguard/id1451685025)

### System Requirements
- **RAM**: Minimum 8GB (16GB recommended for running multiple labs)
- **Disk Space**: Minimum 20GB free space
- **CPU**: 4 cores minimum (8 cores recommended)
- **Network**: Stable internet connection for pulling Docker images

### Optional Tools for Pentesting
- **Impacket**: For AD protocol manipulation
- **BloodHound**: For AD relationship mapping
- **CrackMapExec**: For AD authentication testing
- **Rubeus**: For Kerberos attacks (Windows)
- **Certipy**: For AD CS abuse
- **nmap**: For network enumeration

---

## 🚀 Quick Start Guide

### Option 1: Web Dashboard (Recommended)

1. Start the web dashboard:
   ```bash
   python web/app.py
   ```

2. Open your browser to `http://127.0.0.1:8000`

3. Use the dashboard to:
   - View all lab statuses
   - Deploy/stop/clean labs
   - Generate VPN profiles
   - Download WireGuard configurations

### Option 2: Command Line Interface

1. **Deploy a specific lab** (e.g., Lab 1):
   ```bash
   python adlabs.py --lab 1
   ```

2. **Generate VPN profile** (after lab is running):
   ```bash
   python adlabs.py --gen-vpn 1
   ```

3. **Connect using WireGuard**:
   - Import the generated `.conf` file into WireGuard client
   - Activate the connection
   - You can now access lab targets at their assigned IPs

4. **Stop a lab**:
   ```bash
   python adlabs.py --stop 1
   ```

5. **Clean up lab data** (removes all volumes):
   ```bash
   python adlabs.py --clean 1
   ```

### Useful Commands

- **Stop all running labs**: `python adlabs.py --stop-all`
- **Clean all labs**: `python adlabs.py --clean-all`
- **Generate wordlists**: `python adlabs.py --generate-wordlists`
- **Test lab connectivity**: `python adlabs.py --test 1`

---

## 🔌 Connection Instructions

### WireGuard VPN Setup

Each lab uses a dedicated WireGuard VPN gateway for secure access. Follow these steps:

1. **Deploy the lab** using the web dashboard or CLI
2. **Generate the VPN profile**:
   - Via dashboard: Click "Generate VPN" button for the lab
   - Via CLI: `python adlabs.py --gen-vpn <lab_number>`
3. **Import the configuration**:
   - The `.conf` file is located in the lab directory (e.g., `oscp-network-pivot-lab/oscp-pivot-lab.conf`)
   - Open WireGuard client and import the file
4. **Activate the connection**:
   - Click "Activate" in WireGuard client
   - The tunnel will establish and you'll receive a VPN IP (typically 10.252.x.2)
5. **Access lab targets**:
   - Use the target IPs listed in the table below
   - DNS resolution is configured automatically for domain names

### Connection Troubleshooting

**Issue**: WireGuard handshake fails
- **Solution**: Check that the host IP in the `.conf` file matches your current network interface IP. Regenerate the VPN profile if your IP changed.

**Issue**: Cannot reach lab targets
- **Solution**: Verify the WireGuard tunnel is active (check peer status). Ensure you're using the correct target IP addresses.

**Issue**: Port conflicts
- **Solution**: The script automatically allocates free UDP ports starting from 51820. If you have other WireGuard instances, stop them first.

**Issue**: DNS resolution not working
- **Solution**: The VPN profile includes DNS settings. If issues persist, try using IP addresses directly instead of hostnames.

---

## 🗂️ Lab Management

### Lab Lifecycle

1. **Deploy**: Creates and starts all containers for a lab
2. **Provision**: Configures AD, users, and vulnerabilities (automatic during deploy)
3. **Connect**: Generate VPN profile and connect via WireGuard
4. **Practice**: Perform penetration testing exercises
5. **Stop**: Stops all containers (preserves data in volumes)
6. **Clean**: Removes containers and volumes (complete data removal)

### Best Practices

- **One Lab at a Time**: Only run one lab at a time to avoid resource conflicts
- **Regular Cleanup**: Use `--clean` when finished with a lab to free disk space
- **Backup Configs**: Save your VPN profiles if you need to reconnect later
- **Document Progress**: Take notes on techniques used for each lab
- **Check Resources**: Monitor Docker resource usage with `docker stats`

---

## 🛠️ Troubleshooting

### Common Issues

**Docker containers won't start**
- Check Docker is running: `docker ps`
- Verify sufficient disk space: `docker system df`
- Check port conflicts: `netstat -tuln | grep 5182`
- Restart Docker daemon if needed

**Lab deployment fails**
- Ensure you're in the project root directory
- Check Python dependencies: `pip install -r requirements.txt` (if available)
- Verify Docker Compose version: `docker compose version`
- Check logs: `docker compose logs` in the lab directory

**WireGuard connection issues**
- Regenerate VPN profile after IP changes: `python adlabs.py --gen-vpn <lab>`
- Verify firewall allows UDP traffic on the assigned port
- Check WireGuard client logs for handshake errors
- Try using IP addresses instead of hostnames

**AD authentication failures**
- Verify you're connected to the VPN
- Check DNS resolution: `nslookup <dc_ip>`
- Use correct domain format: `DOMAIN.LOCAL`
- Verify credentials from the lab's credentials.txt file

**Container health checks failing**
- Wait 2-3 minutes after deployment for services to stabilize
- Check container logs: `docker logs <container_name>`
- Restart specific containers: `docker restart <container_name>`
- Use `--test` command to verify connectivity

### Getting Help

- Check container logs: `docker logs <container_name>`
- View all containers: `docker ps -a`
- Inspect networks: `docker network ls`
- Check resource usage: `docker stats`
- Review the lab-specific README files in each directory

---

## 🧹 Cleanup & Maintenance

### Remove a Single Lab
```bash
python adlabs.py --clean <lab_number>
```
This removes all containers, networks, and volumes for the specified lab.

### Remove All Labs
```bash
python adlabs.py --clean-all
```
This completely removes all lab data from your system.

### Docker System Cleanup
```bash
# Remove unused images
docker image prune -a

# Remove unused volumes
docker volume prune

# Remove unused networks
docker network prune

# Complete system cleanup (use with caution)
docker system prune -a --volumes
```

### Reset a Lab
If you need to reset a lab to its initial state:
1. Stop the lab: `python adlabs.py --stop <lab_number>`
2. Clean the lab: `python adlabs.py --clean <lab_number>`
3. Deploy again: `python adlabs.py --lab <lab_number>`

---

## 💡 Tips for Success

### Enumeration Strategy
1. **Start with network scanning**: Use `nmap` to discover all hosts and open ports
2. **Identify domain controllers**: Look for ports 88 (Kerberos), 389 (LDAP), 445 (SMB)
3. **Enumerate users**: Use tools like `ldapsearch`, `crackmapexec`, or BloodHound
4. **Check for vulnerabilities**: Look for AS-REP roasting, Kerberoasting, delegation misconfigurations
5. **Document findings**: Keep track of credentials, SPNs, and interesting permissions

### Common Attack Paths
- **AS-REP Roasting**: Target users with `UF_DONT_REQUIRE_PREAUTH` set
- **Kerberoasting**: Request service tickets for SPN-enabled accounts and crack offline
- **Password Spraying**: Try common passwords across multiple accounts
- **Delegation Abuse**: Exploit unconstrained or constrained delegation
- **Certificate Abuse**: Leverage AD CS misconfigurations (ESC1-ESC8)
- **LAPS**: Extract local admin passwords from AD attributes
- **GPO Abuse**: Modify Group Policy scripts for code execution
- **Trust Abuse**: Pivot across domain and forest trusts

### Useful Commands
```bash
# Check VPN connectivity
ping 10.252.x.2

# Enumerate AD users
crackmapexec smb <dc_ip> -u '' -p '' --users

# AS-REP roasting
GetNPUsers.py <domain>/ -usersfile users.txt -outputfile hashes.asrep

# Kerberoasting
GetUserSPNs.py <domain>/<user>:<password> -outputfile hashes.kerberoast

# BloodHound enumeration
python bloodhound-python -d <domain> -u <user> -p <password> -ns <dc_ip> -c All
```

---

## 1. Labs Architecture & Network Mapping

To prevent port conflicts on the host, each lab operates on isolated subnet spaces and maps its WireGuard VPN gateway to a distinct host UDP port.

| Lab Directory | Domain / Realm | Target Subnets | Gateway Host Port | Connection Profile |
| :--- | :--- | :--- | :--- | :--- |
| **1. [oscp-network-pivot-lab](./oscp-network-pivot-lab/)** | `MEGACORP.LOCAL`<br>`HQ.MEGACORP.LOCAL` | `10.10.10.0/24` (DMZ)<br>`10.20.20.0/24` (Internal)<br>`10.100.10.0/24` (AD) | `51820/udp` | [oscp-pivot-lab.conf](./oscp-network-pivot-lab/oscp-pivot-lab.conf) |
| **2. [multi-domain-forest-lab](./multi-domain-forest-lab/)** | `MEGACORP.LOCAL`<br>`HQ.MEGACORP.LOCAL`<br>`CYBERTECH.LOCAL` | `10.101.10.0/24` (Parent)<br>`10.101.20.0/24` (Child)<br>`10.101.30.0/24` (Tree) | `51821/udp` | [multi-domain-forest-lab.conf](./multi-domain-forest-lab/multi-domain-forest-lab.conf) |
| **3. [adcs-abuse-lab](./adcs-abuse-lab/)** | `ADCSLAB.LOCAL` | `10.102.10.0/24` (AD)<br>`10.102.20.0/24` (CA Web) | `51822/udp` | [oscp-adcs-lab.conf](./adcs-abuse-lab/oscp-adcs-lab.conf) |
| **4. [trust-pivoting-lab](./trust-pivoting-lab/)** | `FORESTA.LOCAL`<br>`FORESTB.LOCAL` | `10.103.10.0/24` (Forest A)<br>`10.103.20.0/24` (Forest B) | `51823/udp` | [oscp-trust-lab.conf](./trust-pivoting-lab/oscp-trust-lab.conf) |
| **5. [gpo-admin-pivot-lab](./gpo-admin-pivot-lab/)** | `GPOLAB.LOCAL` | `10.104.10.0/24` (AD)<br>`10.104.20.0/24` (Workstation) | `51824/udp` | [oscp-gpo-lab.conf](./gpo-admin-pivot-lab/oscp-gpo-lab.conf) |
| **6. [rbcd-lab](./rbcd-lab/)** | `RBCDLAB.LOCAL` | `10.105.10.0/24` (AD)<br>`10.105.20.0/24` (Server) | `51825/udp` | [oscp-rbcd-lab.conf](./rbcd-lab/oscp-rbcd-lab.conf) |
| **7. [sql-pivot-lab](./sql-pivot-lab/)** | `SQLPIVOT.LOCAL` | `10.106.10.0/24` (AD)<br>`10.106.20.0/24` (SQL) | `51826/udp` | [oscp-sql-lab.conf](./sql-pivot-lab/oscp-sql-lab.conf) |
| **8. [laps-lab](./laps-lab/)** | `LAPSLAB.LOCAL` | `10.107.10.0/24` (AD)<br>`10.107.20.0/24` (Server) | `51827/udp` | [oscp-laps-lab.conf](./laps-lab/oscp-laps-lab.conf) |
| **9. [esc8-relay-lab](./esc8-relay-lab/)** | `ESC8LAB.LOCAL` | `10.108.10.0/24` (AD)<br>`10.108.20.0/24` (Web) | `51828/udp` | [oscp-esc8-lab.conf](./esc8-relay-lab/oscp-esc8-lab.conf) |
| **10. [delegation-s4u-lab](./delegation-s4u-lab/)** | `DELEGATELAB.LOCAL` | `10.109.10.0/24` (AD)<br>`10.109.20.0/24` (DB) | `51829/udp` | [oscp-delegation-lab.conf](./delegation-s4u-lab/oscp-delegation-lab.conf) |

---

## 2. AD Labs Exam-Style Practice Scenarios

These labs are designed to simulate real-world enterprise penetration testing assessments and the **OSCP (PEN-200)** / **OSCP+** exam environments. Below are the expanded, immersive background scenarios and objectives for each laboratory. All direct instructions and spoiler credentials have been removed to encourage complete independent enumeration and research.

---

### 🧪 Lab 1: Network Pivoting Lab (MegaCorp - External to Internal Domain Takeover)
* **Background Scenario**: 
  MegaCorp has deployed a public-facing web landing portal in their DMZ network, which connects to internal back-end databases. According to initial architectural reports, network segmentation rules between the DMZ, the Internal Server network, and the Active Directory Forest network may be insecure. The internal network hosts domain controllers for the parent domain `MEGACORP.LOCAL` and a child domain `HQ.MEGACORP.LOCAL`. 
  
  You are tasked with conducting an external-to-internal network penetration test. Starting with only access to the public-facing DMZ portal, you must establish an initial foothold, map the internal subnets, locate internal databases, extract active credentials, and identify directory service vulnerabilities to pivot deeper into the Active Directory forest.
* **Exploitation Objectives**:
  1. Audit the public web interface to identify misconfigurations, leaks, or directory exposure.
  2. Pivot from the DMZ segment to establish access to the internal database server network.
  3. Enumerate the internal database instance to uncover credentials or configuration files.
  4. Perform Active Directory queries to find accounts susceptible to Kerberos pre-authentication attacks or search GPO folders for sensitive data leakage.
  5. Escalate privileges to compromise the parent domain controller.
* **Scope Details**:
  * Attacker Entrance: `10.10.10.80` (Perimeter Web UI)
  * Target subnets: `10.10.10.0/24` (DMZ), `10.20.20.0/24` (Internal), `10.100.10.0/24` (AD Network)
* **Flag Targets**:
  * Web Foothold Flag (DMZ)
  * Domain Admin access (Parent DC)

---

### 🧪 Lab 2: Multi-Domain Forest Lab (Acquisition & Forest Trust Pivot)
* **Background Scenario**: 
  MegaCorp recently acquired a startup company and integrated their infrastructure as a child domain (`HQ.MEGACORP.LOCAL`). In addition, MegaCorp has established a cross-forest partnership trust with an external entity (`CYBERTECH.LOCAL`). The integration has raised security concerns regarding domain boundaries and trust relationships.
  
  You start as a low-privileged employee within the newly acquired child domain. The objective of this assessment is to determine if a low-privileged user can leverage the bi-directional parent-child domain trust to escalate privileges and control the forest root domain controller (`MEGACORP.LOCAL`). Furthermore, you must test the security boundaries of the forest trust by attempting to pivot from the parent domain and access resources in the partner forest (`CYBERTECH.LOCAL`).
* **Exploitation Objectives**:
  1. Map the multi-domain forest topology, including child-to-parent and external forest trusts.
  2. Leverage the trust path to escalate privileges from the child domain to Enterprise Admins on the forest root parent DC.
  3. Enumerate the forest trust boundaries and pivot to gain administrative control over the partner domain controller.
* **Starting Credentials**:
  * Check the domain configuration details in the [credentials.txt](./multi-domain-forest-lab/credentials.txt) file to begin your child domain enumeration.
* **Flag Targets**:
  * Parent Domain Controller Admin access
  * Partner Forest Tree (`CYBERTECH.LOCAL`) Domain Controller Admin access

---

### 🧪 Lab 3: AD CS Certificate Abuse (ESC1) Lab (Certificate Authority Takeover)
* **Background Scenario**: 
  To support modern security operations, the organization has implemented Active Directory Certificate Services (AD CS) to manage PKI certificates for user authentication, smart card login, and web servers. The Certificate Authority (CA) server runs on `ADCSLAB.LOCAL`. However, the security team suspects that legacy or custom certificate templates published by the CA might contain misconfigurations.
  
  Your goal is to perform an internal audit of the certificate infrastructure. You must check published templates for standard misconfigurations (specifically ESC1, which allows clients to supply custom Subject Alternative Names). By exploiting this vulnerability, a standard domain user can request a certificate that impersonates a high-privileged administrator account and use the certificate to authenticate and compromise the domain.
* **Exploitation Objectives**:
  1. Enumerate active CA servers and query the published certificate templates.
  2. Identify templates that allow client authentication and custom SAN input (ESC1 vulnerability).
  3. Request a certificate using the vulnerable template while specifying a high-privileged administrator as the Subject Alternative Name (SAN).
  4. Perform Kerberos PKINIT authentication using the enrolled certificate to retrieve the administrator session ticket or NTLM credential.
* **Starting Credentials**:
  * Check the [credentials.txt](./adcs-abuse-lab/credentials.txt) file in the lab folder for your audit account credentials.
* **Flag Targets**:
  * Domain Administrator authentication access.

---

### 🧪 Lab 4: Trust & Forest Pivoting Lab (Foreign Security Principal Abuse)
* **Background Scenario**: 
  Following a recent partnership, Forest A (`FORESTA.LOCAL`) and Forest B (`FORESTB.LOCAL`) have established a bi-directional external trust. To simplify access management, administrators in Forest A have mapped groups and users from Forest B into local security groups in Forest A. These mappings are stored as Foreign Security Principal (FSP) objects.
  
  You have obtained access to a basic student account in Forest B (`FORESTB.LOCAL`). You must perform cross-forest enumeration to identify if your account or a group you belong to has been mapped to any security groups in Forest A. You must analyze the permissions of those groups to see if they grant write access over administrative containers or groups in Forest A, and exploit that path to escalate privileges.
* **Exploitation Objectives**:
  1. Perform cross-forest trust enumeration from the perspective of a Forest B user.
  2. Locate Foreign Security Principal (FSP) objects in Forest A pointing back to Forest B.
  3. Determine the permissions of the mapped groups in Forest A to identify potential write rights.
  4. Exploit group permissions to add your user (or a controlled account) to the administrative group in Forest A and obtain access to the Forest A Domain Controller.
* **Starting Credentials**:
  * User: `l4b_student`
  * Password: `SimpleStudentPass2026!`
* **Flag Targets**:
  * Administrator level access on the Forest A Domain Controller.

---

### 🧪 Lab 5: GPO & Client Workstation Pivot Lab (Policy-Based RCE)
* **Background Scenario**: 
  System administrators rely heavily on Group Policy Objects (GPOs) to apply updates, configurations, and administrative startup scripts across all workstations. In this environment (`GPOLAB.LOCAL`), GPOs are configured to execute startup script files located on the SYSVOL directory share of the domain controller.
  
  You have compromised the credentials of a low-privileged IT support account. This account does not have remote access or administrative privileges on workstations. However, during your Active Directory audit, you must check if this account has write/modification permissions over any GPOs linked to workstations. If a writeable GPO exists, you can modify its associated script in SYSVOL to execute commands as the SYSTEM account when workstations process the policy update.
* **Exploitation Objectives**:
  1. Enumerate the GPOs in the domain and analyze their security descriptors to find write permissions.
  2. Map the writeable GPO to its corresponding configuration path and script file on the `SYSVOL` share.
  3. Modify the policy script file to inject a command or connection payload.
  4. Start a network listener and capture the connection when the workstation simulator processes the GPO.
* **Starting Credentials**:
  * User: `l5_operator`
  * Password: `OperatorPass2026!`
* **Flag Targets**:
  * SYSTEM-level flag on the simulated workstation.

---

### 🧪 Lab 6: Resource-Based Constrained Delegation (RBCD) Lab (Computer Account Takeover)
* **Background Scenario**: 
  Resource-Based Constrained Delegation (RBCD) allows resource owners to configure who can delegate authentication to their systems. This configuration is controlled by the `msDS-AllowedToActOnBehalfOfOtherIdentity` attribute on computer objects. If a user account or group has write/modification permissions over a computer object in AD, it can configure that computer to trust any machine account.
  
  You are conducting an internal audit with a standard worker account. You need to identify if any servers allow you to modify their properties. If you find a writeable computer object, you can register a new computer account, modify the target server's delegation properties to trust your computer account, and request delegated tickets to impersonate high-privileged users.
* **Exploitation Objectives**:
  1. Identify computer objects where your account or group has write permissions (such as `GenericWrite` or `WriteDacl`).
  2. Register a new computer account inside the Active Directory database.
  3. Configure the target computer object to delegate authentication to your newly registered machine.
  4. Perform Kerberos S4U ticket requests to impersonate a domain administrator and access the target server.
* **Starting Credentials**:
  * User: `l6_r.worker`
  * Password: `WorkerPass2026!`
* **Flag Targets**:
  * Root/Administrator flag on the target server.

---

### 🧪 Lab 7: SQL Database Link Pivoting Lab (Cross-Subnet Database Pivot)
* **Background Scenario**: 
  To secure database assets, the organization isolates high-value backend database servers in a restricted subnet with no direct routing from the outer corporate network. However, to synchronize records, the frontend database server is allowed to communicate with the backend via database links or foreign data wrappers.
  
  You have accessed the network segment of the frontend database. You must search for database configuration backups, credentials, or web service parameters. Once you connect to the frontend database, you must discover existing database links connecting to the isolated backend database. Your goal is to execute queries across the database link to interact with the backend, and abuse database capabilities to run commands on the isolated operating system.
* **Exploitation Objectives**:
  1. Search local directories or logs for connection credentials.
  2. Connect to the frontend database instance and identify configured database links.
  3. Execute SQL statements across the database link targeting the backend database instance.
  4. Leverage database functions on the backend instance to read system files or execute operating system commands.
* **Scope Details**:
  * AD Domain: `10.106.10.10`
  * Frontend DB: `10.106.20.20`
  * Backend DB (Isolated): `10.106.10.20`
* **Flag Targets**:
  * System flag on the isolated backend server.

---

### 🧪 Lab 8: LAPS & Local Admin Password Leak Lab (AD Information Leakage)
* **Background Scenario**: 
  The corporate policy states that all local administrator passwords must be managed using the Local Administrator Password Solution (LAPS). However, legacy administration practices and migration scripts are known to copy these unique administrative credentials into standard, readable computer attributes.
  
  You have gained credentials for a standard domain audit account. Since this account has read-only access to standard Active Directory attributes, you must enumerate all computer objects in the domain and check standard and custom properties (such as descriptions, notes, or info attributes) for clear-text password leakage.
* **Exploitation Objectives**:
  1. Enumerate the computer accounts in the domain.
  2. Perform LDAP queries to inspect readable attributes (e.g., description, comment, info) of the computer objects.
  3. Extract any leaked administrative passwords.
  4. Use the recovered credentials to authenticate and log in as administrator on the target system.
* **Starting Credentials**:
  * User: `l8_audit_user`
  * Password: `AuditPass2026!`
* **Flag Targets**:
  * Administrator access on the finance server.

---

### 🧪 Lab 9: AD CS NTLM Relay (ESC8) & Trigger Lab (DC Coercion and Relay)
* **Background Scenario**: 
  The Certificate Authority (CA) in `ESC8LAB.LOCAL` provides a web-based enrollment interface (`/certsrv`) for users to request certificates. Because this interface does not enforce Channel Binding or HTTPS NTLM protections, it is vulnerable to NTLM relay attacks (ESC8).
  
  Operating as a standard domain user, your goal is to set up a relay handler targeting the CA web enrollment portal. You must then trigger an NTLM authentication request from the Domain Controller to your attacker listener using a coercion protocol (such as MS-RPRN or MS-EFSR). By relaying the coerced DC computer authentication to the CA, you can enroll and download a certificate for the Domain Controller machine account, allowing you to perform DCSync and extract all domain hashes.
* **Exploitation Objectives**:
  1. Verify the presence of the Certificate Authority web enrollment portal.
  2. Launch an NTLM relay listener configured to relay connections to the CA enrollment endpoint.
  3. Coerce NTLM authentication from the Domain Controller back to your listener.
  4. Relay the connection to obtain a certificate for the Domain Controller account, and use the certificate to execute a DCSync attack.
* **Starting Credentials**:
  * User: `l9_student` (password provided in lab credentials)
* **Flag Targets**:
  * Extracted Domain Controller password hashes.

---

### 🧪 Lab 10: Constrained Delegation (S4U) Lab (Protocol Transition Abuse)
* **Background Scenario**: 
  The web service account `l10_web_service` is used to run internal IIS portals. To allow the web portal to query backend databases, the service account is configured with Kerberos Constrained Delegation (S4U) with Protocol Transition.
  
  You have compromised the credentials of the web service account. You must audit the delegation properties of this account in Active Directory. Specifically, analyze what backend services are listed in the `msDS-AllowedToDelegateTo` attribute. Your goal is to abuse the Protocol Transition feature to impersonate a domain administrator, request a delegated Kerberos service ticket, and authenticate to the backend database server.
* **Exploitation Objectives**:
  1. Query Active Directory to inspect the delegation properties and SPNs of the compromised service account.
  2. Perform a Kerberos S4U2self request to impersonate a domain administrator to the service account.
  3. Perform a Kerberos S4U2proxy request to delegate that impersonation to the allowed backend database services.
  4. Authenticate to the backend server using the delegated ticket cache and read the flag.
* **Starting Credentials**:
  * User: `l10_web_service`
  * Password: `WebServPass123!`
* **Flag Targets**:
  * Flag located on the database server.

---