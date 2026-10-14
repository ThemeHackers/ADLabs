<?php
session_start();

$message = '';
$upload_dir = __DIR__ . '/uploads/';
if (!is_dir($upload_dir)) {
    mkdir($upload_dir, 0777, true);
}

if ($_SERVER['REQUEST_METHOD'] === 'POST' && isset($_FILES['file'])) {
    $file = $_FILES['file'];
    $filename = basename($file['name']);
    $target_file = $upload_dir . $filename;
    
    // Intentionally loose/vulnerable file upload check (typical OSCP scenario)
    // Blacklists only .exe, but permits PHP webshells (.php, .phtml, .php5)
    $ext = strtolower(pathinfo($filename, PATHINFO_EXTENSION));
    if ($ext === 'exe') {
        $message = '<div class="alert-error">Executable files (.exe) are strictly prohibited!</div>';
    } else {
        if (move_uploaded_file($file['tmp_name'], $target_file)) {
            $message = '<div class="alert-success">File successfully uploaded! Access it here: <a href="uploads/' . htmlspecialchars($filename) . '" target="_blank">uploads/' . htmlspecialchars($filename) . '</a></div>';
        } else {
            $message = '<div class="alert-error">Failed to save uploaded file.</div>';
        }
    }
}
?>
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>MegaCorp Document Attachment Drop</title>
    <style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: #0f172a; color: #f8fafc; margin: 0; padding: 0; }
        .navbar { background: #1e293b; padding: 1rem 2rem; border-bottom: 2px solid #3b82f6; display: flex; justify-content: space-between; align-items: center; }
        .logo { font-size: 1.5rem; font-weight: bold; color: #60a5fa; }
        .nav-links a { color: #cbd5e1; text-decoration: none; margin-left: 1.5rem; }
        .box { max-width: 550px; margin: 4rem auto; background: #1e293b; padding: 2.5rem; border-radius: 8px; border: 1px solid #334155; box-shadow: 0 10px 25px rgba(0,0,0,0.5); }
        .box h2 { margin-top: 0; color: #38bdf8; }
        .form-group { margin-bottom: 1.5rem; }
        label { display: block; margin-bottom: 0.5rem; font-size: 0.9rem; color: #cbd5e1; }
        input[type="file"] { width: 100%; box-sizing: border-box; padding: 0.5rem; background: #0f172a; border: 1px dashed #475569; border-radius: 4px; color: #cbd5e1; }
        .btn { width: 100%; background: #2563eb; color: #fff; padding: 0.75rem; border: none; border-radius: 4px; font-weight: bold; cursor: pointer; }
        .btn:hover { background: #1d4ed8; }
        .alert-error { background: #7f1d1d; color: #fecaca; padding: 0.75rem; border-radius: 4px; margin-bottom: 1rem; }
        .alert-success { background: #065f46; color: #a7f3d0; padding: 0.75rem; border-radius: 4px; margin-bottom: 1rem; word-break: break-all; }
        .alert-success a { color: #fff; text-decoration: underline; font-weight: bold; }
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
    <div class="box">
        <h2>Support Ticket Attachment Upload</h2>
        <p style="color: #94a3b8; font-size: 0.9rem;">Upload documents, logs, or diagnostic screenshots for the MegaCorp Infrastructure & Active Directory team.</p>
        <?= $message ?>
        <form method="POST" enctype="multipart/form-data">
            <div class="form-group">
                <label>Select Attachment (PDF, DOCX, TXT, LOG)</label>
                <input type="file" name="file" required>
            </div>
            <button type="submit" class="btn">Upload to DMZ Storage</button>
        </form>
    </div>
</body>
</html>
