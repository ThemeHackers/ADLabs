# Active Directory Lab Environments (OSCP/OSCP+ Preparation)

This workspace contains ten lightweight, containerized Active Directory (AD) lab environments tailored for pentesting practice and OSCP/OSCP+ preparation. It replaces heavy Windows virtual machines with Docker containers running Samba AD Domain Controllers, Linux routers, and dedicated WireGuard VPN gateways.

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

## 2. Lab Practice Scenarios

### Lab 1: Network Pivoting Lab
* **Focus**: Internal pivot routing, basic AD vulnerabilities, and credentials harvesting.
* **Attack Paths**: AS-REP Roasting (`svc_backups`), Kerberoasting (`sql_service`), Unconstrained Delegation (`svc_delegate`), SYSVOL GPP AES password decryption, and pivoting through a Linux firewall router.
* **Practice Credentials**: [credentials.txt](./oscp-network-pivot-lab/oscp_exam_assets/credentials.txt)

### Lab 2: Multi-Domain Forest Lab
* **Focus**: Pivoting through trust boundaries, child-to-parent domain escalation, and tree acquisition trust pivoting.
* **Practice Credentials**: [credentials.txt](./multi-domain-forest-lab/credentials.txt)

### Lab 3: AD CS Certificate Abuse Lab
* **Focus**: Active Directory Certificate Services template abuse (ESC1) and PKINIT authentication flow.
* **Attack Paths**: Request a certificate from the CA Web enrollment page at `http://10.102.20.20/certsrv` utilizing the vulnerable `ESC1` template and specifying UPN: `Administrator@ADCSLAB.LOCAL` in the SAN. Submit the signed certificate to the authentication mock gateway at `http://10.102.10.10:8000/pkinit` to compromise the DC.

### Lab 4: Trust & Forest Pivoting Lab
* **Focus**: Cross-forest Trust abuse, SID History injection, and trust routing.
* **Attack Paths**: Compromise low-privilege student credentials on Forest B: `student:SimpleStudentPass2026!`. Map the cross-forest trust to `FORESTA.LOCAL`. Abuse foreign security principal group memberships or SID History to pivot and gain domain administration privileges on Forest A.

### Lab 5: GPO & Client Workstation Pivot Lab
* **Focus**: GPO shared script write privilege abuse and workstation post-exploitation.
* **Attack Paths**: Gain access to student operator account: `operator:OperatorPass2026!`. Modify the shared GPO startup script at `\\10.104.10.10\sysvol\gpolab.local\scripts\update.sh` to get execution on the workstation.

### Lab 6: Resource-Based Constrained Delegation (RBCD) Lab
* **Focus**: RBCD computer account takeover and S4U ticket generation.
* **Attack Paths**: Log in as `r.worker:WorkerPass2026!`. Register a new computer account `COMP-ATTACKER$` and modify the `msDS-AllowedToActOnBehalfOfOtherIdentity` attribute of `SRV-TARGET` to trust `COMP-ATTACKER$`. Request S4U Kerberos tickets to compromise `SRV-TARGET`.

### Lab 7: SQL Database Link Pivoting Lab
* **Focus**: PostgreSQL database links, user mapping configuration, and OS command execution.
* **Attack Paths**: Compromise credentials in a backup file `/var/lib/postgresql/db_backup.cfg` on the frontend SQL server `10.106.20.20`. Connect to the frontend and execute system commands on the backend SQL database `10.106.10.20` using database linking / foreign server mappings.

### Lab 8: LAPS & Local Admin Password Leak Lab
* **Focus**: AD attribute enumeration and local administrator takeover.
* **Attack Paths**: Enumerate computer descriptions using `audit_user:AuditPass2026!`. Retrieve the local administrator password of `srv-finance` leaked in the `description` attribute. Use the password to compromise the finance server.

### Lab 9: AD CS NTLM Relay (ESC8) & Trigger Lab
* **Focus**: NTLM coercion (PetitPotam/Printer Bug) and Web Enrollment relaying.
* **Attack Paths**: Start `ntlmrelayx` targetting the AD CS web interface at `http://10.108.20.20`. Trigger authentication from the DC `10.108.10.10:9999/trigger?ip=<YOUR_IP>` to relay Domain Admin/DC credentials to AD CS and extract a certificate.

### Lab 10: Constrained Delegation (S4U) Lab
* **Focus**: Kerberos constrained delegation and ticket impersonation.
* **Attack Paths**: Gain access to `web_service:WebServPass123!`. Use Impacket's `getST.py` S4U2self/S4U2proxy protocol features to request a delegation ticket for `Administrator` to the `cifs` service on `deleg-db` (`10.109.20.20`).

---

## 3. How to Connect via WireGuard

1. Install the **WireGuard Client** on your attacking machine (Windows or Kali Linux).
2. Import the individual `.conf` configuration profile of the lab you want to target, or import the pre-packaged **`ADLabs-WireGuard.zip`** file directly into the WireGuard Client to load all 10 lab profiles at once.
3. Activate the tunnel.
4. Target the containers directly via their `10.x.x.x` IPs.

> [!WARNING]
> Only activate **one lab tunnel at a time** in your WireGuard Client to prevent routing and DNS resolution conflicts on your host.

