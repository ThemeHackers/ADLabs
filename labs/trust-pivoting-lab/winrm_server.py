#!/usr/bin/env python3
"""
ADLabs Trust Pivoting Lab - WinRM Simulation Server
Wraps centralized core.winrm_server with lab-specific defaults.
"""
import os
import sys

# Default environment configurations for Trust Lab (Lab 4)
os.environ.setdefault("WINRM_HOSTNAME", "FORESTB-WS01")
os.environ.setdefault("WINRM_DOMAIN", "FORESTB.LOCAL")
os.environ.setdefault("WINRM_IP", "10.103.20.30")
os.environ.setdefault("WINRM_GATEWAY", "10.103.20.254")
os.environ.setdefault("WINRM_USERS", "j.forestb:ForestBUserPass2026!,Administrator:ForestBAdminPass2026!")
os.environ.setdefault("WINRM_FLAG", "OSCP{winrm_lateral_movement_forestb_pwned}")
os.environ.setdefault("WINRM_ADMIN_FLAG", "OSCP{cross_forest_trust_full_compromise}")

try:
    from core.winrm_server import main
except ImportError:
    # When mounted directly inside container or standalone
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    sys.path.insert(0, "/core")
    sys.path.insert(0, "/tmp")
    from winrm_server import main  # type: ignore

if __name__ == "__main__":
    main()
