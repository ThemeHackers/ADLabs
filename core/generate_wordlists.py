import random
import string


lab_credentials = {
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
}

def generate_similar_users(correct_user, count=50):
    """Generate 50 similar usernames"""
    similar = []
    first_names = ["john", "jane", "bob", "alice", "charlie", "david", "emma", "frank", "grace", "henry",
                   "isaac", "julia", "kevin", "laura", "michael", "nancy", "oscar", "paul", "quinn", "rachel",
                   "steve", "tina", "ursula", "victor", "wendy", "xavier", "yvonne", "zach", "adam", "beth",
                   "carl", "diana", "eric", "fiona", "george", "hannah", "ivan", "jessica", "keith", "lisa",
                   "martin", "natalie", "oliver", "patricia", "quincy", "rebecca", "samuel", "tiffany", "ulric"]
    last_names = ["smith", "jones", "brown", "wilson", "davis", "miller", "moore", "taylor", "anderson", "thomas",
                  "jackson", "white", "harris", "martin", "thompson", "garcia", "martinez", "robinson", "clark", "rodriguez",
                  "lewis", "lee", "walker", "hall", "allen", "young", "king", "wright", "scott", "torres",
                  "nguyen", "hill", "flores", "green", "adams", "nelson", "baker", "hall", "rivera", "campbell",
                  "mitchell", "carter", "roberts"]
    
    for i in range(count):
        first = random.choice(first_names)
        last = random.choice(last_names)
        similar.append(f"{first[0]}.{last}")
    
    return similar

def generate_similar_passwords(correct_pass, count=50):
    """Generate 50 similar passwords"""
    similar = []
    base_words = ["Secure", "Pass", "Password", "Admin", "User", "Login", "Access", "Secret", "Key", "Auth",
                  "Corp", "Lab", "Test", "Demo", "Prod", "Dev", "Staging", "System", "Service", "Account"]
    years = ["2024", "2025", "2026", "2027", "2028"]
    specials = ["!", "@", "#", "$", "%", "^", "&", "*", "(", ")", "-", "_", "+", "="]
    
    for i in range(count):
        word = random.choice(base_words)
        year = random.choice(years)
        special = random.choice(specials)
        num = random.randint(1, 999)
        similar.append(f"{word}{year}{special}{num}")
    
    return similar

def create_wordlist_for_lab(lab_name, credentials):
    """Create users.txt and pass.txt for a lab"""
    correct_user = credentials["user"]
    correct_pass = credentials["pass"]
    

    similar_users = generate_similar_users(correct_user, 50)
    all_users = [correct_user] + similar_users
    random.shuffle(all_users)

    similar_passes = generate_similar_passwords(correct_pass, 50)
    all_passes = [correct_pass] + similar_passes
    random.shuffle(all_passes)
    

    users_path = f"c:\\Users\\1com310568\\Downloads\\ADLabs\\{lab_name}\\users.txt"
    with open(users_path, "w") as f:
        for user in all_users:
            f.write(user + "\n")
    

    pass_path = f"c:\\Users\\1com310568\\Downloads\\ADLabs\\{lab_name}\\pass.txt"
    with open(pass_path, "w") as f:
        for password in all_passes:
            f.write(password + "\n")
    
    print(f"[+] Created wordlists for {lab_name}")
    print(f"    - users.txt: {len(all_users)} entries (correct: {correct_user})")
    print(f"    - pass.txt: {len(all_passes)} entries (correct: {correct_pass})")



for lab_name, credentials in lab_credentials.items():
    create_wordlist_for_lab(lab_name, credentials)

print("\n[+] All wordlists generated successfully!")
