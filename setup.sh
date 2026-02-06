#!/bin/bash
# SecureAssist Setup Script for Linux/macOS

echo "🚀 Starting SecureAssist Setup..."

# 1. Check Python version
python3 --version || { echo "❌ Python 3 not found"; exit 1; }

# 2. Create Virtual Environment
echo "📦 Creating virtual environment..."
python3 -m venv venv
source venv/bin/activate

# 3. Upgrade pip
echo "⬆️ Upgrading pip..."
pip install --upgrade pip

# 4. Install Dependencies
echo "🛠️ Installing dependencies (this may take a few minutes)..."
pip install -r requirements.txt

# 4b. Install OpenCode CLI (Official Script)
echo "💻 Installing OpenCode CLI..."
curl -fsSL https://opencode.ai/install | bash

# 5. Initialize Browser for Playwright
echo "🌐 Initializing browser engines..."
playwright install chromium

# 6. Initialize Database
echo "🗄️ Initializing database..."
python manage.py migrate
python manage.py collectstatic --noinput

# 7. Run Onboarding
echo "👤 Starting Onboarding Wizard..."
python onboard.py

# 8. Start Platform
echo ""
read -p "🚀 Would you like to start SecureAssist now? (y/n): " start_now
if [[ $start_now == "y" || $start_now == "Y" ]]; then
    python run.py
else
    echo "✅ Setup complete! Run 'python run.py' whenever you are ready to chat."
fi
