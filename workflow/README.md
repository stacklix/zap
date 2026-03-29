# ⚡ Zap

> **Zap your bookmarks. Instant access, zero friction.**

Zap is a lightweight, high-performance Alfred Workflow designed to manage and launch your favorite URLs with lightning speed. Stop digging through folders or browser tabs—just type, zap, and go.

## 🚀 Features

- **⚡ Instant Launch**: Search by title and open links in your default browser immediately.
- **➕ Easy Management**: Add, edit, or delete bookmarks directly from Alfred without leaving your keyboard.
- **🔍 Smart Search**: Fuzzy matching ensures you find what you need even with partial keywords.
- **🛠 Zero Config**: Works out of the box with minimal setup.

## ⚙️ Environment variables

Set in Alfred via the workflow **[×] → Variables** (stored in `info.plist` defaults; overrides go in `prefs.plist`):

- **`DATA_PATH`** — Absolute or `~` path to the Zap data directory (default: `~/.config/alfred`). Bookmarks are stored as `zap.json` inside that folder; other files may use the same directory later.
- **`WEB_PORT`** — Local port for `zap web` (default in this workflow: `14535`). Empty or invalid values fall back to that default.

Running `zap.py` outside Alfred without these variables uses the same defaults.

## 💡 Usage

Type `zap` in Alfred, then (if needed) a space and the rest. Commands:

- `zap <text>` — Search titles/URLs; select a row, **Enter** opens it in the browser (e.g. `zap goo`).
- `zap edit <title> <url>` — Add or update a bookmark (e.g. `zap edit github https://github.com`).
- `zap edit <title>` — Same without URL; a dialog asks for the link.
- `zap del <title>` — Remove a bookmark after confirmation (e.g. `zap del github`).
- `zap web` — Open the local web UI to manage bookmarks. The built-in server stops automatically about half a minute after you close every browser tab (no page + no heartbeat).

---
*Built for developers who value speed.*