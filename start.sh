#!/usr/bin/env sh
# Lance KrakenQ. Sous Termux, garde le processus éveillé.
cd "$(dirname "$0")" || exit 1
command -v termux-wake-lock >/dev/null 2>&1 && termux-wake-lock
exec python3 app.py "$@"
