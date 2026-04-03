# Manifest Reference

Every plugin needs a `plugin.json` in its root folder.

## Fields

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `name` | string | Yes | — | Unique identifier (must match folder name) |
| `version` | string | No | — | Semver (`1.0.0`) |
| `description` | string | No | — | One-line summary |
| `author` | string | No | — | Author name |
| `url` | string | No | — | Project URL (shown in Settings) |
| `priority` | int | No | 50 | Execution order within band (lower = first) |
| `default_enabled` | bool | No | false | Auto-enable on fresh install |
| `capabilities` | object | No | — | What the plugin provides (see below) |

## Capabilities

The `capabilities` object declares what the plugin provides:

```json
{
  "capabilities": {
    "hooks": { ... },
    "voice_commands": [ ... ],
    "tools": [ ... ],
    "routes": [ ... ],
    "schedule": [ ... ],
    "settings": [ ... ],
    "web": { ... }
  }
}
```

Each capability is documented in its own guide:
- [Hooks & Voice Commands](hooks.md)
- [Tools](tools.md)
- [Routes](routes.md)
- [Schedule](schedule.md)
- [Settings & Web UI](settings.md)

## Priority Bands

Lower fires first. Within each band:

| Range | Purpose |
|-------|---------|
| 0-19 | Critical intercepts (stop, security) |
| 20-49 | Input modification (translation, formatting) |
| 50-79 | Context enrichment (prompt injection, state) |
| 80-99 | Observation (logging, analytics) |

User plugins use the same ranges but shifted to 100-199.

## Directory Structure

```
plugins/                          # System plugins (0-99)
  voice-commands/
    plugin.json
    plugin.sig
    hooks/stop.py
    hooks/reset.py
  ssh/
    plugin.json
    plugin.sig
    tools/ssh_tool.py
    web/index.js

user/
  plugins/                        # User plugins (100-199)
    my-plugin/
      plugin.json
      hooks/handler.py
  plugin_state/                   # Per-plugin JSON state
    ssh.json
  webui/
    plugins.json                  # Enabled list: {"enabled": [...]}
    plugins/                      # Per-plugin settings
      ssh.json
      image-gen.json
```
