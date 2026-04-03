# Web UI Reference

Reference for plugin web assets — shared JavaScript modules, CSS theming, and patterns.

## Shared Modules

Plugin web UIs can import these from `/static/shared/`:

| Module | Key Exports | Purpose |
|--------|------------|---------|
| `plugin-registry.js` | `registerPluginSettings(config)`, `unregisterPluginSettings(id)` | Register/remove settings tabs |
| `plugins-api.js` | `listPlugins()`, `getSettings(name)`, `saveSettings(name, data)`, `resetSettings(name)`, `togglePlugin(name)` | Plugin backend API wrapper (auto-injects CSRF) |
| `toast.js` | `showToast(msg, type, duration)`, `showActionToast(msg, label, callback, type, duration)` | Non-blocking notifications (`info`, `success`, `warning`, `error`) |
| `modal.js` | `showModal(title, fields, onSave, opts)`, `showConfirm(msg, onConfirm)`, `showPrompt(title, label, default)`, `showHelpModal(title, text)`, `escapeHtml(str)` | Dialogs with auto form serialization |
| `danger-confirm.js` | `showDangerConfirm(config)`, `showDangerBanner(container, msg)` | High-stakes type-to-confirm gates |
| `fetch.js` | `fetchWithTimeout(url, opts, timeout)`, `sessionId` | Pre-configured fetch with CSRF, 401 redirect, timeout |

## Modal Field Types

`showModal()` accepts an array of field objects:

| Type | Properties | Notes |
|------|-----------|-------|
| `text` | `id`, `label`, `value`, `readonly` | Single-line input |
| `number` | `id`, `label`, `value`, `readonly` | Numeric input |
| `textarea` | `id`, `label`, `value`, `rows` | Multi-line (default 6 rows) |
| `select` | `id`, `label`, `options`, `labels`, `value` | Dropdown (`labels` optional) |
| `checkboxes` | `id`, `label`, `options` (object), `selected` (array) | Multi-select, returns array of keys |
| `html` | `value` | Raw HTML, skipped in serialization |

---

## CSS Variables

Use CSS variables for theme compatibility. Key variables:

```css
/* Backgrounds */
--bg: #121212          --bg-secondary: #1a1a1a   --bg-tertiary: #2c2c2c
--bg-hover: #383838

/* Text */
--text: #e0e0e0        --text-secondary: #ccc    --text-muted: #888

/* Borders */
--border: #333         --border-light: #444

/* Semantic */
--success: #4caf50     --warning: #ff9800        --error: #ef5350
--accent-blue: #4a9eff --trim: #4a9eff           /* user-configurable accent */

/* Spacing (density-aware) */
--space-xs: 4px   --space-sm: 8px   --space-md: 12px   --space-lg: 16px

/* Radius */
--radius-sm: 4px  --radius-md: 6px  --radius-lg: 8px

/* Fonts */
--font-sm: 11px   --font-base: 13px --font-md: 14px    --font-lg: 16px
```

---

## Patterns

### Style Injection

Plugin web UIs inject scoped CSS into the document head:

```javascript
function injectStyles() {
    if (document.getElementById('my-plugin-styles')) return;
    const style = document.createElement('style');
    style.id = 'my-plugin-styles';
    style.textContent = `
        .my-plugin-item {
            background: var(--bg-secondary);
            border: 1px solid var(--border);
            border-radius: var(--radius-md);
            padding: var(--space-md);
        }
        .my-plugin-item:hover { background: var(--bg-hover); }
    `;
    document.head.appendChild(style);
}
```

### Plugin Scripts (web/main.js)

Plugins that need JavaScript running in the chat view (not just settings) can provide a `web/main.js` file. It's auto-loaded on app startup for enabled plugins.

```javascript
// web/main.js
export default {
    init() {
        // Runs once when the app loads and this plugin is enabled
        document.addEventListener('sapphire:tool_start', (e) => {
            const { id, name, args } = e.detail;
            // React to tool execution...
        });
    }
};
```

The module must export a `default` object with an `init()` method. It's loaded via dynamic `import()` with full error isolation — a broken plugin script won't crash the app.

**Available DOM events:**

| Event | Detail | Fires When |
|-------|--------|------------|
| `sapphire:tool_start` | `{id, name, args}` | A tool begins executing during chat streaming |

### CSRF Headers

Plugin web UIs making custom API calls need CSRF tokens:

```javascript
function csrfHeaders(extra = {}) {
    const token = document.querySelector('meta[name="csrf-token"]')?.content || '';
    return { 'X-CSRF-Token': token, 'Content-Type': 'application/json', ...extra };
}

const res = await fetch('/api/my-endpoint', {
    method: 'POST',
    headers: csrfHeaders(),
    body: JSON.stringify({ key: 'value' })
});
```
