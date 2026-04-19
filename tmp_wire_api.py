from pathlib import Path

path = Path("core/api_fastapi.py")
content = path.read_text(encoding="utf-8")

import_line = "from core.routes.system_v1_api import router as system_v1_router"
include_line = "app.include_router(system_v1_router)"

lines = content.splitlines()

# ---- 1. Ensure import exists ----
if import_line not in content:
    # find last import line
    insert_idx = 0
    for i, line in enumerate(lines):
        if line.startswith("import") or line.startswith("from"):
            insert_idx = i + 1

    lines.insert(insert_idx, import_line)
    print("Import inserted at line", insert_idx)
else:
    print("Import already present")

# ---- 2. Ensure router is included AFTER app = FastAPI() ----
if include_line not in content:
    for i, line in enumerate(lines):
        if "FastAPI(" in line:
            lines.insert(i + 1, include_line)
            print("Router inserted after FastAPI init")
            break
else:
    print("Router already included")

# ---- 3. Write back ----
path.write_text("\n".join(lines), encoding="utf-8")
print("api_fastapi.py safely updated")
