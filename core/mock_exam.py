#!/usr/bin/env python3
"""
ADLabs OSCP Mock Exam Simulator (24-Hour Blind Exam Engine)
Simulates a realistic 24-hour OSCP exam session with blind targets, randomized attack paths,
real-time scoring, and strict exam constraints.
"""

import json
import os
import random
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
EXAM_SESSION_PATH = BASE_DIR / "output" / "mock_exam_session.json"

try:
    from core.flag_manager import init_flags_for_all_labs, load_flags_db, LAB_METADATA
except ImportError:
    from flag_manager import init_flags_for_all_labs, load_flags_db, LAB_METADATA

AD_CORE_CANDIDATES = [
    "oscp-network-pivot-lab",
    "multi-domain-forest-lab",
    "trust-pivoting-lab",
    "adcs-abuse-lab"
]

STANDALONE_CANDIDATES = [
    "rbcd-lab",
    "laps-lab",
    "gpo-admin-pivot-lab",
    "delegation-s4u-lab",
    "sql-pivot-lab"
]

def load_exam_session():
    if EXAM_SESSION_PATH.exists():
        try:
            with open(EXAM_SESSION_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return None

def save_exam_session(session):
    EXAM_SESSION_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(EXAM_SESSION_PATH, "w", encoding="utf-8") as f:
        json.dump(session, f, indent=2)

def start_mock_exam(duration_hours=24):
    existing = load_exam_session()
    if existing and existing.get("status") == "active":
        now = time.time()
        if now < existing.get("end_time", 0):
            return False, "An active exam session is already in progress. Use 'exam status' or 'exam stop'."

    flags_db = load_flags_db()
    if not flags_db:
        flags_db = init_flags_for_all_labs(force_regenerate=True)

    # Pick 1 Primary AD Forest / Pivot Lab (40 points)
    ad_lab = random.choice(AD_CORE_CANDIDATES)
    # Pick 2 Standalone / Pivot Machines (30 points each = 60 points)
    standalone_labs = random.sample(STANDALONE_CANDIDATES, 2)

    selected_labs = [ad_lab] + standalone_labs
    targets = []

    target_letters = ["ALPHA", "BRAVO", "CHARLIE"]
    total_max_points = 0

    for idx, lab_name in enumerate(selected_labs):
        meta = LAB_METADATA[lab_name]
        flag_info = flags_db[lab_name]
        letter = target_letters[idx]

        is_ad = (idx == 0)
        target_role = "Active Directory Pivot & Domain Set (Primary Network Target)" if is_ad else "Standalone Pivot / Privilege Escalation Target"
        pts = 40 if is_ad else 30
        total_max_points += pts

        targets.append({
            "code": f"TARGET-{letter}",
            "lab_name": lab_name,
            "role": target_role,
            "local_ip": meta["local_host"].split()[0],
            "points_possible": pts,
            "local_pts": 10,
            "proof_pts": pts - 10,
            "local_flag": flag_info["local"]["flag"],
            "proof_flag": flag_info["proof"]["flag"],
            "local_solved": False,
            "proof_solved": False,
            "local_solved_at": None,
            "proof_solved_at": None
        })

    start_time = time.time()
    end_time = start_time + (duration_hours * 3600)

    session = {
        "status": "active",
        "started_at": datetime.fromtimestamp(start_time).strftime("%Y-%m-%d %H:%M:%S"),
        "start_time": start_time,
        "end_time": end_time,
        "duration_hours": duration_hours,
        "passing_score": 70,
        "current_score": 0,
        "max_score": 100,
        "passed": False,
        "targets": targets
    }

    save_exam_session(session)
    return True, session

def get_exam_status():
    session = load_exam_session()
    if not session:
        return None, "No active exam session found. Start one with 'adlabs exam start'."

    now = time.time()
    if session["status"] == "active" and now >= session["end_time"]:
        session["status"] = "expired"
        save_exam_session(session)

    remaining_seconds = max(0, int(session["end_time"] - now))
    rem_h = remaining_seconds // 3600
    rem_m = (remaining_seconds % 3600) // 60
    rem_s = remaining_seconds % 60
    time_str = f"{rem_h:02d}h {rem_m:02d}m {rem_s:02d}s"

    # Recalculate score
    current_score = 0
    for t in session["targets"]:
        if t["local_solved"]:
            current_score += t["local_pts"]
        if t["proof_solved"]:
            current_score += t["proof_pts"]
    session["current_score"] = current_score
    if current_score >= session["passing_score"]:
        session["passed"] = True
    save_exam_session(session)

    return session, {
        "remaining_seconds": remaining_seconds,
        "remaining_str": time_str,
        "score": current_score,
        "passed": session["passed"]
    }

def submit_exam_flag(flag_input):
    session = load_exam_session()
    if not session or session.get("status") != "active":
        return {"status": "no_exam", "message": "No active exam session."}

    now = time.time()
    if now >= session["end_time"]:
        session["status"] = "expired"
        save_exam_session(session)
        return {"status": "expired", "message": "Exam time has expired (24-hour limit reached)."}

    cleaned = flag_input.strip()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    for t in session["targets"]:
        if t["local_flag"] == cleaned:
            if t["local_solved"]:
                return {"status": "already_solved", "target": t["code"], "type": "local", "points": t["local_pts"]}
            t["local_solved"] = True
            t["local_solved_at"] = now_str
            session["current_score"] += t["local_pts"]
            if session["current_score"] >= session["passing_score"]:
                session["passed"] = True
            save_exam_session(session)
            return {"status": "success", "target": t["code"], "type": "local", "points": t["local_pts"], "total_score": session["current_score"]}

        if t["proof_flag"] == cleaned:
            if t["proof_solved"]:
                return {"status": "already_solved", "target": t["code"], "type": "proof", "points": t["proof_pts"]}
            t["proof_solved"] = True
            t["proof_solved_at"] = now_str
            session["current_score"] += t["proof_pts"]
            if session["current_score"] >= session["passing_score"]:
                session["passed"] = True
            save_exam_session(session)
            return {"status": "success", "target": t["code"], "type": "proof", "points": t["proof_pts"], "total_score": session["current_score"]}

    return {"status": "invalid", "message": "Flag does not match any active exam targets."}

def stop_mock_exam():
    session = load_exam_session()
    if not session:
        return False, "No active exam session."

    session["status"] = "stopped"
    session["stopped_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    save_exam_session(session)
    return True, session
