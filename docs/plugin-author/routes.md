# HTTP Routes

Plugins can register custom HTTP endpoints. Auth, CSRF, and rate limiting are enforced by the framework — your handler code never touches any of that.

## Manifest Declaration

```json
{
  "capabilities": {
    "routes": [
      {
        "method": "POST",
        "path": "capture/{request_id}",
        "handler": "routes/capture.py:handle_capture"
      }
    ]
  }
}
```

The full URL becomes: `POST /api/plugin/{plugin_name}/{path}`

For the example above: `POST /api/plugin/webcam/capture/abc123`

## Route Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `method` | string | No | `GET`, `POST`, `PUT`, or `DELETE` (default: `GET`) |
| `path` | string | Yes | URL path (supports `{param}` placeholders) |
| `handler` | string | Yes | `file:function` reference (default function: `handle`) |

## Handler Signature

```python
def handle_capture(request_id: str, body: dict, settings: dict) -> dict:
    """
    Args:
        request_id: Extracted from {request_id} in the path
        body: Parsed JSON body (POST/PUT only, empty dict for GET/DELETE)
        settings: Plugin settings from user/webui/plugins/{name}.json

    Returns:
        dict (auto-serialized to JSON) or a FastAPI Response object
    """
    return {"status": "ok"}
```

Path parameters are passed as keyword arguments matching the `{name}` in your path pattern. `body` and `settings` are always provided.

## Security

All of the following are enforced automatically — you cannot disable them:

- **Authentication**: `require_login` dependency — session or API key required
- **CSRF**: Middleware validates tokens on POST/PUT/DELETE from browser sessions
- **Rate limiting**: 30 requests per 60 seconds per session per plugin

## Example: Webcam Capture Endpoint

```
plugins/webcam/
  plugin.json
  routes/capture.py
  tools/webcam.py
```

**plugin.json:**
```json
{
  "name": "webcam",
  "version": "1.0.0",
  "capabilities": {
    "tools": ["tools/webcam.py"],
    "routes": [
      {
        "method": "POST",
        "path": "capture/{request_id}",
        "handler": "routes/capture.py:handle_capture"
      }
    ]
  }
}
```

**routes/capture.py:**
```python
import threading

# Pending capture requests: {request_id: {"event": Event, "image": None}}
_pending = {}
_lock = threading.Lock()

def create_request(request_id, timeout=15):
    """Called by the tool — blocks until browser POSTs the image."""
    event = threading.Event()
    with _lock:
        _pending[request_id] = {"event": event, "image": None}
    event.wait(timeout=timeout)
    with _lock:
        data = _pending.pop(request_id, {})
    return data.get("image")

def handle_capture(request_id: str, body: dict, **_) -> dict:
    """Called by the browser — delivers the captured image."""
    with _lock:
        req = _pending.get(request_id)
    if not req:
        return {"error": "No pending request"}
    req["image"] = body
    req["event"].set()
    return {"status": "ok"}
```

## Notes

- Routes are registered on plugin load and removed on unload
- Hot reload (`POST /api/plugins/{name}/reload`) re-registers routes
- Handlers can be sync or async — async handlers are awaited directly, sync handlers run in a threadpool
- Path parameters only match single path segments (no slashes)
