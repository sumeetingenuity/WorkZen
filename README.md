# 🛡️ WorkZen

**WorkZen** is a production-ready, multi-agent AI platform built on **Django 6**. It allows users to chat with a powerful Orchestrator that can research, write code, build entire sub-applications, and manage long-term semantic memory—all within a secure, audited, and hot-reloadable environment.

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
*   **📂 Intelligent Document Management**: Automatically categorize and organize uploaded files into a structured directory tree.
*   **🌙 Daily Briefing Sweeper**: AI-synthesized daily activity reports delivered as a briefing.
*   **✨ Agent Personalization**: Fully customizable name, persona, and voice profile for a unique AI identity.
*   **💻 Universal Productivity Suite**: Built-in tools for Email reading/sending, Calendar management, and Structured Data Entry.
*   **🎙️ Autonomous Voice Ingestion**: Speak to your agent via Telegram; it transcribes, extracts intent, and takes action automatically.
*   **🔗 Knowledge Graph**: Semantic linking between documents, contacts, and tasks for a unified data web.
*   **📋 Task & Finance Engine**: Proactive to-do management with reminders and a built-in financial ledger for budget tracking.
*   **⚡ WorkZen Task Engine (SATE)**: Decompose complex objectives into parallelized, dependency-aware task graphs for maximum efficiency.
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
- Create your initial `.env` file and secure vault.

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
gunicorn WorkZen.asgi:application \
    -k uvicorn.workers.UvicornWorker \
    --pid /tmp/gunicorn_WorkZen.pid \
    --bind 0.0.0.0:8000
```

2. **Configuration**: WorkZen will automatically detect `/tmp/gunicorn_WorkZen.pid` and send a `SIGHUP` signal to trigger a graceful reload across all workers whenever the Developer Agent builds a new capability.

The API will be available at: `http://127.0.0.1:8000/api/v1/`
The API Documentation (Swagger) is at: `http://127.0.0.1:8000/api/v1/docs`

### 💬 Chatting with WorkZen
Once both processes are running, simply open your Telegram Bot and start chatting. 
- Say "I'm a lawyer" to build a legal assistant app.
- Ask "What do we know about case X?" to use semantic memory.
- Upload an image and ask for an analysis using the integrated Vision model.

Everything you do in the chat is securely logged and immediately functional.

---

## 📂 Workspace & Document Management

WorkZen is not just a chatbot; it's an intelligent workspace manager.

### 🗄️ Automated Document Organization
When you upload a document, your agent will:
1.  **classify** it (Legal, Medical, Finance, etc.)
2.  **Organize** it into `data/documents/{category}/{project}/`
3.  **Index** it for future semantic recall.

### 📅 Daily Briefing Sweeper
The system includes a proactive "Sweeper" service that:
-   Reviews all agent actions and tool results from the day.
-   Synthesizes a professional summary briefing.
-   Can be scheduled as a daily cron job (e.g., *"Generate my daily briefing every night at 11 PM"*).

---

## 💻 Computer & Productivity Suite

WorkZen comes with a built-in "OS Integration" layer for essential professional tasks.

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
WorkZen ensures your development process is robust and reversible.

### 🔄 Git Versioning
- **Automated Checkpoints**: The system commits changes before and after every generation.
- **Commands**: 
  - `/git_status`: Check current development state.
  - `/rollback`: Revert to the last stable checkpoint immediately.

### 🏥 Crash Recovery
The **Process Supervisor** in `run.py` monitors system health:
- Automatically restarts processes on crash.
- Captures and displays the last 10 lines of crash logs for debugging.
- Prevents system downtime during heavy development or app generation.

---

## 🚀 Advanced OS & Intelligence

WorkZen acts as a proactive operating system for your professional life.

### 🎙️ Voice-to-Action
Send a voice note to the Telegram bot. The system will:
1. Transcribe the audio using **Whisper**.
2. Extract intent (e.g., "Remind me to call John" or "Track $50 for lunch").
3. Execute the corresponding tool immediately.

### 🔗 Knowledge Graph
Everything in WorkZen is connected. You can link a **Document** to a **Contact**, or a **Task** to a **Project**.
- *"Link this contract to the Acme Corp contact."*
- *"Show me all tasks related to Project Alpha."*

### 📋 Proactive Task Engine
The agent doesn't just wait for you.
- It tracks a global to-do list with priorities and due dates.
- It proactively suggests tasks during your **Daily Briefing**.

### ⚡ WorkZen Task Engine (SATE)
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

WorkZen is designed to play well with other tools and services.

### 🔌 Model Context Protocol (MCP) Server
WorkZen acts as a proactive MCP server, exposing its tools and context to external AI clients.
- **API Endpoint**: `http://localhost:8000/api/v1/mcp/`
- **Capabilities**: List tools, retrieve schemas, and execute tools directly from Cursor, Claude Desktop, or other AI-powered IDEs.

> [!TIP]
> **Example Usecase**: Imagine you have a custom "Legal Research" app in WorkZen. By connecting WorkZen to **Cursor** via MCP, you can highlight code in Cursor and ask: *"Does this function align with the compliance guidelines in our WorkZen legal database?"* Cursor will use the WorkZen tool via MCP to fetch the answer.

### 🔗 Webhooks & Automation
You can register external HTTP endpoints to receive real-time updates from your agent.
- **Events**: `tool_execution_success`, `tool_execution_failed`, and more.
- **Security**: HMAC-SHA256 signatures are included in the `X-WorkZen-Signature` header for verification.
- **Configuration**: Manage webhooks via the chat: *"Register a webhook to https://my-service.com/hooks"*

---

## 🔒 Security & Agent Safety

WorkZen is designed to prevent "Agent Rebellion" or accidental leakage of sensitive credentials.

### 🛡️ Hardened Secret Vault
Unlike typical projects that store keys in a local `.env` file, WorkZen uses an **Out-of-Workspace Vault**:
- **Location**: `~/.WorkZen/vault.json` (outside your project directory).
- **Isolation**: When an LLM agent or generated code scans your workspace, it will find **no sensitive keys**.
- **Access**: Tools access secrets only via **Runtime Injection** (they are injected just for the function call and never stored in the agent's memory).

### 🚫 Automatic Redaction
The Orchestrator includes a final safety net. Every response is scanned for known secrets before being sent to the user. Any leaked keys are automatically replaced with `[REDACTED]`.

### ⚠️ Best Practices
- **Do not** manually move secrets into the `.env` file within the project.
- **Always** use the `onboard.py` wizard to update your credentials.

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

WorkZen is evolving rapidly. Here is what's coming next:

- **👥 Multi-User Collaboration**: Role-Based Access Control (RBAC) for teams sharing an agent.
- **📱 Mobile Companion App**: Native Flutter/React Native app for on-the-go access.
- **🗣️ Live Voice Mode**: Real-time, 2-way audio conversations (WebRTC).
- **🐳 Docker Compose Support**: Simplified self-hosting container stack.
- **🎯 Agent Fine-Tuning Studio**: UI to train custom LoRAs for specific agent personas.
- **🔌 Enterprise Integrations**: Native connectors for Slack, Jira, Linear, and Salesforce.

---

## 📜 License
This project is licensed under the MIT License.
