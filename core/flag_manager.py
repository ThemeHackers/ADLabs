#!/usr/bin/env python3
"""
ADLabs Flag Verification & Progressive Hint System
Manages randomized local.txt and proof.txt flags, scoring, and multi-tier hints.
"""

import hashlib
import json
import os
import random
import sys
import time
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
FLAGS_DB_PATH = BASE_DIR / "output" / "adlabs_flags.json"

LAB_METADATA = {
    "oscp-network-pivot-lab": {
        "index": 1,
        "title": "OSCP Network Pivoting & Full-Loop AD Lab",
        "local_host": "10.10.10.80 (DMZ Perimeter Web Server)",
        "local_path": "/home/www-data/local.txt",
        "local_pts": 10,
        "proof_host": "10.100.10.10 (Parent Forest DC)",
        "proof_path": "/root/proof.txt or C:\\Users\\Administrator\\Desktop\\proof.txt",
        "proof_pts": 40,
        "hints": [
            "Tier 1 (Recon): Scan the perimeter IP 10.10.10.80 on port 80. Identify the web application technology and public endpoints.",
            "Tier 2 (Foothold): The staff login form (/login.php) accepts unsanitized user inputs. Alternatively, inspect the document attachment portal (/upload.php) for unrestricted extension filtering.",
            "Tier 3 (PrivEsc): Check low-privilege sudo permissions (`sudo -l`). Look for binary execution or writable automation scripts in /opt.",
            "Tier 4 (AD Pivot): Inspect /root/pivot_notes.txt. Pivot through 10.10.10.80 using SSH dynamic port forwarding or Chisel to reach the PostgreSQL DB at 10.20.20.20 and the AD DC at 10.100.10.10. Extract LDAP bind creds, then perform Kerberoasting/AS-REP Roasting."
        ]
    },
    "multi-domain-forest-lab": {
        "index": 2,
        "title": "Multi-Domain Active Directory Forest Trust Lab",
        "local_host": "10.101.20.10 (Child Domain DC / Standard User)",
        "local_path": "Desktop\\local.txt",
        "local_pts": 10,
        "proof_host": "10.101.10.10 (Parent Forest Root DC)",
        "proof_path": "Desktop\\proof.txt",
        "proof_pts": 40,
        "hints": [
            "Tier 1 (Recon): Connect to WireGuard and enumerate child DC at 10.101.20.10 using netexec/crackmapexec with credentials from users.txt and pass.txt.",
            "Tier 2 (Foothold): Authenticate as the child domain user and run impacket-GetUserSPNs to discover Kerberoastable SPNs across the forest.",
            "Tier 3 (PrivEsc): Crack the retrieved TGS hash using hashcat/john with pass.txt. The compromised service account has GenericWrite permissions.",
            "Tier 4 (Forest Esc): Exploit msDS-KeyCredentialLink (Shadow Credentials) or forge an Inter-Realm TGT with SID History for Parent RID 500 to gain Enterprise Admin."
        ]
    },
    "adcs-abuse-lab": {
        "index": 3,
        "title": "Active Directory Certificate Services (ADCS) ESC1 Abuse",
        "local_host": "10.102.10.10 (Standard Domain User)",
        "local_path": "Desktop\\local.txt",
        "local_pts": 10,
        "proof_host": "10.102.10.10 (ADCS Domain Controller)",
        "proof_path": "Desktop\\proof.txt",
        "proof_pts": 40,
        "hints": [
            "Tier 1 (Recon): Use certipy or find-certificate-templates over LDAP to discover active Enterprise CAs in ADCSLAB.LOCAL.",
            "Tier 2 (Foothold): Identify template 'ESC1-WebServer'. Inspect flags: CT_FLAG_ENROLLEE_SUPPLIES_SUBJECT and Client Authentication EKU.",
            "Tier 3 (Exploit): Run certipy req -u <user> -p <pass> -target 10.102.20.20 -ca ADCSLAB-CA -template ESC1-WebServer -upn Administrator@ADCSLAB.LOCAL.",
            "Tier 4 (Domain Admin): Authenticate with the obtained PFX certificate via certipy auth to retrieve the NT hash of Domain Administrator."
        ]
    },
    "trust-pivoting-lab": {
        "index": 4,
        "title": "Cross-Forest External Trust Pivoting Lab",
        "local_host": "10.103.20.30 (Forest B Workstation / WinRM)",
        "local_path": "Desktop\\local.txt",
        "local_pts": 10,
        "proof_host": "10.103.10.10 (Forest A Domain Controller)",
        "proof_path": "Desktop\\proof.txt",
        "proof_pts": 40,
        "hints": [
            "Tier 1 (Recon): Connect to Forest B on 10.103.20.10 and workstation 10.103.20.30 via WinRM (port 5985).",
            "Tier 2 (Foothold): Log into 10.103.20.30 using evil-winrm with Forest B student credentials.",
            "Tier 3 (Trust Enum): Enumerate domain trusts with netexec or impacket. Notice bidirectional trust between forestb.local and foresta.local.",
            "Tier 4 (Cross-Forest): Check group memberships. The Forest B user or foreign security principal has GenericWrite over Forest A Domain Admins."
        ]
    },
    "gpo-admin-pivot-lab": {
        "index": 5,
        "title": "GPO Abuse & Workstation Pivot Lab",
        "local_host": "10.104.20.20 (Workstation GPO Client)",
        "local_path": "/flag.txt",
        "local_pts": 10,
        "proof_host": "10.104.10.10 (GPOLab Domain Controller)",
        "proof_path": "/root/flag.txt",
        "proof_pts": 40,
        "hints": [
            "Tier 1 (Recon): Enumerate GPOs linked to the Domain or Workstations OU using pyGPOAbuse or netexec.",
            "Tier 2 (Foothold): Operator user has Write/Modify permissions over the default GPO or startup scripts.",
            "Tier 3 (Abuse): Inject a reverse shell or new local admin user into SYSVOL startup scripts or Immediate Scheduled Tasks.",
            "Tier 4 (Elevation): Wait for the client workstation (10.104.20.20) to refresh GPO policy, granting administrative execution."
        ]
    },
    "rbcd-lab": {
        "index": 6,
        "title": "Resource-Based Constrained Delegation (RBCD) Lab",
        "local_host": "10.105.10.10 (Standard Domain Worker)",
        "local_path": "Desktop\\local.txt",
        "local_pts": 10,
        "proof_host": "10.105.20.20 (Target Workstation / Server)",
        "proof_path": "Desktop\\proof.txt",
        "proof_pts": 30,
        "hints": [
            "Tier 1 (Recon): Worker account has GenericWrite permissions over target computer object WORKSTATION01$.",
            "Tier 2 (Machine Account): Check ms-DS-MachineAccountQuota. Create a new computer account using impacket-addcomputer.",
            "Tier 3 (RBCD Config): Configure msDS-AllowedToActOnBehalfOfOtherIdentity using impacket-rbcd pointing to your new computer account.",
            "Tier 4 (S4U2Self): Request service ticket via S4U2Self/S4U2Proxy impersonating Administrator and connect via evil-winrm/wmiexec."
        ]
    },
    "sql-pivot-lab": {
        "index": 7,
        "title": "MSSQL Linked Servers & xp_cmdshell Pivot Lab",
        "local_host": "10.106.10.20 (Initial SQL Server 1)",
        "local_path": "C:\\local.txt",
        "local_pts": 10,
        "proof_host": "10.106.10.10 (Domain Controller)",
        "proof_path": "C:\\proof.txt",
        "proof_pts": 30,
        "hints": [
            "Tier 1 (Recon): Connect to MSSQL on 10.106.10.20 using impacket-mssqlclient with DB operator credentials.",
            "Tier 2 (Linked Servers): Query linked database servers with `EXEC sp_linkedservers`.",
            "Tier 3 (Execution): Crawl through linked SQL server chains and enable `xp_cmdshell` using `sp_configure`.",
            "Tier 4 (PrivEsc): Execute commands as SQL service account and extract service ticket or impersonate sysadmin."
        ]
    },
    "laps-lab": {
        "index": 8,
        "title": "LAPS Password Leak & Local Admin Pivot Lab",
        "local_host": "10.107.20.20 (Finance Server / WinRM)",
        "local_path": "/flag.txt",
        "local_pts": 10,
        "proof_host": "10.107.10.10 (LAPS Domain Controller)",
        "proof_path": "/root/flag.txt",
        "proof_pts": 30,
        "hints": [
            "Tier 1 (Recon): Connect to LDAP on 10.107.10.10 with audit user credentials.",
            "Tier 2 (LAPS Query): Query computer objects for attribute `ms-Mcs-AdmPwd` using netexec or ldapsearch.",
            "Tier 3 (Password Retrieval): Extract the plaintext local administrator password for FINANCE-SRV.",
            "Tier 4 (WinRM Foothold): Connect to 10.107.20.20 on port 5985 via evil-winrm or netexec with Administrator and the extracted LAPS password."
        ]
    },
    "esc8-relay-lab": {
        "index": 9,
        "title": "ADCS ESC8 Web Enrollment NTLM Relay Lab",
        "local_host": "10.108.20.20 (HTTP Web CA Enrollment)",
        "local_path": "/tmp/local.txt",
        "local_pts": 10,
        "proof_host": "10.108.10.10 (Domain Controller)",
        "proof_path": "/tmp/proof.txt",
        "proof_pts": 30,
        "hints": [
            "Tier 1 (Recon): Scan 10.108.20.20 port 80. Identify ADCS HTTP web enrollment endpoint (/certsrv/).",
            "Tier 2 (Relay Setup): Set up ntlmrelayx targeting http://10.108.20.20/certsrv/certfnsh.asp with --adcs --template DomainController.",
            "Tier 3 (Coerce): Trigger authentication from the Domain Controller using PetitPotam or printerbug.",
            "Tier 4 (PKINIT): Use the relayed certificate with PKINIT to obtain the DC machine NT hash."
        ]
    },
    "delegation-s4u-lab": {
        "index": 10,
        "title": "Constrained Delegation (S4U2Self & S4U2Proxy) Lab",
        "local_host": "10.109.10.10 (Web Service Host)",
        "local_path": "Desktop\\local.txt",
        "local_pts": 10,
        "proof_host": "10.109.10.10 (Domain Controller)",
        "proof_path": "Desktop\\proof.txt",
        "proof_pts": 30,
        "hints": [
            "Tier 1 (Recon): Enumerate accounts with msDS-AllowedToDelegateTo configured.",
            "Tier 2 (Foothold): Compromise web_service account credentials or extract its Kerberos key.",
            "Tier 3 (S4U Request): Use impacket-getST with -spn cifs/dc.delegation.local -impersonate Administrator.",
            "Tier 4 (TGS Impersonation): Export KRB5CCNAME and access CIFS/WMI on the Domain Controller."
        ]
    },
    "hybrid-cloud-aad-lab": {
        "index": 11,
        "title": "Hybrid Cloud Azure AD / Entra ID Connect Sync Lab",
        "local_host": "10.111.20.20 (AAD Connect Sync Server)",
        "local_path": "Desktop\\local.txt",
        "local_pts": 10,
        "proof_host": "10.111.10.10 (On-Prem Domain Controller)",
        "proof_path": "Desktop\\proof.txt",
        "proof_pts": 30,
        "hints": [
            "Tier 1 (Recon): Enumerate sync server at 10.111.20.20 with intern credentials.",
            "Tier 2 (Foothold): Locate local SQL LocalDB instance used by Microsoft Azure AD Sync.",
            "Tier 3 (Credential Dump): Dump MSOL service account encrypted credentials using AADInternals or addecrypt.",
            "Tier 4 (DCSync): MSOL account holds Replicating Directory Changes permissions. Run secretsdump to DCSync the DC."
        ]
    },
    "sccm-mecm-pivot-lab": {
        "index": 12,
        "title": "SCCM / MECM Site Server & DP Lateral Movement Lab",
        "local_host": "10.112.20.20 (SCCM Site Server)",
        "local_path": "Desktop\\local.txt",
        "local_pts": 10,
        "proof_host": "10.112.10.10 (Management Domain Controller)",
        "proof_path": "Desktop\\proof.txt",
        "proof_pts": 30,
        "hints": [
            "Tier 1 (Recon): Scan 10.112.20.20 for SCCM Web portal (port 80) and SMB share SMSPKGD$.",
            "Tier 2 (Network Pivot): Connect via SSH to pivot host 10.112.20.20 using intern credentials.",
            "Tier 3 (SCCM Creds): Inspect SCCM configuration files and network access accounts (NAA) stored on distribution point.",
            "Tier 4 (Domain Admin): The SCCM Computer Account is member of Domain Admins or has Full Control over the DC."
        ]
    }
}

def generate_flag_hash(lab_name, flag_type):
    entropy = f"{lab_name}:{flag_type}:{time.time()}:{random.randint(100000, 999999)}"
    h = hashlib.sha256(entropy.encode()).hexdigest()[:24]
    return f"OSCP{{{flag_type}_{h}}}"

def load_flags_db():
    if FLAGS_DB_PATH.exists():
        try:
            with open(FLAGS_DB_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def save_flags_db(db):
    FLAGS_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(FLAGS_DB_PATH, "w", encoding="utf-8") as f:
        json.dump(db, f, indent=2)

def init_flags_for_all_labs(force_regenerate=False):
    db = load_flags_db() if not force_regenerate else {}
    for lab_name, meta in LAB_METADATA.items():
        if lab_name not in db or force_regenerate:
            db[lab_name] = {
                "index": meta["index"],
                "title": meta["title"],
                "local": {
                    "flag": generate_flag_hash(lab_name, "local"),
                    "points": meta["local_pts"],
                    "host": meta["local_host"],
                    "path": meta["local_path"],
                    "solved": False,
                    "solved_at": None
                },
                "proof": {
                    "flag": generate_flag_hash(lab_name, "proof"),
                    "points": meta["proof_pts"],
                    "host": meta["proof_host"],
                    "path": meta["proof_path"],
                    "solved": False,
                    "solved_at": None
                },
                "unlocked_hints": 0
            }
    save_flags_db(db)
    return db

def submit_flag(flag_input):
    """
    Submits a flag string. Returns dict with status and details.
    """
    cleaned = flag_input.strip()
    db = load_flags_db()
    if not db:
        db = init_flags_for_all_labs()

    for lab_name, data in db.items():
        for ftype in ["local", "proof"]:
            if data[ftype]["flag"] == cleaned:
                if data[ftype]["solved"]:
                    return {
                        "status": "already_solved",
                        "lab": lab_name,
                        "title": data["title"],
                        "type": ftype,
                        "points": data[ftype]["points"],
                        "solved_at": data[ftype]["solved_at"],
                        "total_score": calculate_score(db)
                    }
                else:
                    data[ftype]["solved"] = True
                    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    data[ftype]["solved_at"] = now
                    save_flags_db(db)
                    return {
                        "status": "success",
                        "lab": lab_name,
                        "title": data["title"],
                        "type": ftype,
                        "points": data[ftype]["points"],
                        "solved_at": now,
                        "total_score": calculate_score(db)
                    }

    return {
        "status": "invalid",
        "flag": cleaned,
        "total_score": calculate_score(db)
    }

def calculate_score(db=None):
    if db is None:
        db = load_flags_db()
    score = 0
    for lab in db.values():
        if lab["local"]["solved"]:
            score += lab["local"]["points"]
        if lab["proof"]["solved"]:
            score += lab["proof"]["points"]
    return score

def get_hints(lab_identifier, tier=None):
    """
    Returns progressive hints for a lab by name or index.
    Unlocks next tier if tier is None.
    """
    db = load_flags_db()
    if not db:
        db = init_flags_for_all_labs()

    matched_name = None
    target_str = str(lab_identifier).strip().lower()

    for name, meta in LAB_METADATA.items():
        if target_str == str(meta["index"]) or target_str == name.lower():
            matched_name = name
            break

    if not matched_name:
        return None, "Lab not found."

    meta = LAB_METADATA[matched_name]
    all_hints = meta["hints"]
    current_unlocked = db.get(matched_name, {}).get("unlocked_hints", 0)

    if tier is not None:
        idx = max(0, min(int(tier) - 1, len(all_hints) - 1))
        return meta, all_hints[idx]

    # Progressive unlock: unlock next tier
    next_tier = min(current_unlocked + 1, len(all_hints))
    if matched_name in db:
        db[matched_name]["unlocked_hints"] = next_tier
        save_flags_db(db)

    revealed = all_hints[:next_tier]
    return meta, revealed
