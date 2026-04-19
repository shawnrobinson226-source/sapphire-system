import json
from pathlib import Path

# 1) force plugins.json
plugins_path = Path("user/webui/plugins.json")
plugins_path.parent.mkdir(parents=True, exist_ok=True)
plugins_data = {"enabled": ["voice-commands", "vanta-execution"]}
plugins_path.write_text(json.dumps(plugins_data, indent=2), encoding="utf-8")
print("plugins.json written:")
print(plugins_path.read_text(encoding="utf-8"))

# 2) inspect plugin_loader.py lines related to verification
loader_path = Path("core/plugin_loader.py")
content = loader_path.read_text(encoding="utf-8")

print("\n--- verification-related lines in core/plugin_loader.py ---")
for i, line in enumerate(content.splitlines(), start=1):
    low = line.lower()
    if "verify" in low or "tamper" in low or "failed" in low or "unsigned" in low:
        print(f"{i}: {line}")
