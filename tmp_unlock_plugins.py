import json
from pathlib import Path

path = Path("user/settings.json")

if path.exists():
    data = json.loads(path.read_text(encoding="utf-8"))
else:
    data = {}

data["ALLOW_UNSIGNED_PLUGINS"] = True

path.write_text(json.dumps(data, indent=2), encoding="utf-8")
print("ALLOW_UNSIGNED_PLUGINS set to True")
