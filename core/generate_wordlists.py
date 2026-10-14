#!/usr/bin/env python3
"""
ADLabs Dynamic Wordlist & Credential Generator
Generates realistic randomized Active Directory user accounts and password wordlists.
Ensures students must perform genuine enumeration rather than memorizing static answers.
"""

import json
import os
import random
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
CREDENTIALS_STATE_FILE = BASE_DIR / "output" / "lab_credentials.json"

DEFAULT_LAB_CREDENTIALS = {
    "oscp-network-pivot-lab": {"user": "j.smith", "pass": "CorpSecurePass2026!1", "role": "Employee"},
    "multi-domain-forest-lab": {"user": "j.doe", "pass": "CorpSecurePass2026!1", "role": "Child Domain User"},
    "adcs-abuse-lab": {"user": "l3_j.doe", "pass": "StudentPass2026!", "role": "Domain Student"},
    "trust-pivoting-lab": {"user": "l4b_student", "pass": "SimpleStudentPass2026!", "role": "Forest B Student"},
    "gpo-admin-pivot-lab": {"user": "l5_operator", "pass": "OperatorPass2026!", "role": "Workstation Operator"},
    "rbcd-lab": {"user": "l6_r.worker", "pass": "WorkerPass2026!", "role": "Standard Worker"},
    "sql-pivot-lab": {"user": "l7_db_operator", "pass": "OperatorSecurePass2026!", "role": "DB Operator"},
    "laps-lab": {"user": "l8_audit_user", "pass": "AuditPass2026!", "role": "Audit Account"},
    "esc8-relay-lab": {"user": "l9_student", "pass": "StudentPass2026!", "role": "Relay Practice Student"},
    "delegation-s4u-lab": {"user": "l10_web_service", "pass": "WebServPass123!", "role": "Web Service Account"},
    "hybrid-cloud-aad-lab": {"user": "l11_t.intern", "pass": "InternPass2026!", "role": "AAD Connect Intern"},
    "sccm-mecm-pivot-lab": {"user": "l12_j.intern", "pass": "InternPass2026!", "role": "SCCM Support Intern"},
}

FIRST_NAMES = [
    "john", "jane", "bob", "alice", "charlie", "david", "emma", "frank", "grace", "henry",
    "isaac", "julia", "kevin", "laura", "michael", "nancy", "oscar", "paul", "quinn", "rachel",
    "steve", "tina", "ursula", "victor", "wendy", "xavier", "yvonne", "zach", "adam", "beth",
    "carl", "diana", "eric", "fiona", "george", "hannah", "ivan", "jessica", "keith", "lisa",
    "martin", "natalie", "oliver", "patricia", "quincy", "rebecca", "samuel", "tiffany", "ulric"
]

LAST_NAMES = [
    "smith", "jones", "brown", "wilson", "davis", "miller", "moore", "taylor", "anderson",
    "thomas", "jackson", "white", "harris", "martin", "thompson", "garcia", "martinez", "robinson",
    "clark", "rodriguez", "lewis", "lee", "walker", "hall", "allen", "young", "king", "wright",
    "scott", "torres", "nguyen", "hill", "flores", "green", "adams", "nelson", "baker", "rivera",
    "campbell", "mitchell", "carter", "roberts"
]

BASE_WORDS = [
    "Secure", "Pass", "Password", "Admin", "User", "Login", "Access", "Secret", "Key", "Auth",
    "Corp", "Lab", "Test", "Demo", "Prod", "Dev", "Staging", "System", "Service", "Account",
    "Winter", "Spring", "Summer", "Autumn", "Corporate", "Network", "Domain", "Global"
]

YEARS = ["2024", "2025", "2026", "2027", "2028"]
SPECIALS = ["!", "@", "#", "$", "%", "^", "&", "*", "-", "_"]

def generate_random_password():
    """Generates a strong, realistic corporate AD password."""
    word = random.choice(BASE_WORDS)
    year = random.choice(YEARS)
    special = random.choice(SPECIALS)
    num = random.randint(1, 99)
    patterns = [
        f"{word}{year}{special}{num}",
        f"{word}{special}{year}",
        f"{word}{num}{special}{year}",
        f"{word}Corp{year}{special}"
    ]
    return random.choice(patterns)

def generate_random_username(prefix=""):
    fn = random.choice(FIRST_NAMES)
    ln = random.choice(LAST_NAMES)
    u = f"{fn[0]}.{ln}"
    if prefix:
        return f"{prefix}{u}"
    return u

def generate_similar_users(count=50, prefix=""):
    out = set()
    while len(out) < count:
        out.add(generate_random_username(prefix=prefix))
    return list(out)

def generate_similar_passwords(count=50):
    out = set()
    while len(out) < count:
        out.add(generate_random_password())
    return list(out)

def load_lab_credentials():
    """Loads current active lab credentials from state file, or falls back to defaults."""
    if CREDENTIALS_STATE_FILE.exists():
        try:
            with open(CREDENTIALS_STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return DEFAULT_LAB_CREDENTIALS.copy()

def save_lab_credentials(creds):
    CREDENTIALS_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(CREDENTIALS_STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(creds, f, indent=2)
    except Exception as e:
        print(f"[-] Warning: Failed to save credentials state: {e}", file=sys.stderr)

def create_wordlist_for_lab(base_dir, lab_name, randomize=False):
    """
    Creates dynamic users.txt and pass.txt for a lab.
    If randomize is True, generates brand new unpredictable passwords and credentials.
    """
    state = load_lab_credentials()
    default_entry = DEFAULT_LAB_CREDENTIALS.get(lab_name, {"user": "j.smith", "pass": "CorpSecurePass2026!1", "role": "Employee"})

    # Determine prefix if lab has one
    prefix = ""
    default_user = default_entry["user"]
    if "_" in default_user and default_user.startswith("l"):
        prefix = default_user.split("_")[0] + "_"

    if randomize:
        correct_user = generate_random_username(prefix=prefix)
        correct_pass = generate_random_password()
        state[lab_name] = {
            "user": correct_user,
            "pass": correct_pass,
            "role": default_entry.get("role", "User")
        }
    else:
        # Use existing saved state or default
        entry = state.get(lab_name, default_entry)
        correct_user = entry["user"]
        correct_pass = entry["pass"]

    # Generate decoy wordlists (50 users, 50 passwords)
    all_users = [correct_user] + generate_similar_users(50, prefix=prefix)
    random.shuffle(all_users)

    all_passes = [correct_pass] + generate_similar_passwords(50)
    random.shuffle(all_passes)

    lab_dir = Path(base_dir) / "labs" / lab_name
    lab_dir.mkdir(parents=True, exist_ok=True)

    users_file = lab_dir / "users.txt"
    pass_file = lab_dir / "pass.txt"

    with open(users_file, "w", encoding="utf-8") as f:
        f.write("\n".join(all_users) + "\n")

    with open(pass_file, "w", encoding="utf-8") as f:
        f.write("\n".join(all_passes) + "\n")

    save_lab_credentials(state)

    return {
        "lab": lab_name,
        "user": correct_user,
        "pass": correct_pass,
        "users_count": len(all_users),
        "pass_count": len(all_passes)
    }

def generate_all_wordlists(base_dir=None, randomize=False):
    target = Path(base_dir) if base_dir else BASE_DIR
    results = []
    print(f"[*] Generating wordlists (randomize={randomize})...")
    for lab_name in DEFAULT_LAB_CREDENTIALS:
        res = create_wordlist_for_lab(target, lab_name, randomize=randomize)
        results.append(res)
        print(f"[+] Lab '{lab_name}': {res['users_count']} users, {res['pass_count']} passwords (Active: {res['user']})")
    print(f"[✓] Dynamic wordlists updated successfully for {len(results)} labs!")
    return results

def main():
    import argparse
    parser = argparse.ArgumentParser(description="ADLabs Dynamic Wordlist & Credential Generator")
    parser.add_argument("--randomize", "-r", action="store_true", help="Generate fresh randomized credentials and wordlists")
    parser.add_argument("--lab", "-l", type=str, help="Generate wordlist for a specific lab")
    parser.add_argument("--dir", "-d", type=str, default=str(BASE_DIR), help="Root directory of ADLabs")

    args = parser.parse_args()

    if args.lab:
        res = create_wordlist_for_lab(args.dir, args.lab, randomize=args.randomize)
        print(f"[+] Generated wordlists for {args.lab}: {res['user']} / {res['pass']}")
    else:
        generate_all_wordlists(args.dir, randomize=args.randomize)

if __name__ == "__main__":
    main()
