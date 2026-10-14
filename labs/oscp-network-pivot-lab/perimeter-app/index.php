<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>MegaCorp Global Network - Perimeter Access Gateway</title>
    <style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: #0f172a; color: #f8fafc; margin: 0; padding: 0; }
        .navbar { background: #1e293b; padding: 1rem 2rem; border-bottom: 2px solid #3b82f6; display: flex; justify-content: space-between; align-items: center; }
        .logo { font-size: 1.5rem; font-weight: bold; color: #60a5fa; }
        .nav-links a { color: #cbd5e1; text-decoration: none; margin-left: 1.5rem; font-weight: 500; }
        .nav-links a:hover { color: #60a5fa; }
        .hero { text-align: center; padding: 4rem 2rem; max-width: 800px; margin: 0 auto; }
        .hero h1 { font-size: 2.5rem; margin-bottom: 1rem; color: #ffffff; }
        .hero p { font-size: 1.1rem; color: #94a3b8; line-height: 1.6; }
        .cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 2rem; max-width: 1000px; margin: 2rem auto; padding: 0 1rem; }
        .card { background: #1e293b; border-radius: 8px; padding: 2rem; border: 1px solid #334155; }
        .card h3 { color: #38bdf8; margin-top: 0; }
        .card p { color: #94a3b8; font-size: 0.95rem; }
        .btn { display: inline-block; background: #2563eb; color: #fff; padding: 0.6rem 1.2rem; border-radius: 4px; text-decoration: none; font-weight: 600; margin-top: 1rem; }
        .btn:hover { background: #1d4ed8; }
        .badge { display: inline-block; background: #065f46; color: #34d399; padding: 0.2rem 0.6rem; border-radius: 9999px; font-size: 0.8rem; font-weight: bold; margin-bottom: 0.5rem; }
        footer { text-align: center; padding: 2rem; color: #64748b; font-size: 0.85rem; border-top: 1px solid #1e293b; margin-top: 3rem; }
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
    <div class="hero">
        <span class="badge">SECURE DMZ NODE 10.10.10.80</span>
        <h1>Corporate Perimeter Services</h1>
        <p>Welcome to MegaCorp's external demarcation zone. Authorized personnel may access support services, ticketing file attachments, and internal synchronization dashboards.</p>
    </div>
    <div class="cards">
        <div class="card">
            <h3>Staff Authentication Portal</h3>
            <p>Access the corporate employee self-service area. Authorized staff accounts are synchronized with the internal Active Directory forest.</p>
            <a href="login.php" class="btn">Employee Login &rarr;</a>
        </div>
        <div class="card">
            <h3>Ticket & Document Drop</h3>
            <p>Upload support attachments, crash logs, or billing documents for automated IT processing.</p>
            <a href="upload.php" class="btn">Upload Files &rarr;</a>
        </div>
    </div>
    <footer>
        &copy; 2026 MegaCorp International Inc. All rights reserved. Perimeter Node: DMZ-SRV01
    </footer>
</body>
</html>
