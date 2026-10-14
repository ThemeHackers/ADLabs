# ADLabs Architecture & Directory Structure

This document outlines the architectural organization, network topology, and directory conventions used in **ADLabs**.

---

## 1. Directory Structure

```text
ADLabs/
├── adlabs.py                   # Main CLI & Interactive Dashboard
├── connect.bat                 # Windows shortcut to connect WireGuard
├── disconnect.bat              # Windows shortcut to disconnect WireGuard
├── README.md                   # Project overview & quick start
├── LICENSE                     # MIT License
├── .gitignore                  # Git ignore rules for runtime files and configs
│
├── core/                       # Core orchestration utilities
│   ├── configure_ad.py         # In-container Samba Domain Controller provisioning engine
│   ├── generate_wordlists.py   # Wordlist generator (users.txt & pass.txt)
│   ├── adlabs_daemon.py        # Background idle/timeout monitor daemon
│   └── uac.py                  # Windows UAC elevation helper
│
├── labs/                       # All 12 Active Directory Lab Scenarios
│   ├── oscp-network-pivot-lab/ # Lab 1: Multi-Tier Pivot & Forest Trust
│   ├── multi-domain-forest-lab/# Lab 2: Multi-Domain Forest Trust & Kerberoast
│   ├── adcs-abuse-lab/         # Lab 3: AD CS Certificate Templates (ESC1)
│   ├── trust-pivoting-lab/     # Lab 4: Cross-Forest External Trust Abuse
│   ├── gpo-admin-pivot-lab/    # Lab 5: GPO Task Injection & Workstation Join
│   ├── rbcd-lab/               # Lab 6: Resource-Based Constrained Delegation
│   ├── sql-pivot-lab/          # Lab 7: SQL Database Link Pivot
│   ├── laps-lab/               # Lab 8: LAPS Abuse & Pass-the-Ticket
│   ├── esc8-relay-lab/         # Lab 9: AD CS ESC8 Web Enrollment NTLM Relay
│   ├── delegation-s4u-lab/     # Lab 10: Constrained Delegation S4U
│   ├── hybrid-cloud-aad-lab/   # Lab 11: Hybrid Cloud Azure AD Connect & DCSync
│   └── sccm-mecm-pivot-lab/    # Lab 12: SCCM/MECM Network Pivot & Client Push
│
├── scripts/                    # Platform launcher scripts
│   ├── windows/                # Windows Batch launchers (with UAC elevation)
│   │   ├── connect.bat
│   │   └── disconnect.bat
│   └── linux/                  # Linux Shell launchers (with wg-quick & sudo)
│       ├── connect.sh
│       └── disconnect.sh
│
├── output/                     # Centralized runtime outputs (gitignored)
│   └── vpn/                    # Generated WireGuard client .conf profiles
│
├── logs/                       # Daemon and execution logs (gitignored)
│   └── adlabs_daemon.log       # Background daemon logs
│
└── docs/                       # Architecture and scenario documentation
    └── architecture.md         # This document
```

---

## 2. Network Isolation & Dynamic Allocation

- **Subnet Allocation**: Each lab runs in its own private Docker network (`10.x.x.x/24`), completely non-overlapping with other labs.
- **VPN Subnet Allocation**: Client connections use `10.252.<lab_id>.0/24` with client IP `10.252.<lab_id>.2`.
- **WireGuard Host Port**: Automatically allocated starting at UDP port `51820` without collision.
- **Central DNS Router (`adlabs-dns`)**: Automatically translates lab domain names (`*.local`) to their corresponding domain controller IP addresses.
