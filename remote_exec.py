import paramiko
import sys

# Reconfigure stdout/stderr to use utf-8 to avoid console encoding errors on Windows
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except AttributeError:
        # Fallback for Python versions where reconfigure is not available
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

def run_remote_command(cmd):
    host = "seg-dev.sreenidhi.edu.in"
    port = 5791
    username = "seg"
    password = "SecureAccess@SEG"

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        ssh.connect(host, port=port, username=username, password=password, timeout=15)
        stdin, stdout, stderr = ssh.exec_command(cmd)
        
        # Read stream output
        out = stdout.read().decode('utf-8', errors='replace')
        err = stderr.read().decode('utf-8', errors='replace')
        
        ssh.close()
        return out, err
    except Exception as e:
        return "", f"Connection failed: {e}"

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python remote_exec.py <command>")
        sys.exit(1)
        
    cmd = " ".join(sys.argv[1:])
    print(f"Executing remote command: {cmd}")
    out, err = run_remote_command(cmd)
    
    if out:
        print("\n=== STDOUT ===")
        print(out)
    if err:
        print("\n=== STDERR ===")
        print(err)
