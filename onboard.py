"""
SecureAssist Advanced Onboarding Wizard - Multi-Provider Model Configuration.
Supports OpenAI, Anthropic, Google Gemini, and Local (Ollama/VLLM).
"""
import os
import sys
import secrets

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def print_header():
    print("=" * 60)
    print("      🛡️  SECUREASSIST ADVANCED CONFIGURATION WIZARD  🛡️      ")
    print("=" * 60)
    print("\nConfigure your AI Brain - Mix and match providers easily.")

def get_choice(prompt, options):
    print(f"\n{prompt}")
    for i, opt in enumerate(options, 1):
        print(f"  {i}. {opt}")
    
    while True:
        try:
            choice = int(input(f"Selection (1-{len(options)}): "))
            if 1 <= choice <= len(options):
                return options[choice-1]
        except ValueError:
            pass
        print(f"Invalid input. Please choose 1-{len(options)}.")

def get_input(prompt, default=None):
    if default:
        val = input(f"{prompt} [{default}]: ").strip()
        return val if val else default
    return input(f"{prompt}: ").strip()

def main():
    clear_screen()
    print_header()
    
    env_data = {}
    llm_config = {}
    
    print("\n--- 🔑 1. Security Infrastructure ---")
    env_data['SECRET_KEY'] = secrets.token_urlsafe(50)
    from cryptography.fernet import Fernet
    env_data['SECRET_ENCRYPTION_KEY'] = Fernet.generate_key().decode()
    print("✅ Identity & Encryption keys generated.")

    print("\n--- 🤖 2. Orchestration & Code (Primary LLM) ---")
    provider = get_choice("Select your Primary LLM Provider:", [
        "Anthropic", 
        "OpenAI", 
        "Google Gemini", 
        "OpenRouter", 
        "Together AI", 
        "Local (Ollama/vLLM)"
    ])
    
    if provider == "Anthropic":
        llm_config['LLM_ORCHESTRATE'] = "anthropic/claude-3-5-sonnet-20240620"
        env_data['ANTHROPIC_API_KEY'] = get_input("Enter Anthropic API Key")
    elif provider == "OpenAI":
        llm_config['LLM_ORCHESTRATE'] = "openai/gpt-4o"
        env_data['OPENAI_API_KEY'] = get_input("Enter OpenAI API Key")
    elif provider == "Google Gemini":
        llm_config['LLM_ORCHESTRATE'] = "gemini/gemini-1.5-pro"
        env_data['GEMINI_API_KEY'] = get_input("Enter Google API Key")
    elif provider == "OpenRouter":
        llm_config['LLM_ORCHESTRATE'] = get_input("Enter OpenRouter model (e.g., openrouter/anthropic/claude-3-5-sonnet)", "openrouter/anthropic/claude-3.5-sonnet")
        env_data['OPENROUTER_API_KEY'] = get_input("Enter OpenRouter API Key")
    elif provider == "Together AI":
        llm_config['LLM_ORCHESTRATE'] = get_input("Enter Together AI model (e.g., together_ai/mistralai/Mixtral-8x7B-Instruct-v0.1)", "together_ai/mistralai/Mixtral-8x7B-Instruct-v0.1")
        env_data['TOGETHER_API_KEY'] = get_input("Enter Together AI API Key")
    else:
        llm_config['LLM_ORCHESTRATE'] = get_input("Enter local model path (e.g., ollama/llama3)", "ollama/llama3")
        env_data['LITELLM_LOCAL_BASE_URL'] = get_input("Local base URL (optional)", "http://localhost:11434")

    print("\n--- 🔍 2b. Web Research (Tavily) ---")
    tavily_enabled = get_input("Enable Web Research? (y/n)", "y").lower() == "y"
    if tavily_enabled:
        env_data['TAVILY_API_KEY'] = get_input("Enter Tavily API Key")
        print("✅ Tavily API Key added.")

    print("\n--- 💻 3. AI Coding Agent (OpenCode) ---")
    print("OpenCode is an autonomous coding CLI. (Official install: curl -fsSL https://opencode.ai/install | bash)")
    opencode_enabled = get_input("Enable OpenCode CLI for autonomous coding? (y/n)", "y").lower() == "y"
    if opencode_enabled:
        env_data['OPENCODE_API_KEY'] = get_input("Enter OpenCode API Key (or leave blank to use your own provider keys)")
        env_data['OPENCODE_MODEL'] = get_input("Default OpenCode Model (e.g., anthropic/claude-3-5-sonnet)", "anthropic/claude-3-5-sonnet")
        print("✅ OpenCode configuration added. SecureAssist will inject these into the CLI at runtime.")

    print("\n--- 👁️ 4. Vision & OCR Support ---")
    vision_provider = get_choice("Select Vision Provider:", [
        "Same as Primary", 
        "OpenAI (GPT-4o)", 
        "Anthropic (Claude 3.5 Sonnet)", 
        "Local OCR (Ollama/Llava)",
        "Tesseract (CPU-only Fallback)"
    ])
    if vision_provider == "Same as Primary":
        llm_config['LLM_VISION'] = llm_config['LLM_ORCHESTRATE']
    elif vision_provider == "OpenAI (GPT-4o)":
        llm_config['LLM_VISION'] = "openai/gpt-4o"
        if 'OPENAI_API_KEY' not in env_data:
            env_data['OPENAI_API_KEY'] = get_input("Enter OpenAI API Key")
    elif vision_provider == "Anthropic (Claude 3.5 Sonnet)":
        llm_config['LLM_VISION'] = "anthropic/claude-3-5-sonnet-20240620"
        if 'ANTHROPIC_API_KEY' not in env_data:
            env_data['ANTHROPIC_API_KEY'] = get_input("Enter Anthropic API Key")
    elif vision_provider == "Local OCR (Ollama/Llava)":
        llm_config['LLM_VISION'] = get_input("Enter local vision model (e.g., ollama/llava)", "ollama/llava")
        llm_config['OCR_ENGINE'] = "ollama"
    else:
        llm_config['LLM_VISION'] = "tesseract"
        llm_config['OCR_ENGINE'] = "tesseract"

    print("\n--- 🎤 5. Voice & Speech (TTS/STT) ---")
    voice_enabled = get_input("Enable Voice features? (y/n)", "n").lower() == "y"
    if voice_enabled:
        tts_provider = get_choice("Select TTS Provider:", ["OpenAI", "Local (VibeVoice-1.5B)"])
        if tts_provider == "OpenAI":
            llm_config['LLM_TTS'] = "openai/tts-1"
            llm_config['LLM_TTS_VOICE'] = get_choice("Select Voice Profile:", ["alloy", "echo", "fable", "onyx", "nova", "shimmer"])
            if 'OPENAI_API_KEY' not in env_data:
                env_data['OPENAI_API_KEY'] = get_input("Enter OpenAI API Key for Voice")
        else:
            llm_config['LLM_TTS'] = "local/vibevoice"
            print("✅ Using local VibeVoice-1.5B for TTS.")
            
        llm_config['LLM_STT'] = "openai/whisper-1"
        if 'OPENAI_API_KEY' not in env_data and llm_config.get('LLM_STT') == "openai/whisper-1":
             # We might need it for STT too if not local
             pass 

    print("\n--- ✨ 6. Agent Identity & Personality ---")
    llm_config['AGENT_NAME'] = get_input("Give your AI Agent a name", "SecureAssist")
    llm_config['AGENT_PERSONA'] = get_input("Describe the Agent personality (e.g., 'Professional & Stoic', 'Sassy & Helpful', 'Warm & Empathetic')", "Professional & Direct")
    
    print("\n--- 💾 7. Finalizing Configuration ---")
    vault_path = os.path.expanduser("~/.secureassist/vault.json")
    os.makedirs(os.path.dirname(vault_path), exist_ok=True)
    
    # Save secrets to vault
    import json
    with open(vault_path, "w") as f:
        json.dump(env_data, f, indent=2)
    
    # Set strict permissions (readable only by current user)
    if os.name != 'nt':
        os.chmod(vault_path, 0o600)
    
    print(f"✅ Sensitive keys saved to secure vault: '{vault_path}'")

    # Save non-sensitive metadata to workspace .env
    env_path = ".env"
    with open(env_path, "w") as f:
        f.write("# SecureAssist Workspace Configuration\n")
        f.write("# (Sensitive keys are stored in ~/.secureassist/vault.json)\n")
        f.write("DEBUG=True\n")
        f.write("ALLOWED_HOSTS=localhost,127.0.0.1\n\n")
        for k, v in llm_config.items():
            f.write(f"{k}={v}\n")
            
    print(f"\n✅ SUCCESS! Workspace metadata saved to '{env_path}'.")
    print("\n🚀 **ONE-CLICK START**:")
    print("Simply run:   python run.py")
    print("\nThis will launch both your AI Server and Telegram Bot together!")
    print("-" * 60)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nExiting...")
        sys.exit(0)
