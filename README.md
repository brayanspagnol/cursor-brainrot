# Cursor Brainrot

Opens TikTok, Instagram Reels and YouTube Shorts in 3 windows while Cursor is thinking. Closes only those windows when the agent finishes.

## Installation

**Requirements:** Cursor, Python 3.10+, Chrome/Brave/Edge

```bash
git clone https://github.com/brayanspagnol/cursor-brainrot.git
cd cursor-brainrot
python3 brainrot.py install      # Linux
# py -3 .\brainrot.py install   # Windows
```

Restart Cursor if the hooks don't fire.

## Login

It uses the **same profile** as your Brave/Chrome, so if you're already logged in on the browser, the brainrot windows are logged in too.

`close` closes **only** the 3 brainrot windows. The rest of the browser stays open.

## Usage

```bash
python3 brainrot.py open
python3 brainrot.py close
```

To change the sites, edit `URLS` in `brainrot.py`.

## Uninstall

```bash
python3 brainrot.py uninstall
```
