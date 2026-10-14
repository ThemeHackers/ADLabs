<?php
session_start();

$error = '';
$success = '';

// SQLite database initialization for vulnerable staff login
$db_file = '/tmp/staff_portal.db';
$db = new SQLite3($db_file);
$db->exec("CREATE TABLE IF NOT EXISTS staff_users (id INTEGER PRIMARY KEY, username TEXT, password TEXT, role TEXT, full_name TEXT)");
$check = $db->querySingle("SELECT COUNT(*) FROM staff_users");
if ($check == 0) {
    $db->exec("INSERT INTO staff_users (username, password, role, full_name) VALUES ('admin', 'MegaAdminSecret2026!', 'Administrator', 'System Admin')");
    $db->exec("INSERT INTO staff_users (username, password, role, full_name) VALUES ('support', 'SupportTeamPass2026!', 'Support', 'Support Desk')");
    $db->exec("INSERT INTO staff_users (username, password, role, full_name) VALUES ('j.smith', 'CorpSecurePass2026!1', 'Employee', 'John Smith')");
}

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    $username = $_POST['username'] ?? '';
    $password = $_POST['password'] ?? '';

    // Intentionally vulnerable SQL Injection (classic authentication bypass)
    $query = "SELECT * FROM staff_users WHERE username = '$username' AND password = '$password'";
    $result = $db->query($query);

    if ($result && ($row = $result->fetchArray(SQLITE3_ASSOC))) {
        $_SESSION['user'] = $row['username'];
        $_SESSION['role'] = $row['role'];
        $_SESSION['full_name'] = $row['full_name'];
        header("Location: portal.php");
        exit;
    } else {
        $error = "Invalid credentials. (Debug query: " . htmlspecialchars($query) . ")";
    }
}
?>
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>MegaCorp Staff Login</title>
    <style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: #0f172a; color: #f8fafc; margin: 0; padding: 0; }
        .navbar { background: #1e293b; padding: 1rem 2rem; border-bottom: 2px solid #3b82f6; display: flex; justify-content: space-between; align-items: center; }
        .logo { font-size: 1.5rem; font-weight: bold; color: #60a5fa; }
        .nav-links a { color: #cbd5e1; text-decoration: none; margin-left: 1.5rem; }
        .login-box { max-width: 440px; margin: 5rem auto; background: #1e293b; padding: 2.5rem; border-radius: 8px; border: 1px solid #334155; box-shadow: 0 10px 25px rgba(0,0,0,0.5); }
        .login-box h2 { margin-top: 0; color: #38bdf8; }
        .form-group { margin-bottom: 1.5rem; }
        label { display: block; margin-bottom: 0.5rem; font-size: 0.9rem; color: #cbd5e1; }
        input[type="text"], input[type="password"] { width: 100%; box-sizing: border-box; padding: 0.75rem; background: #0f172a; border: 1px solid #475569; border-radius: 4px; color: #f8fafc; }
        .btn { width: 100%; background: #2563eb; color: #fff; padding: 0.75rem; border: none; border-radius: 4px; font-weight: bold; cursor: pointer; }
        .btn:hover { background: #1d4ed8; }
        .alert-error { background: #7f1d1d; color: #fecaca; padding: 0.75rem; border-radius: 4px; margin-bottom: 1rem; font-size: 0.85rem; word-break: break-all; }
    </style>
</head>
<body>
    <div class="navbar">
        <div class="logo">⚡ MegaCorp IT Gateway</div>
        <div class="nav-links">
            <a href="index.php">Home</a>
            <a href="login.php">Staff Login</a>
            <a href="upload.php">Document Drop</a>
        </div>
    </div>
    <div class="login-box">
        <h2>Staff Portal Login</h2>
        <?php if ($error): ?>
            <div class="alert-error"><?= $error ?></div>
        <?php endif; ?>
        <form method="POST">
            <div class="form-group">
                <label>Username</label>
                <input type="text" name="username" placeholder="e.g. j.smith or admin" required>
            </div>
            <div class="form-group">
                <label>Password</label>
                <input type="password" name="password" placeholder="Password" required>
            </div>
            <button type="submit" class="btn">Sign In</button>
        </form>
    </div>
</body>
</html>
