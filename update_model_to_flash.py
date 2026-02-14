import json
import os
import sys

config_path = os.path.expanduser("~/.clawdbot/clawdbot.json")
if not os.path.exists(config_path):
    print(f"Error: {config_path} not found")
    sys.exit(1)

with open(config_path, 'r') as f:
    data = json.load(f)

# Update model to gemini-1.5-flash
if "models" in data and "providers" in data["models"] and "opencode" in data["models"]["providers"]:
    data["models"]["providers"]["opencode"]["models"] = [
        {
            "id": "gemini-1.5-flash",
            "name": "Gemini 1.5 Flash",
            "reasoning": False,
            "input": ["text"]
        }
    ]

if "agents" in data and "defaults" in data["agents"] and "model" in data["agents"]["defaults"]:
    data["agents"]["defaults"]["model"]["primary"] = "opencode/gemini-1.5-flash"

with open(config_path, 'w') as f:
    json.dump(data, f, indent=2)

print("clawdbot.json updated to gemini-1.5-flash")
