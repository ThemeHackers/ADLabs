<?php
session_start();
if (!isset($_SESSION['user'])) {
    header("Location: login.php");
    exit;
}
?>
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>MegaCorp Staff Portal</title>
    <style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: #0f172a; color: #f8fafc; margin: 0; padding: 0; }
        .navbar { background: #1e293b; padding: 1rem 2rem; border-bottom: 2px solid #3b82f6; display: flex; justify-content: space-between; align-items: center; }
        .logo { font-size: 1.5rem; font-weight: bold; color: #60a5fa; }
        .nav-links a { color: #cbd5e1; text-decoration: none; margin-left: 1.5rem; }
        .container { max-width: 900px; margin: 3rem auto; padding: 0 1rem; }
        .welcome-card { background: #1e293b; padding: 2rem; border-radius: 8px; border: 1px solid #334155; margin-bottom: 2rem; }
        .notice { background: #1e3a8a; border-left: 4px solid #3b82f6; padding: 1rem; border-radius: 4px; margin-top: 1rem; }
        code { background: #0f172a; padding: 0.2rem 0.4rem; border-radius: 4px; color: #38bdf8; font-family: monospace; }
        .btn { display: inline-block; background: #2563eb; color: #fff; padding: 0.6rem 1.2rem; border-radius: 4px; text-decoration: none; font-weight: 600; margin-top: 1rem; }
    </style>
</head>
<body>
    <div class="navbar">
        <div class="logo">⚡ MegaCorp IT Gateway</div>
        <div class="nav-links">
            <a href="portal.php">Dashboard</a>
            <a href="upload.php">Upload File</a>
            <a href="logout.php">Logout (<?= htmlspecialchars($_SESSION['user']) ?>)</a>
        </div>
    </div>
    <div class="container">
        <div class="welcome-card">
            <h2>Welcome back, <?= htmlspecialchars($_SESSION['full_name'] ?? $_SESSION['user']) ?>!</h2>
            <p>Role: <code><?= htmlspecialchars($_SESSION['role'] ?? 'Staff') ?></code></p>
            <div class="notice">
                <strong>Internal Infrastructure Synchronization Notice:</strong><br>
                Staff accounts are synchronized automatically to the child domain <code>HQ.MEGACORP.LOCAL</code>.<br>
                Automated database sync service binds via PostgreSQL at <code>10.20.20.20:5432</code> with AD Bind account <code>l1_j.doe:SimplePass2026!</code>.
            </div>
            <a href="upload.php" class="btn">Proceed to Document Upload &rarr;</a>
        </div>
    </div>
</body>
</html>
