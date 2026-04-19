from pathlib import Path

path = Path("core/api_fastapi.py")
content = path.read_text(encoding="utf-8")

import_line = "from core.routes.system_v1_api import router as system_v1_router"
include_line = "app.include_router(system_v1_router)"

if import_line not in content:
    content = import_line + "\n" + content
    print("Import added at top")
else:
    print("Import exists")

if include_line not in content:
    content = content + "\n\n" + include_line + "\n"
    print("Router included at bottom")
else:
    print("Router already included")

path.write_text(content, encoding="utf-8")
print("Safe wiring complete")
