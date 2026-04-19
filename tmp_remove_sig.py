from pathlib import Path

sig_file = Path("plugins/vanta_execution/plugin.sig")
if sig_file.exists():
    sig_file.unlink()
    print("Removed plugin.sig - plugin will now be treated as unsigned")
else:
    print("No sig file found")
