"""
SecureAssist Unified Launcher - Starts both Server and Bot in one command.
"""
import subprocess
import sys
import time
import signal
import os

def start_process(cmd, name):
    print(f"📡 Starting {name}...")
    return subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

def main():
    print("=" * 60)
    print("      🛡️  SECUREASSIST UNIFIED LAUNCHER  🛡️      ")
    print("=" * 60)
    
    if not os.path.exists(".env") and not os.path.exists(os.path.expanduser("~/.secureassist/vault.json")):
        print("❌ Error: System not configured. Please run 'python onboard.py' first.")
        sys.exit(1)

    # 1. Start Django Server
    server_cmd = [sys.executable, "manage.py", "runserver"]
    p_server = start_process(server_cmd, "Backend Server")
    
    # 2. Start Telegram Bot
    time.sleep(2)
    bot_cmd = [sys.executable, "manage.py", "run_bot"]
    p_bot = start_process(bot_cmd, "Telegram Bot")
    
    processes = {"Backend": (p_server, server_cmd), "Bot": (p_bot, bot_cmd)}
    
    print("\n✅ SYSTEM LIVE! Press Ctrl+C to stop.")

    try:
        while True:
            time.sleep(2)
            for name, (proc, cmd) in list(processes.items()):
                if proc.poll() is not None:
                    print(f"⚠️  {name} process crashed! Captured last output:")
                    # Try to get some crash info
                    if proc.stdout:
                        lines = proc.stdout.readlines()[-10:]
                        for line in lines:
                            print(f"  [CRASH LOG] {line.strip()}")
                    
                    print(f"♻️  Restarting {name}...")
                    processes[name] = (start_process(cmd, name), cmd)
                    
    except KeyboardInterrupt:
        print("\n🛑 Stopping SecureAssist...")
    finally:
        for name, (proc, _) in processes.items():
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
        print("✅ Shutdown complete.")

if __name__ == "__main__":
    main()
