"""
SecureAssist Unified Launcher - Starts both Server and Bot in one command.
"""
import subprocess
import sys
import time
import signal
import os

def main():
    print("=" * 60)
    print("      🛡️  SECUREASSIST UNIFIED LAUNCHER  🛡️      ")
    print("=" * 60)
    
    if not os.path.exists(".env") and not os.path.exists(os.path.expanduser("~/.secureassist/vault.json")):
        print("❌ Error: System not configured. Please run 'python onboard.py' first.")
        sys.exit(1)

    processes = []
    
    try:
        # 1. Start Django Server
        print("📡 Starting Backend Server (gunicorn/uvicorn)...")
        server_cmd = [sys.executable, "manage.py", "runserver"]
        # In a real VPS context, this would be the gunicorn command, 
        # but for the launcher, runserver is the easiest entry point.
        p_server = subprocess.Popen(server_cmd)
        processes.append(p_server)
        
        # Wait for server to initialize
        time.sleep(2)
        
        # 2. Start Telegram Bot
        print("🤖 Starting Telegram Bot interface...")
        bot_cmd = [sys.executable, "manage.py", "run_bot"]
        p_bot = subprocess.Popen(bot_cmd)
        processes.append(p_bot)
        
        print("\n✅ SYSTEM LIVE! You can now start chatting on Telegram.")
        print("Press Ctrl+C to stop all services.")
        
        # Keep the launcher alive
        while True:
            time.sleep(1)
            # Check if any process died
            if p_server.poll() is not None:
                print("❌ Server process stopped unexpectedly.")
                break
            if p_bot.poll() is not None:
                print("❌ Bot process stopped unexpectedly.")
                break
                
    except KeyboardInterrupt:
        print("\n🛑 Stopping SecureAssist...")
    finally:
        for p in processes:
            p.terminate()
            try:
                p.wait(timeout=5)
            except subprocess.TimeoutExpired:
                p.kill()
        print("✅ Shutdown complete.")

if __name__ == "__main__":
    main()
