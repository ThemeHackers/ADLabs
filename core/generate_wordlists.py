import random
import sys
from pathlib import Path
BASE_DIR = Path(__file__).resolve().parent.parent
LAB_CREDENTIALS = {
    "oscp-network-pivot-lab": {"user": "j.smith", "pass": "CorpSecurePass2026!1"},
    "multi-domain-forest-lab": {"user": "j.doe", "pass": "CorpSecurePass2026!1"},
    "adcs-abuse-lab": {"user": "l3_j.doe", "pass": "StudentPass2026!"},
    "trust-pivoting-lab": {"user": "l4b_student", "pass": "SimpleStudentPass2026!"},
    "gpo-admin-pivot-lab": {"user": "l5_operator", "pass": "OperatorPass2026!"},
    "rbcd-lab": {"user": "l6_r.worker", "pass": "WorkerPass2026!"},
    "sql-pivot-lab": {"user": "l7_db_operator", "pass": "OperatorSecurePass2026!"},
    "laps-lab": {"user": "l8_audit_user", "pass": "AuditPass2026!"},
    "esc8-relay-lab": {"user": "l9_student", "pass": "StudentPass2026!"},
    "delegation-s4u-lab": {"user": "l10_web_service", "pass": "WebServPass123!"},
    "hybrid-cloud-aad-lab": {"user": "l11_t.intern", "pass": "InternPass2026!"},
    "sccm-mecm-pivot-lab": {"user": "l12_j.intern", "pass": "InternPass2026!"},
}
FIRST_NAMES = ["john", "jane", "bob", "alice", "charlie", "david", "emma", "frank", "grace", "henry", "isaac", "julia", "kevin", "laura", "michael", "nancy", "oscar", "paul", "quinn", "rachel", "steve", "tina", "ursula", "victor", "wendy", "xavier", "yvonne", "zach", "adam", "beth", "carl", "diana", "eric", "fiona", "george", "hannah", "ivan", "jessica", "keith", "lisa", "martin", "natalie", "oliver", "patricia", "quincy", "rebecca", "samuel", "tiffany", "ulric"]
LAST_NAMES = ["smith", "jones", "brown", "wilson", "davis", "miller", "moore", "taylor", "anderson", "thomas", "jackson", "white", "harris", "martin", "thompson", "garcia", "martinez", "robinson", "clark", "rodriguez", "lewis", "lee", "walker", "hall", "allen", "young", "king", "wright", "scott", "torres", "nguyen", "hill", "flores", "green", "adams", "nelson", "baker", "rivera", "campbell", "mitchell", "carter", "roberts"]
BASE_WORDS = ["Secure", "Pass", "Password", "Admin", "User", "Login", "Access", "Secret", "Key", "Auth", "Corp", "Lab", "Test", "Demo", "Prod", "Dev", "Staging", "System", "Service", "Account"]
YEARS = ["2024", "2025", "2026", "2027", "2028"]
SPECIALS = ["!", "@", "$", "%", "^", "&", "*", "-", "_", "+", "="]
def generate_similar_users(count=50):
    out = []
    for _ in range(count):
        out.append(FIRST_NAMES[random.randrange(len(FIRST_NAMES))][0] + "." + LAST_NAMES[random.randrange(len(LAST_NAMES))])
    return out
def generate_similar_passwords(count=50):
    out = []
    for _ in range(count):
        out.append(BASE_WORDS[random.randrange(len(BASE_WORDS))] + YEARS[random.randrange(len(YEARS))] + SPECIALS[random.randrange(len(SPECIALS))] + str(random.randint(1, 999)))
    return out
def create_wordlist_for_lab(base_dir, lab_name, credentials):
    correct_user = credentials["user"]
    correct_pass = credentials["pass"]
    all_users = [correct_user] + generate_similar_users(50)
    random.shuffle(all_users)
    all_passes = [correct_pass] + generate_similar_passwords(50)
    random.shuffle(all_passes)
    lab_dir = Path(base_dir) / lab_name
    lab_dir.mkdir(parents=True, exist_ok=True)
    with open(lab_dir / "users.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(all_users) + "\n")
    with open(lab_dir / "pass.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(all_passes) + "\n")
    print("[+] Created wordlists for " + lab_name)
    print("    - users.txt: " + str(len(all_users)) + " entries (correct: " + correct_user + ")")
    print("    - pass.txt: " + str(len(all_passes)) + " entries (correct: " + correct_pass + ")")
def main(base_dir=None):
    target = Path(base_dir) if base_dir else BASE_DIR
    for lab_name, credentials in LAB_CREDENTIALS.items():
        create_wordlist_for_lab(target, lab_name, credentials)
    print("\n[+] All wordlists generated successfully!")
if __name__ == "__main__":
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else BASE_DIR
    main(root)
