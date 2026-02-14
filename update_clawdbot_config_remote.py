import json
import os
import sys

config_path = os.path.expanduser("~/.clawdbot/clawdbot.json")
if not os.path.exists(config_path):
    print(f"Error: {config_path} not found")
    sys.exit(1)

with open(config_path, 'r') as f:
    data = json.load(f)

# 1. Update GOOGLE_API_KEY in env
if "env" not in data:
    data["env"] = {}
data["env"]["GOOGLE_API_KEY"] = "AIzaSyCvhbwNnqqtVwCU4d7BEdUffMYe72I8sBg"

# 2. Add opencode provider
if "models" not in data:
    data["models"] = {}
if "providers" not in data["models"]:
    data["models"]["providers"] = {}

data["models"]["providers"]["opencode"] = {
    "baseUrl": "http://127.0.0.1:8082/v1",
    "apiKey": "any",
    "api": "openai-completions",
    "models": [
        {
            "id": "gemma-3-27b-it",
            "name": "Gemini Local",
            "reasoning": False,
            "input": ["text"]
        }
    ]
}

# 3. Set primary model
if "agents" not in data:
    data["agents"] = {}
if "defaults" not in data["agents"]:
    data["agents"]["defaults"] = {}
if "model" not in data["agents"]["defaults"]:
    data["agents"]["defaults"]["model"] = {}

data["agents"]["defaults"]["model"]["primary"] = "opencode/gemma-3-27b-it"

# 4. Remove opencode auth profile from clawdbot.json (handled by auth-profiles.json)
if "auth" in data and "profiles" in data["auth"]:
    if "opencode:manual" in data["auth"]["profiles"]:
        del data["auth"]["profiles"]["opencode:manual"]

with open(config_path, 'w') as f:
    json.dump(data, f, indent=2)

print("clawdbot.json updated successfully")

# 5. Update auth-profiles.json
auth_path = os.path.expanduser("~/.clawdbot/agents/main/agent/auth-profiles.json")
if os.path.exists(auth_path):
    with open(auth_path, 'r') as f:
        auth_data = json.load(f)
    
    if "profiles" not in auth_data:
        auth_data["profiles"] = {}
    
    auth_data["profiles"]["opencode:manual"] = {
        "type": "api-key",
        "provider": "opencode",
        "access": "any"
    }
    
    if "lastGood" not in auth_data:
        auth_data["lastGood"] = {}
    auth_data["lastGood"]["opencode"] = "opencode:manual"
    
    # Also fix any previous corruption in current auth_data
    if "usageStats" in auth_data:
        for profile, stats in auth_data["usageStats"].items():
            if profile == "google:manual" and isinstance(stats.get("lastUsed"), str):
                stats["lastUsed"] = 1739508492000
    
    with open(auth_path, 'w') as f:
        json.dump(auth_data, f, indent=2)
    print("auth-profiles.json updated successfully")
else:
    print(f"Warning: {auth_path} not found, skipping auth-profiles update")
