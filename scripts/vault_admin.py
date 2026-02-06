#!/usr/bin/env python3
"""
SecureAssist Vault Administration Utility.
Allows manual management of secrets in the secure vault.
"""
import os
import sys
import json
import getpass
from cryptography.fernet import Fernet

def get_vault_path():
    return os.path.expanduser("~/.secureassist/vault.json")

def load_vault():
    path = get_vault_path()
    if os.path.exists(path):
        with open(path, 'r') as f:
            return json.load(f)
    return {}

def save_vault(vault):
    path = get_vault_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w') as f:
        json.dump(vault, f, indent=2)
    if os.name != 'nt':
        os.chmod(path, 0o600)

def main():
    print("=" * 60)
    print("      🛡️  SECUREASSIST VAULT ADMIN  🛡️      ")
    print("=" * 60)
    
    vault = load_vault()
    
    print("\nCurrent Secrets:")
    for k in vault.keys():
        print(f"  - {k}")
    
    print("\nActions:")
    print("  1. Add/Update Secret")
    print("  2. Delete Secret")
    print("  3. Exit")
    
    choice = input("\nSelection: ").strip()
    
    if choice == "1":
        name = input("Secret Name (e.g., TAVILY_API_KEY): ").strip()
        value = getpass.getpass(f"Enter value for {name} (input will be hidden): ")
        if value:
            vault[name] = value
            save_vault(vault)
            print(f"✅ Secret '{name}' saved successfully.")
        else:
            print("❌ Value cannot be empty.")
            
    elif choice == "2":
        name = input("Secret Name to delete: ").strip()
        if name in vault:
            del vault[name]
            save_vault(vault)
            print(f"✅ Secret '{name}' deleted.")
        else:
            print(f"❌ Secret '{name}' not found.")
            
    else:
        print("Exiting...")

if __name__ == "__main__":
    main()
