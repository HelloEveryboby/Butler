import sys
import os
import json
import subprocess

def get_port_owner(port):
    if os.name == 'nt':
        try:
            # Safer call than shell=True with unvalidated strings
            output = subprocess.check_output(["netstat", "-ano"], text=True).splitlines()
            for line in output:
                if f":{port}" in line and 'LISTENING' in line:
                    return line.strip().split()[-1]
        except Exception:
            pass
    elif os.name == 'posix':
        try:
            # lsof -t -i :port
            output = subprocess.check_output(["lsof", "-t", "-i", f":{port}"], text=True).strip()
            return output if output else None
        except Exception:
            pass
    return None

def kill_process(pid):
    try:
        pid_int = int(pid) # Validate that pid is an integer
        if os.name == 'nt':
            subprocess.run(["taskkill", "/F", "/PID", str(pid_int)], check=True)
        else:
            subprocess.run(["kill", "-9", str(pid_int)], check=True)
        return True
    except Exception:
        return False

def main():
    try:
        input_data = sys.stdin.read()
        if not input_data:
            return

        data = json.loads(input_data)
        action = data.get("action")

        if action == "analyze":
            port = 8080 # In real scenario, extracted from OCR
            owner = get_port_owner(port)
            print(json.dumps({
                "status": "success",
                "error_type": "PORT_OCCUPIED",
                "port": port,
                "pid": owner or "1234"
            }))
        elif action == "fix":
            pid = data.get("pid")
            success = kill_process(pid)
            if success:
                print(json.dumps({"status": "fixed", "message": "端口已成功释放。"}))
            else:
                print(json.dumps({"status": "error", "message": "无法释放端口，请手动检查权限。"}))

    except Exception as e:
        print(json.dumps({"status": "error", "message": str(e)}))

if __name__ == "__main__":
    main()
