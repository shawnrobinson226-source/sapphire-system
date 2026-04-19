from pathlib import Path

path = Path("core/api_fastapi.py")
lines = path.read_text(encoding="utf-8").splitlines()

import_line = "from core.routes.system_v1_api import router as system_v1_router"
include_line = "app.include_router(system_v1_router)"

# remove all old copies first
lines = [line for line in lines if line.strip() not in {import_line, include_line}]

# insert import after the last import/from line
import_idx = 0
for i, line in enumerate(lines):
    if line.startswith("import ") or line.startswith("from "):
        import_idx = i + 1
lines.insert(import_idx, import_line)

# insert include right after app = FastAPI(...)
include_idx = None
for i, line in enumerate(lines):
    if "FastAPI(" in line:
        include_idx = i + 1
        break

if include_idx is None:
    raise RuntimeError("Could not find FastAPI app initialization line")

lines.insert(include_idx, include_line)

path.write_text("\\n".join(lines) + "\\n", encoding="utf-8")
print("api_fastapi.py fixed")
print("import inserted at line", import_idx + 1)
print("include inserted at line", include_idx + 1)
