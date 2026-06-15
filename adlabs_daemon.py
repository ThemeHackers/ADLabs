import os
import sys
import time
import argparse
import subprocess

def log_message(msg):
    log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "adlabs_daemon.log")
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] {msg}\n")
    print(f"[{timestamp}] {msg}")

def is_container_running(container_name):
    try:
        res = subprocess.run(
            ["docker", "inspect", "--format", "{{.State.Running}}", container_name],
            capture_output=True, text=True, timeout=10
        )
        return res.stdout.strip() == "true"
    except Exception as e:
        log_message(f"Error checking container status: {e}")
        return False

def get_wg_stats(container_name):
    try:
        res = subprocess.run(
            ["docker", "exec", container_name, "wg", "show", "all", "dump"],
            capture_output=True, text=True, timeout=10
        )
        if res.returncode != 0:
            return None
        
        lines = res.stdout.strip().split("\n")
        if len(lines) <= 1:
            return None
        
        max_handshake = 0
        total_rx = 0
        total_tx = 0
        
        for line in lines[1:]:
            parts = line.split("\t")
            if len(parts) >= 8:
                try:
                    handshake = int(parts[4])
                    rx = int(parts[5])
                    tx = int(parts[6])
                    
                    if handshake > max_handshake:
                        max_handshake = handshake
                    total_rx += rx
                    total_tx += tx
                except ValueError:
                    continue
                    
        return max_handshake, total_rx, total_tx
    except Exception as e:
        log_message(f"Error retrieving WireGuard stats: {e}")
        return None

def main():
    parser = argparse.ArgumentParser(description="ADLabs Background Orchestration Daemon")
    parser.add_argument("--lab-dir", required=True, help="Absolute path to the lab directory")
    parser.add_argument("--wg-container", required=True, help="WireGuard container name")
    parser.add_argument("--timeout", type=int, default=7200, help="Absolute timeout in seconds")
    parser.add_argument("--idle-timeout", type=int, default=900, help="Inactivity timeout in seconds")
    
    args = parser.parse_args()
    
    lab_name = os.path.basename(args.lab_dir)
    log_message(f"Daemon started for lab '{lab_name}' (WG: {args.wg_container}). Max lifetime: {args.timeout}s, Idle timeout: {args.idle_timeout}s")
    
    start_time = time.time()
    last_active_time = time.time()
    
    prev_rx = 0
    prev_tx = 0
    has_connected_once = False
    
    for _ in range(30):
        if is_container_running(args.wg_container):
            break
        time.sleep(2)
        
    if not is_container_running(args.wg_container):
        log_message(f"WireGuard container '{args.wg_container}' did not start. Exiting daemon.")
        sys.exit(1)
        
    log_message(f"Container '{args.wg_container}' is running. Starting monitoring loop.")
    
    while True:
        time.sleep(30)
        
        if not is_container_running(args.wg_container):
            log_message(f"Container '{args.wg_container}' stopped. Exiting daemon.")
            sys.exit(0)
            
        stats = get_wg_stats(args.wg_container)
        current_time = time.time()
        
        if stats:
            handshake, rx, tx = stats
            
            traffic_changed = False
            if rx > prev_rx or tx > prev_tx:
                traffic_changed = True
                
            prev_rx = rx
            prev_tx = tx
            
            handshake_active = False
            if handshake > 0:
                has_connected_once = True
                if (current_time - handshake) < args.idle_timeout:
                    handshake_active = True
            
            if traffic_changed or handshake_active:
                last_active_time = current_time
        
        elapsed = current_time - start_time
        idle_time = current_time - last_active_time
        
        if elapsed > args.timeout:
            log_message(f"Lab '{lab_name}' reached maximum lifetime ({args.timeout}s). Triggering cleanup.")
            break
            
        if has_connected_once:
            if idle_time > args.idle_timeout:
                log_message(f"Lab '{lab_name}' inactive for {idle_time:.1f}s (exceeded {args.idle_timeout}s). Triggering cleanup.")
                break
        else:
            if elapsed > 1800:
                log_message(f"Lab '{lab_name}' did not receive any connection within 30 minutes of startup. Triggering cleanup.")
                break

    log_message(f"Stopping lab '{lab_name}' via docker compose down...")
    try:
        res = subprocess.run(
            ["docker", "compose", "down"],
            cwd=args.lab_dir, capture_output=True, text=True, timeout=60
        )
        if res.returncode == 0:
            log_message(f"Lab '{lab_name}' successfully stopped by daemon.")
        else:
            log_message(f"Error stopping lab '{lab_name}': {res.stderr.strip()}")
    except Exception as e:
        log_message(f"Exception raised while stopping lab '{lab_name}': {e}")
        
    log_message("Daemon exiting.")
    sys.exit(0)

if __name__ == "__main__":
    main()
