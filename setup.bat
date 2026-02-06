@echo off
REM SecureAssist Setup Script for Windows

echo 🚀 Starting SecureAssist Setup...

REM 1. Check Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Python not found. Please install Python 3.10+
    pause
    exit /b
)

REM 2. Create Venv
echo 📦 Creating virtual environment...
python -m venv venv
call venv\Scripts\activate

REM 3. Upgrade pip
echo ⬆️ Upgrading pip...
python -m pip install --upgrade pip

REM 4. Install Dependencies
echo 🛠️ Installing dependencies...
pip install -r requirements.txt

REM 4b. OpenCode CLI (Note: Please install via Chocolatey, Scoop, or Docker)
echo 💻 Note: To use autonomous coding, please install OpenCode CLI separately.
echo Visit https://docs.opencode.ai for Windows installation methods.

REM 5. Initialize Browser
echo 🌐 Initializing browser engines...
playwright install chromium

REM 6. Initialize Database
echo 🗄️ Initializing database...
python manage.py migrate
python manage.py collectstatic --noinput

REM 7. Run Onboarding
echo 👤 Starting Onboarding Wizard...
python onboard.py

REM 8. Start Platform
set /p start_now=🚀 Would you like to start SecureAssist now? (y/n): 
if /I "%start_now%"=="y" (
    python run.py
) else (
    echo ✅ Setup complete! Start the platform with 'python run.py' whenever you are ready.
    pause
)
