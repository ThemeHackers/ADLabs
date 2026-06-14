# Active Directory Labs Connection Test Utility (Windows PowerShell)
# Run this script while connected to the respective WireGuard VPN to verify access.

$ErrorActionPreference = "SilentlyContinue"

$labs = @(
    [PSCustomObject]@{
        Name = "Lab 1: Network Pivot Lab"
        VPN = "oscp-pivot-lab.conf (Port 51820)"
        Targets = @(
            @{ Name = "Perimeter Web UI"; IP = "10.10.10.80"; Ports = @(9000) }
            @{ Name = "ad-forest-parent (MEGACORP)"; IP = "10.100.10.10"; Ports = @(88, 389, 445) }
            @{ Name = "ad-forest-child (HQ)"; IP = "10.100.10.20"; Ports = @(88, 389, 445) }
        )
    },
    [PSCustomObject]@{
        Name = "Lab 2: Multi-Domain Forest Lab"
        VPN = "multi-domain-forest-lab.conf (Port 51821)"
        Targets = @(
            @{ Name = "mega-dc-parent (MEGACORP)"; IP = "10.101.10.10"; Ports = @(88, 389, 445) }
            @{ Name = "mega-dc-child (HQ)"; IP = "10.101.20.10"; Ports = @(88, 389, 445) }
            @{ Name = "mega-dc-tree (CYBERTECH)"; IP = "10.101.30.10"; Ports = @(88, 389, 445) }
        )
    },
    [PSCustomObject]@{
        Name = "Lab 3: AD CS Certificate Abuse Lab"
        VPN = "oscp-adcs-lab.conf (Port 51822)"
        Targets = @(
            @{ Name = "adcs-ca-mock (Mock CA Web)"; IP = "10.102.20.20"; Ports = @(80) }
            @{ Name = "adcs-dc (DC & Mock PKINIT)"; IP = "10.102.10.10"; Ports = @(389, 445, 8000) }
        )
    },
    [PSCustomObject]@{
        Name = "Lab 4: Trust & Forest Pivoting Lab"
        VPN = "oscp-trust-lab.conf (Port 51823)"
        Targets = @(
            @{ Name = "dc-foresta (FORESTA)"; IP = "10.103.10.10"; Ports = @(88, 389, 445) }
            @{ Name = "dc-forestb (FORESTB)"; IP = "10.103.20.10"; Ports = @(88, 389, 445) }
        )
    },
    [PSCustomObject]@{
        Name = "Lab 5: GPO & Workstation Pivot Lab"
        VPN = "oscp-gpo-lab.conf (Port 51824)"
        Targets = @(
            @{ Name = "gpo-dc (GPOLAB)"; IP = "10.104.10.10"; Ports = @(389, 445) }
            @{ Name = "gpo-client-sim (Client)"; IP = "10.104.20.20"; Ports = @() }
        )
    },
    [PSCustomObject]@{
        Name = "Lab 6: Resource-Based Constrained Delegation (RBCD)"
        VPN = "oscp-rbcd-lab.conf (Port 51825)"
        Targets = @(
            @{ Name = "rbcd-dc (DC)"; IP = "10.105.10.10"; Ports = @(88, 389, 445) }
            @{ Name = "rbcd-target-srv (Target Web Server)"; IP = "10.105.20.20"; Ports = @(80) }
        )
    },
    [PSCustomObject]@{
        Name = "Lab 7: SQL Database Link Pivoting"
        VPN = "oscp-sql-lab.conf (Port 51826)"
        Targets = @(
            @{ Name = "sql-dc (DC)"; IP = "10.106.10.10"; Ports = @(88, 389, 445) }
            @{ Name = "sql-front (SQL Front-End DB)"; IP = "10.106.20.20"; Ports = @(5432) }
            @{ Name = "sql-back (SQL Back-End DB)"; IP = "10.106.10.20"; Ports = @(5432) }
        )
    },
    [PSCustomObject]@{
        Name = "Lab 8: LAPS & Local Admin Password Leak"
        VPN = "oscp-laps-lab.conf (Port 51827)"
        Targets = @(
            @{ Name = "laps-dc (DC)"; IP = "10.107.10.10"; Ports = @(88, 389, 445) }
            @{ Name = "laps-finance-srv (Finance Web Server)"; IP = "10.107.20.20"; Ports = @(80) }
        )
    },
    [PSCustomObject]@{
        Name = "Lab 9: AD CS NTLM Relay (ESC8) & Trigger"
        VPN = "oscp-esc8-lab.conf (Port 51828)"
        Targets = @(
            @{ Name = "esc8-dc (DC & Trigger API)"; IP = "10.108.10.10"; Ports = @(389, 445, 9999) }
            @{ Name = "esc8-ca-web (Mock CA Web)"; IP = "10.108.20.20"; Ports = @(80) }
        )
    },
    [PSCustomObject]@{
        Name = "Lab 10: Constrained Delegation (S4U)"
        VPN = "oscp-delegation-lab.conf (Port 51829)"
        Targets = @(
            @{ Name = "deleg-dc (DC)"; IP = "10.109.10.10"; Ports = @(88, 389, 445) }
            @{ Name = "deleg-db (Target DB Web Console)"; IP = "10.109.20.20"; Ports = @(80) }
        )
    }
)

function Test-TcpPort {
    param(
        [string]$IP,
        [int]$Port
    )
    $tcp = New-Object System.Net.Sockets.TcpClient
    $connection = $tcp.BeginConnect($IP, $Port, $null, $null)
    $success = $connection.AsyncWaitHandle.WaitOne(1000, $false)
    if ($success) {
        $tcp.EndConnect($connection)
        $tcp.Close()
        return $true
    }
    return $false
}

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "    ACTIVE DIRECTORY LABS CONNECTIVITY TESTER (WINDOWS)   " -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "Note: You must activate the respective WireGuard profile first." -ForegroundColor Gray
Write-Host ""

foreach ($lab in $labs) {
    Write-Host "--- $($lab.Name) ---" -ForegroundColor Yellow
    Write-Host "Expected VPN Profile: $($lab.VPN)" -ForegroundColor Gray
    
    foreach ($target in $lab.Targets) {
        # Test Ping
        $ping = Test-Connection -ComputerName $target.IP -Count 1 -Delay 1 -TimeToLive 64 -Quiet
        if ($ping) {
            Write-Host "  [+] $($target.Name) ($($target.IP)) is reachable (Ping: OK)" -ForegroundColor Green
            
            # Test Ports
            foreach ($port in $target.Ports) {
                $port_ok = Test-TcpPort -IP $target.IP -Port $port
                if ($port_ok) {
                    Write-Host "      └─ TCP Port $port is OPEN" -ForegroundColor Green
                } else {
                    Write-Host "      └─ TCP Port $port is CLOSED" -ForegroundColor Red
                }
            }
        } else {
            Write-Host "  [-] $($target.Name) ($($target.IP)) is UNREACHABLE (Ping: Timeout)" -ForegroundColor Red
        }
    }
    Write-Host ""
}
Write-Host "Connection checks complete." -ForegroundColor Cyan
