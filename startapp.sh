#!/bin/sh
/usr/bin/python3 /syncphony/start_webui.py "$@" &
exec /usr/bin/chromium --no-sandbox --no-first-run --start-fullscreen "http://localhost:8501"