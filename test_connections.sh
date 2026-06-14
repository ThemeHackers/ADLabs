#!/bin/bash
# Active Directory Labs Connection Test Utility (Linux/macOS - Kali)
# Run this script while connected to the respective WireGuard VPN to verify access.


RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
GRAY='\033[0;90m'
NC='\033[0m' 

test_ping() {
    local ip=$1
   
    if [[ "$OSTYPE" == "darwin"* ]]; then
        ping -c 1 -t 1 "$ip" >/dev/null 2>&1
    else
        ping -c 1 -W 1 "$ip" >/dev/null 2>&1
    fi
    return $?
}

test_port() {
    local ip=$1
    local port=$2
    if command -v nc >/dev/null 2>&1; then
        nc -z -w 1 "$ip" "$port" >/dev/null 2>&1
        return $?
    elif [ -e /dev/tcp ]; then
        timeout 1 bash -c "cat < /dev/null > /dev/tcp/$ip/$port" >/dev/null 2>&1
        return $?
    else
       
        python3 -c "import socket; s = socket.socket(); s.settimeout(1); s.connect(('$ip', $port))" >/dev/null 2>&1
        return $?
    fi
}

echo -e "${CYAN}==========================================================${NC}"
echo -e "${CYAN}    ACTIVE DIRECTORY LABS CONNECTIVITY TESTER (LINUX/MAC)  ${NC}"
echo -e "${CYAN}==========================================================${NC}"
echo -e "${GRAY}Note: You must activate the respective WireGuard profile first.${NC}"
echo ""

# Lab 1
echo -e "${YELLOW}--- Lab 1: Network Pivot Lab ---${NC}"
echo -e "${GRAY}Expected VPN Profile: oscp-pivot-lab.conf (Port 51820)${NC}"
for target in "Perimeter Web UI:10.10.10.80:9000" "ad-forest-parent (MEGACORP):10.100.10.10:88,389,445" "ad-forest-child (HQ):10.100.10.20:88,389,445"; do
    name=$(echo $target | cut -d: -f1)
    ip=$(echo $target | cut -d: -f2)
    ports=$(echo $target | cut -d: -f3 | tr ',' ' ')
    
    if test_ping "$ip"; then
        echo -e "  [${GREEN}+${NC}] $name ($ip) is reachable (Ping: OK)"
        for port in $ports; do
            if test_port "$ip" "$port"; then
                echo -e "      ${GREEN}└─ TCP Port $port is OPEN${NC}"
            else
                echo -e "      ${RED}└─ TCP Port $port is CLOSED${NC}"
            fi
        done
    else
        echo -e "  [${RED}-${NC}] $name ($ip) is UNREACHABLE (Ping: Timeout)"
    fi
done
echo ""

# Lab 2
echo -e "${YELLOW}--- Lab 2: Multi-Domain Forest Lab ---${NC}"
echo -e "${GRAY}Expected VPN Profile: multi-domain-forest-lab.conf (Port 51821)${NC}"
for target in "mega-dc-parent (MEGACORP):10.101.10.10:88,389,445" "mega-dc-child (HQ):10.101.20.10:88,389,445" "mega-dc-tree (CYBERTECH):10.101.30.10:88,389,445"; do
    name=$(echo $target | cut -d: -f1)
    ip=$(echo $target | cut -d: -f2)
    ports=$(echo $target | cut -d: -f3 | tr ',' ' ')
    
    if test_ping "$ip"; then
        echo -e "  [${GREEN}+${NC}] $name ($ip) is reachable (Ping: OK)"
        for port in $ports; do
            if test_port "$ip" "$port"; then
                echo -e "      ${GREEN}└─ TCP Port $port is OPEN${NC}"
            else
                echo -e "      ${RED}└─ TCP Port $port is CLOSED${NC}"
            fi
        done
    else
        echo -e "  [${RED}-${NC}] $name ($ip) is UNREACHABLE (Ping: Timeout)"
    fi
done
echo ""

# Lab 3
echo -e "${YELLOW}--- Lab 3: AD CS Certificate Abuse Lab ---${NC}"
echo -e "${GRAY}Expected VPN Profile: oscp-adcs-lab.conf (Port 51822)${NC}"
for target in "adcs-ca-mock (Mock CA Web):10.102.20.20:80" "adcs-dc (DC & Mock PKINIT):10.102.10.10:389,445,8000"; do
    name=$(echo $target | cut -d: -f1)
    ip=$(echo $target | cut -d: -f2)
    ports=$(echo $target | cut -d: -f3 | tr ',' ' ')
    
    if test_ping "$ip"; then
        echo -e "  [${GREEN}+${NC}] $name ($ip) is reachable (Ping: OK)"
        for port in $ports; do
            if test_port "$ip" "$port"; then
                echo -e "      ${GREEN}└─ TCP Port $port is OPEN${NC}"
            else
                echo -e "      ${RED}└─ TCP Port $port is CLOSED${NC}"
            fi
        done
    else
        echo -e "  [${RED}-${NC}] $name ($ip) is UNREACHABLE (Ping: Timeout)"
    fi
done
echo ""

# Lab 4
echo -e "${YELLOW}--- Lab 4: Trust & Forest Pivoting Lab ---${NC}"
echo -e "${GRAY}Expected VPN Profile: oscp-trust-lab.conf (Port 51823)${NC}"
for target in "dc-foresta (FORESTA):10.103.10.10:88,389,445" "dc-forestb (FORESTB):10.103.20.10:88,389,445"; do
    name=$(echo $target | cut -d: -f1)
    ip=$(echo $target | cut -d: -f2)
    ports=$(echo $target | cut -d: -f3 | tr ',' ' ')
    
    if test_ping "$ip"; then
        echo -e "  [${GREEN}+${NC}] $name ($ip) is reachable (Ping: OK)"
        for port in $ports; do
            if test_port "$ip" "$port"; then
                echo -e "      ${GREEN}└─ TCP Port $port is OPEN${NC}"
            else
                echo -e "      ${RED}└─ TCP Port $port is CLOSED${NC}"
            fi
        done
    else
        echo -e "  [${RED}-${NC}] $name ($ip) is UNREACHABLE (Ping: Timeout)"
    fi
done
echo ""

# Lab 5
echo -e "${YELLOW}--- Lab 5: GPO & Workstation Pivot Lab ---${NC}"
echo -e "${GRAY}Expected VPN Profile: oscp-gpo-lab.conf (Port 51824)${NC}"
for target in "gpo-dc (GPOLAB):10.104.10.10:389,445" "gpo-client-sim (Client):10.104.20.20:"; do
    name=$(echo $target | cut -d: -f1)
    ip=$(echo $target | cut -d: -f2)
    ports=$(echo $target | cut -d: -f3 | tr ',' ' ' | sed 's/ *$//')
    
    if test_ping "$ip"; then
        echo -e "  [${GREEN}+${NC}] $name ($ip) is reachable (Ping: OK)"
        for port in $ports; do
            if [ -n "$port" ]; then
                if test_port "$ip" "$port"; then
                    echo -e "      ${GREEN}└─ TCP Port $port is OPEN${NC}"
                else
                    echo -e "      ${RED}└─ TCP Port $port is CLOSED${NC}"
                fi
            fi
        done
    else
        echo -e "  [${RED}-${NC}] $name ($ip) is UNREACHABLE (Ping: Timeout)"
    fi
done
echo ""

# Lab 6
echo -e "${YELLOW}--- Lab 6: Resource-Based Constrained Delegation (RBCD) ---${NC}"
echo -e "${GRAY}Expected VPN Profile: oscp-rbcd-lab.conf (Port 51825)${NC}"
for target in "rbcd-dc (DC):10.105.10.10:88,389,445" "rbcd-target-srv (Target Web Server):10.105.20.20:80"; do
    name=$(echo $target | cut -d: -f1)
    ip=$(echo $target | cut -d: -f2)
    ports=$(echo $target | cut -d: -f3 | tr ',' ' ' | sed 's/ *$//')
    
    if test_ping "$ip"; then
        echo -e "  [${GREEN}+${NC}] $name ($ip) is reachable (Ping: OK)"
        for port in $ports; do
            if [ -n "$port" ]; then
                if test_port "$ip" "$port"; then
                    echo -e "      ${GREEN}└─ TCP Port $port is OPEN${NC}"
                else
                    echo -e "      ${RED}└─ TCP Port $port is CLOSED${NC}"
                fi
            fi
        done
    else
        echo -e "  [${RED}-${NC}] $name ($ip) is UNREACHABLE (Ping: Timeout)"
    fi
done
echo ""

# Lab 7
echo -e "${YELLOW}--- Lab 7: SQL Database Link Pivoting ---${NC}"
echo -e "${GRAY}Expected VPN Profile: oscp-sql-lab.conf (Port 51826)${NC}"
for target in "sql-dc (DC):10.106.10.10:88,389,445" "sql-front (SQL Front-End DB):10.106.20.20:5432" "sql-back (SQL Back-End DB):10.106.10.20:5432"; do
    name=$(echo $target | cut -d: -f1)
    ip=$(echo $target | cut -d: -f2)
    ports=$(echo $target | cut -d: -f3 | tr ',' ' ' | sed 's/ *$//')
    
    if test_ping "$ip"; then
        echo -e "  [${GREEN}+${NC}] $name ($ip) is reachable (Ping: OK)"
        for port in $ports; do
            if [ -n "$port" ]; then
                if test_port "$ip" "$port"; then
                    echo -e "      ${GREEN}└─ TCP Port $port is OPEN${NC}"
                else
                    echo -e "      ${RED}└─ TCP Port $port is CLOSED${NC}"
                fi
            fi
        done
    else
        echo -e "  [${RED}-${NC}] $name ($ip) is UNREACHABLE (Ping: Timeout)"
    fi
done
echo ""

# Lab 8
echo -e "${YELLOW}--- Lab 8: LAPS & Local Admin Password Leak ---${NC}"
echo -e "${GRAY}Expected VPN Profile: oscp-laps-lab.conf (Port 51827)${NC}"
for target in "laps-dc (DC):10.107.10.10:88,389,445" "laps-finance-srv (Finance Web Server):10.107.20.20:80"; do
    name=$(echo $target | cut -d: -f1)
    ip=$(echo $target | cut -d: -f2)
    ports=$(echo $target | cut -d: -f3 | tr ',' ' ' | sed 's/ *$//')
    
    if test_ping "$ip"; then
        echo -e "  [${GREEN}+${NC}] $name ($ip) is reachable (Ping: OK)"
        for port in $ports; do
            if [ -n "$port" ]; then
                if test_port "$ip" "$port"; then
                    echo -e "      ${GREEN}└─ TCP Port $port is OPEN${NC}"
                else
                    echo -e "      ${RED}└─ TCP Port $port is CLOSED${NC}"
                fi
            fi
        done
    else
        echo -e "  [${RED}-${NC}] $name ($ip) is UNREACHABLE (Ping: Timeout)"
    fi
done
echo ""

# Lab 9
echo -e "${YELLOW}--- Lab 9: AD CS NTLM Relay (ESC8) & Trigger ---${NC}"
echo -e "${GRAY}Expected VPN Profile: oscp-esc8-lab.conf (Port 51828)${NC}"
for target in "esc8-dc (DC & Trigger API):10.108.10.10:389,445,9999" "esc8-ca-web (Mock CA Web):10.108.20.20:80"; do
    name=$(echo $target | cut -d: -f1)
    ip=$(echo $target | cut -d: -f2)
    ports=$(echo $target | cut -d: -f3 | tr ',' ' ' | sed 's/ *$//')
    
    if test_ping "$ip"; then
        echo -e "  [${GREEN}+${NC}] $name ($ip) is reachable (Ping: OK)"
        for port in $ports; do
            if [ -n "$port" ]; then
                if test_port "$ip" "$port"; then
                    echo -e "      ${GREEN}└─ TCP Port $port is OPEN${NC}"
                else
                    echo -e "      ${RED}└─ TCP Port $port is CLOSED${NC}"
                fi
            fi
        done
    else
        echo -e "  [${RED}-${NC}] $name ($ip) is UNREACHABLE (Ping: Timeout)"
    fi
done
echo ""

# Lab 10
echo -e "${YELLOW}--- Lab 10: Constrained Delegation (S4U) ---${NC}"
echo -e "${GRAY}Expected VPN Profile: oscp-delegation-lab.conf (Port 51829)${NC}"
for target in "deleg-dc (DC):10.109.10.10:88,389,445" "deleg-db (Target DB Web Console):10.109.20.20:80"; do
    name=$(echo $target | cut -d: -f1)
    ip=$(echo $target | cut -d: -f2)
    ports=$(echo $target | cut -d: -f3 | tr ',' ' ' | sed 's/ *$//')
    
    if test_ping "$ip"; then
        echo -e "  [${GREEN}+${NC}] $name ($ip) is reachable (Ping: OK)"
        for port in $ports; do
            if [ -n "$port" ]; then
                if test_port "$ip" "$port"; then
                    echo -e "      ${GREEN}└─ TCP Port $port is OPEN${NC}"
                else
                    echo -e "      ${RED}└─ TCP Port $port is CLOSED${NC}"
                fi
            fi
        done
    else
        echo -e "  [${RED}-${NC}] $name ($ip) is UNREACHABLE (Ping: Timeout)"
    fi
done
echo ""

echo -e "${CYAN}Connection checks complete.${NC}"
