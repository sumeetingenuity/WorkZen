# 🛡️ SecureAssist

**SecureAssist** is a production-ready, multi-agent AI platform built on **Django 6**, inspired by **OpenClaw** and designed with **security as the top priority**. It allows users to chat with a powerful Orchestrator that can research, write code, build entire sub-applications, and manage long-term semantic memory—all within a secure, audited, and hot-reloadable environment.

> **🔒 Security-First Philosophy**: Every aspect of SecureAssist is built with security in mind—from out-of-band secret management to autonomous self-healing capabilities that prevent system vulnerabilities.

> **💡 Inspired by OpenClaw**: SecureAssist takes inspiration from OpenClaw's innovative approach to AI agent architecture, extending it with enhanced security, autonomous error recovery, and comprehensive document management capabilities.

---

## 🚀 Quick Start

1. **Install**: Run `./setup.sh` (Linux/macOS) or `setup.bat` (Windows)
2. **Configure**: Complete the onboarding wizard (`python onboard.py`)
3. **Launch**: Start the platform (`python run.py`)
4. **Chat**: Open your Telegram bot and start chatting!

For detailed instructions, see the [Setup Instructions](#-setup-instructions) section below.

---

## ✨ Features

*   **🧠 Infinite Semantic Memory**: Uses **LanceDB** to store and recall past conversations and tool results forever.
*   **🛠️ Dynamic App Generation**: Build new specialized apps on the fly using the **Developer Agent** and OpenCode CLI.
*   **🌐 Expanded LLM Ecosystem**: Seamlessly switch between **OpenAI, Anthropic, Google Gemini, Ollama, OpenRouter, and Together AI**.
*   **👁️ Advanced OCR & Vision**: Extract text from scanned PDFs and images using local **Ollama Vision** models (Llava) with **Tesseract** fallback.
*   **🎙️ Local Text-to-Speech**: High-quality local voice synthesis using **microsoft/VibeVoice-1.5B**.
*   **🛡️ Out-of-Band Secure Credentials**: Signal-based input mechanism ensures API keys are **never seen by the LLM**.
*   **🔄 Git Checkpoints & Rollback**: Automatic pre-generation checkpoints with one-click **rollback** and **autofix** capabilities.
*   **🏥 Self-Healing Supervisor**: Watchdog service in `run.py` that captures crash logs and **auto-restarts** the server on failure.
*   **🔌 MCP Server Support**: Standardized **Model Context Protocol** endpoints for interoperability with external AI tools (Cursor, Claude Desktop).
*   **🔗 Webhook Integration**: Trigger external notifications and workflows based on agent actions and tool results.
*   **📂 Intelligent Document Management**: Automatically detect file types (images, PDFs, CSVs, XLS, videos), store them securely, and organize by category. Files are stored first, processed only on request.
*   **📤 File Retrieval & Delivery**: Request any stored document and the agent will send it back to you via Telegram instantly.
*   **🔄 Autonomous Self-Healing**: The Orchestrator and Developer agents can detect, diagnose, and fix errors automatically without user intervention.
*   **🌙 Daily Briefing Sweeper**: AI-synthesized daily activity reports delivered as a briefing.
*   **✨ Agent Personalization**: Fully customizable name, persona, and voice profile for a unique AI identity.
*   **💻 Universal Productivity Suite**: Built-in tools for Email reading/sending, Calendar management, and Structured Data Entry.
*   **🎙️ Autonomous Voice Ingestion**: Speak to your agent via Telegram; it transcribes, extracts intent, and takes action automatically.
*   **🔗 Knowledge Graph**: Semantic linking between documents, contacts, and tasks for a unified data web.
*   **📋 Task & Finance Engine**: Proactive to-do management with reminders and a built-in financial ledger for budget tracking.
*   **⚡ SecureAssist Task Engine (SATE)**: Decompose complex objectives into parallelized, dependency-aware task graphs for maximum efficiency.
*   **📰 Intelligence Feeds**: Subscribe topics for the agent to monitor the web and alert you on significant updates.
*   **🛡️ Security-First Architecture**: Features mandatory ORM logging for tools, secret injection at runtime, and comprehensive audit logs.
*   **⚡ Zero-Downtime Hot-Reloading**: Inject new models and tools with **syntax protection** to prevent system instability.

---

## 🚀 Use Cases

### ⚖️ Legal Practice Management
Generate a specialized "Lawyer App" that can research NY state law, extract text from massive PDF evidence files, and store client data in a secure database—all via natural language.

### 📈 Financial Intelligence
Create a "Research App" that monitors market sentiments using Tavily Web Search, processes quarterly reports with Vision parsing, and maintains a long-term memory of investment theses.

### 📧 Automated Communications
Compose "Macro Tools" to chain web research with email drafting and scheduling, creating high-level autonomous workflows for business operations.

---

## 🛠️ Setup Instructions

### 1. One-Click Installation
We provide automated setup scripts for all major platforms.

**For Linux / macOS:**
```bash
chmod +x setup.sh
./setup.sh
```

**For Windows:**
```batch
setup.bat
```

### 2. Configuration (Onboarding Wizard)
After installation, the **Onboarding Wizard** will launch automatically. It will:
- Generate your unique **Secret Keys** for encryption.
- Configure your **LLM Providers** (OpenRouter, Together AI, Ollama, OpenAI, etc.).
- Set up **Advanced OCR** and **Local TTS** settings.
- Configure **Embedding models** for semantic memory (Ollama, OpenAI, etc.).
- Initialize **Git repository** (if not already initialized) for version control.
- Create your secure vault at `~/.secureassist/vault.json` (outside project directory for security).

*If you need to run it again later:*
```bash
python onboard.py
```

### 3. Run the Platform
**One-Click Launcher (Recommended)**
```bash
python run.py
```
*This starts the Backend, Bot, and Supervising Watchdog in one command.*

### ☁️ VPS / Production Deployment (Gunicorn)
For professional deployments on a VPS, use **Gunicorn** with Uvicorn workers. Our hot-reload system supports Gunicorn by signalling the master process to refresh workers when new apps are generated.

1. **Start Gunicorn with a PID file**:
```bash
gunicorn secureassist.asgi:application \
    -k uvicorn.workers.UvicornWorker \
    --pid /tmp/gunicorn_secureassist.pid \
    --bind 0.0.0.0:8000
```

2. **Configuration**: SecureAssist will automatically detect `/tmp/gunicorn_secureassist.pid` and send a `SIGHUP` signal to trigger a graceful reload across all workers whenever the Developer Agent builds a new capability.

The API will be available at: `http://127.0.0.1:8000/api/v1/`
The API Documentation (Swagger) is at: `http://127.0.0.1:8000/api/v1/docs`

### 💬 Using SecureAssist

#### Basic Chat Commands
Once both processes are running, simply open your Telegram Bot and start chatting:

**App Generation:**
- *"I'm a lawyer"* → Builds a legal assistant app with case management
- *"Create a finance tracking app"* → Generates a custom financial tool
- *"Build an app for managing contracts"* → Creates a contract management system

**Memory & Recall:**
- *"What do we know about case X?"* → Uses semantic memory to recall past conversations
- *"Remember that I prefer morning meetings"* → Stores preferences for future reference
- *"What did we discuss last week about project Alpha?"* → Retrieves historical context

**File Operations:**
- Upload any file (image, PDF, document) → Automatically stored
- *"Extract text from the last image"* → Runs OCR on demand
- *"Send me the contract I uploaded"* → Retrieves and sends file back
- *"Search for documents about legal cases"* → Finds files by content

**Tool Execution:**
- *"Research the latest AI regulations"* → Uses web research tools
- *"Schedule a meeting tomorrow at 2 PM"* → Creates calendar event
- *"Send an email to john@example.com"* → Composes and sends email (with approval)

Everything you do in the chat is securely logged and immediately functional.

---

## 📂 Workspace & Document Management

SecureAssist is not just a chatbot; it's an intelligent workspace manager with robust file handling capabilities.

### 📁 Universal File Support
SecureAssist accepts **any file type** via Telegram:
- **Images**: JPG, PNG, WebP, GIF
- **Documents**: PDF, DOC, DOCX, TXT, MD
- **Spreadsheets**: CSV, XLS, XLSX
- **Videos**: MP4, AVI, MOV, and animations
- **Other**: Any file type you need to store

### 🗄️ Smart Document Storage Workflow
When you upload a file, SecureAssist follows a **secure, two-phase process**:

1. **Phase 1: Immediate Storage** (Automatic)
   - File type is automatically detected
   - File is stored in `media/uploads/{type}/` with a unique ID
   - Metadata is recorded (name, type, size, upload date, user)
   - **No processing occurs**—files are stored safely first

2. **Phase 2: Processing** (On Request Only)
   - OCR extraction: *"Extract text from the last uploaded image"*
   - PDF parsing: *"Read the PDF I just uploaded"*
   - Vision analysis: *"Analyze this document layout"*
   - File retrieval: *"Send me the contract I uploaded yesterday"*

### 📤 Retrieving Stored Files
Ask the agent to retrieve any stored document:
- *"Send me the last file I uploaded"*
- *"Find and send me the invoice from last week"*
- *"Show me all PDFs I've stored"*

The agent will automatically send the file back to you via Telegram.

### 🔍 Document Search
Use natural language to find files:
- *"Search for documents about legal contracts"*
- *"Find all images uploaded this month"*
- *"Show me PDFs related to project Alpha"*

### 📅 Daily Briefing Sweeper
The system includes a proactive "Sweeper" service that:
-   Reviews all agent actions and tool results from the day.
-   Synthesizes a professional summary briefing.
-   Can be scheduled as a daily cron job (e.g., *"Generate my daily briefing every night at 11 PM"*).

---

## 💻 Computer & Productivity Suite

SecureAssist comes with a built-in "OS Integration" layer for essential professional tasks.

### 📧 Communications (Email)
- **Send**: Send professional emails via SMTP with user approval.
- **Read**: The `check_inbox` tool allows the agent to monitor and summarize your incoming communications.

### 📅 Timeline (Calendar)
- **Manage**: Create, update, and list appointments or meetings.
- **Reminders**: Schedule pro-active reminders that the bot will trigger via your primary chat interface.

### 📑 Universal Data Entry
The **Generic Entity Registry** allows you to save structured information without needing special apps.

### 🛡️ Secure Vault Administration
Manage your credentials safely using the CLI utility:
```bash
python scripts/vault_admin.py
```
This tool allows you to add/update secrets with masked input, keeping them separate from your working project.

---

## 🏗️ Advanced Reliability & Git
SecureAssist ensures your development process is robust and reversible.

### 🔄 Git Versioning
- **Automated Checkpoints**: The system commits changes before and after every generation.
- **Commands**: 
  - `/git_status`: Check current development state.
  - `/rollback`: Revert to the last stable checkpoint immediately.

### 🏥 Crash Recovery & Self-Healing
SecureAssist includes multiple layers of autonomous error recovery:

**Process-Level Recovery:**
- The **Process Supervisor** in `run.py` monitors system health
- Automatically restarts processes on crash
- Captures and displays the last 10 lines of crash logs for debugging
- Prevents system downtime during heavy development or app generation

**Agent-Level Self-Healing:**
- **Orchestrator Agent** can detect tool execution failures and automatically retry with recovery
- **Developer Agent** validates generated code and fixes syntax errors autonomously
- **App Recovery**: If app generation fails, the system automatically attempts to fix issues and retry
- **Tool Reload**: Failed tools trigger automatic app reload and tool re-registration

**Error Detection & Recovery Flow:**
1. Error occurs (tool failure, syntax error, migration issue)
2. Agent identifies the root cause
3. Automatic fix attempt (syntax correction, app reload, migration fix)
4. Retry the operation
5. If successful, continue; if not, report with detailed diagnostics

This ensures **autonomous app creation** where the system can build, validate, and fix issues without manual intervention.

---

## 🚀 Advanced OS & Intelligence

SecureAssist acts as a proactive operating system for your professional life.

### 🎙️ Voice-to-Action
Send a voice note to the Telegram bot. The system will:
1. Transcribe the audio using **Whisper**.
2. Extract intent (e.g., "Remind me to call John" or "Track $50 for lunch").
3. Execute the corresponding tool immediately.

### 🔗 Knowledge Graph
Everything in SecureAssist is connected. You can link a **Document** to a **Contact**, or a **Task** to a **Project**.
- *"Link this contract to the Acme Corp contact."*
- *"Show me all tasks related to Project Alpha."*

### 📋 Proactive Task Engine
The agent doesn't just wait for you.
- It tracks a global to-do list with priorities and due dates.
- It proactively suggests tasks during your **Daily Briefing**.

### ⚡ SecureAssist Task Engine (SATE)
For heavy-duty workflows, use the **Parallel Execution Engine**:
- **DAG Execution**: Breaks down "Research X then Build Y" into a graph of sub-tasks.
- **Parallelism**: Runs independent tasks (e.g., researching 3 competitors) simultaneously.
- **Efficiency**: Reduces wait time by maximizing agent concurrency.

### 📰 Intelligence Feeds (Watchdog)
Monitor the web for topics you care about.
- *"Monitor the web for 'Generative AI legal news' every day."*
- The agent will ping you on Telegram if it finds something significant.

---

## 🔌 Connectivity & Extensions

SecureAssist is designed to play well with other tools and services.

### 🔌 Model Context Protocol (MCP) Server
SecureAssist acts as a proactive MCP server, exposing its tools and context to external AI clients.
- **API Endpoint**: `http://localhost:8000/api/v1/mcp/`
- **Capabilities**: List tools, retrieve schemas, and execute tools directly from Cursor, Claude Desktop, or other AI-powered IDEs.

> [!TIP]
> **Example Usecase**: Imagine you have a custom "Legal Research" app in SecureAssist. By connecting SecureAssist to **Cursor** via MCP, you can highlight code in Cursor and ask: *"Does this function align with the compliance guidelines in our SecureAssist legal database?"* Cursor will use the SecureAssist tool via MCP to fetch the answer.

### 🔗 Webhooks & Automation
You can register external HTTP endpoints to receive real-time updates from your agent.
- **Events**: `tool_execution_success`, `tool_execution_failed`, and more.
- **Security**: HMAC-SHA256 signatures are included in the `X-SecureAssist-Signature` header for verification.
- **Configuration**: Manage webhooks via the chat: *"Register a webhook to https://my-service.com/hooks"*

---

## 🔒 Security & Agent Safety

**Security is the foundation of SecureAssist.** Inspired by OpenClaw's security-first approach, every component is designed to prevent "Agent Rebellion" or accidental leakage of sensitive credentials. Security is not an afterthought—it's built into the core architecture.

### 🛡️ Hardened Secret Vault
Unlike typical projects that store keys in a local `.env` file, SecureAssist uses an **Out-of-Workspace Vault**:
- **Location**: `~/.secureassist/vault.json` (outside your project directory).
- **Isolation**: When an LLM agent or generated code scans your workspace, it will find **no sensitive keys**.
- **Access**: Tools access secrets only via **Runtime Injection** (they are injected just for the function call and never stored in the agent's memory).

### 🚫 Automatic Redaction
The Orchestrator includes a final safety net. Every response is scanned for known secrets before being sent to the user. Any leaked keys are automatically replaced with `[REDACTED]`.

### 🔐 Runtime Secret Injection
Secrets are **never** stored in agent memory or code:
- Secrets are injected only at tool execution time
- Each tool call receives secrets as isolated parameters
- Secrets are cleared from memory immediately after use
- No secrets appear in logs, responses, or generated code

### 📋 Comprehensive Audit Logging
Every action is logged for security and compliance:
- Tool executions with input/output summaries
- User actions and agent decisions
- Policy violations and access denials
- All stored in `AuditLog` model for review

### ⚠️ Security Best Practices
- **Do not** manually move secrets into the `.env` file within the project
- **Always** use the `onboard.py` wizard to update your credentials
- **Review** audit logs regularly to monitor agent behavior
- **Use** approval requirements for sensitive operations (email, file deletion, etc.)
- **Keep** your vault file (`~/.secureassist/vault.json`) with restricted permissions (600)

---

## 📂 Project Structure

- `/core`: Core framework logic, decorators, registry, and memory services.
- `/agents`: The "brains" of the platform (Orchestrator, Developer, ContextManager).
- `/apps`: Dynamically generated sub-applications.
- `/integrations`: API, Telegram, and other entry points.
- `/data`: Persistent storage for LanceDB and SQLite.

---

---

## 🔮 Roadmap & Future Features

SecureAssist is evolving rapidly. Here is what's coming next:

- **👥 Multi-User Collaboration**: Role-Based Access Control (RBAC) for teams sharing an agent.
- **📱 Mobile Companion App**: Native Flutter/React Native app for on-the-go access.
- **🗣️ Live Voice Mode**: Real-time, 2-way audio conversations (WebRTC).
- **🐳 Docker Compose Support**: Simplified self-hosting container stack.
- **🎯 Agent Fine-Tuning Studio**: UI to train custom LoRAs for specific agent personas.
- **🔌 Enterprise Integrations**: Native connectors for Slack, Jira, Linear, and Salesforce.

---

## 🆘 Troubleshooting

### Common Issues

**Bot not responding:**
- Check that both the Django server and Telegram bot are running (`python run.py`)
- Verify your Telegram bot token is correct in the vault
- Check logs in `logs/secureassist.log`

**File upload fails:**
- Ensure `media/uploads/` directory exists and is writable
- Check database migrations are applied: `python manage.py migrate`
- Verify file size limits in Django settings

**App generation errors:**
- The system will automatically attempt to fix issues
- Check `/git_status` in Telegram to see current state
- Use `/rollback` to revert to last stable checkpoint
- Review logs for detailed error messages

**Secret/API key issues:**
- Run `python onboard.py` to reconfigure
- Use `python scripts/vault_admin.py` to manage secrets
- Ensure secrets are stored in `~/.secureassist/vault.json`, not in project `.env`

**OCR/Vision not working:**
- For local OCR: Ensure Ollama is running with `nomic-embed-text:latest` model
- For vision: Configure vision model in onboarding (OpenAI GPT-4o, Anthropic Claude, or Ollama Llava)
- Check API keys are correctly configured in vault

**Database errors:**
- Run migrations: `python manage.py migrate`
- If issues persist, check `db.sqlite3` permissions
- For production, consider PostgreSQL instead of SQLite

### Getting Help

- Check the logs: `logs/secureassist.log`
- Review audit logs in Django admin for tool execution history
- Use `/git_status` to see current development state
- The system's self-healing capabilities will attempt to fix many issues automatically

---

## 📜 License
This project is licensed under the MIT License.

---

## 🙏 Acknowledgments

SecureAssist is inspired by **OpenClaw** and builds upon its innovative approach to AI agent architecture. We extend our gratitude to the OpenClaw community for their pioneering work in secure, autonomous AI systems.
