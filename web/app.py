import os
import sys
import subprocess
from flask import Flask, jsonify, render_template, Response, send_file, request, make_response

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import adlabs

app = Flask(__name__)

def get_lab_status_data(lab):
    containers_status = []
    all_running = True
    any_running = False
    
    for container in lab["containers"]:
        status, color = adlabs.check_container_status(container)
        containers_status.append({
            "name": container,
            "status": status,
            "color": color
        })
        if status == "RUNNING":
            any_running = True
        else:
            all_running = False
            
    status_label = "RUNNING" if all_running else ("STOPPED" if not any_running else "PARTIAL")
    
    actual_port = lab['vpn_port']
    wg_container = lab["wg_container"]
    if wg_container:
        res_port = subprocess.run(["docker", "port", wg_container, "51820/udp"], capture_output=True, text=True)
        if res_port.returncode == 0 and res_port.stdout.strip():
            actual_port = res_port.stdout.strip().split(":")[-1] + "/UDP"

    return {
        "index": lab["index"],
        "dir": lab["dir"],
        "status": status_label,
        "containers": containers_status,
        "vpn_profile": lab["vpn_profile"],
        "vpn_port": actual_port,
        "dns_domains": lab["dns_domains"],
        "targets_count": len(lab["targets"]),
        "targets": lab["targets"]
    }

@app.route('/')
def index_route():
    return render_template('index.html')

@app.route('/api/labs', methods=['GET'])
def get_labs():
    data = []
    for lab in adlabs.labs_def:
        data.append(get_lab_status_data(lab))
    return jsonify(data)

@app.route('/api/labs/<int:index>/status', methods=['GET'])
def get_lab_status(index):
    lab = next((l for l in adlabs.labs_def if l["index"] == index), None)
    if not lab:
        return jsonify({"error": "Lab not found"}), 404
    return jsonify(get_lab_status_data(lab))

def stream_command(cmd):
    def generate():
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            cwd=base_dir
        )
        for line in iter(process.stdout.readline, ''):
            yield f"data: {line}\n\n"
        process.stdout.close()
        process.wait()
        yield "data: [DONE]\n\n"
    return Response(generate(), mimetype='text/event-stream')

@app.route('/api/labs/<int:index>/deploy', methods=['GET'])
def deploy_lab_route(index):
    cmd = [sys.executable, "-u", "adlabs.py", "--lab", str(index)]
    return stream_command(cmd)

@app.route('/api/labs/<int:index>/stop', methods=['GET'])
def stop_lab_route(index):
    cmd = [sys.executable, "-u", "adlabs.py", "--stop", str(index)]
    return stream_command(cmd)

@app.route('/api/labs/<int:index>/clean', methods=['GET'])
def clean_lab_route(index):
    cmd = [sys.executable, "-u", "adlabs.py", "--clean", str(index)]
    return stream_command(cmd)

@app.route('/api/labs/<int:index>/test', methods=['GET'])
def test_lab_route(index):
    cmd = [sys.executable, "-u", "adlabs.py", "--test", str(index)]
    return stream_command(cmd)

@app.route('/api/labs/<int:index>/gen-vpn', methods=['POST'])
def gen_vpn_route(index):
    lab = next((l for l in adlabs.labs_def if l["index"] == index), None)
    if not lab:
        return jsonify({"error": "Lab not found"}), 404
        
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    success = adlabs.generate_vpn_profile(lab, base_dir)
    if success:
        return jsonify({"success": True, "message": "VPN profile generated successfully."})
    else:
        return jsonify({"success": False, "message": "Failed to generate VPN profile. Make sure the lab has been started at least once."}), 400

@app.route('/api/labs/<int:index>/vpn-config', methods=['GET', 'HEAD'])
def get_vpn_config(index):
    lab = next((l for l in adlabs.labs_def if l["index"] == index), None)
    if not lab:
        return jsonify({"error": "Lab not found"}), 404

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    dest_path = os.path.join(base_dir, lab["dir"], lab["vpn_profile"])
    if not os.path.exists(dest_path):
        return jsonify({"error": "VPN config not found. Start/Deploy the lab or generate VPN first."}), 404

    if request.method == 'HEAD':
        return '', 200

    return send_file(
        dest_path,
        as_attachment=True,
        download_name=lab["vpn_profile"],
        mimetype='text/plain'
    )

@app.route('/api/global/stop-all', methods=['GET'])
def stop_all_route():
    cmd = [sys.executable, "-u", "adlabs.py", "--stop-all"]
    return stream_command(cmd)

@app.route('/api/global/clean-all', methods=['GET'])
def clean_all_route():
    cmd = [sys.executable, "-u", "adlabs.py", "--clean-all"]
    return stream_command(cmd)

@app.route('/api/global/generate-wordlists', methods=['GET'])
def generate_wordlists_route():
    cmd = [sys.executable, "-u", "adlabs.py", "--generate-wordlists"]
    return stream_command(cmd)

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=8000, debug=True)
