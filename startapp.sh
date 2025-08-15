#!/bin/sh
/usr/bin/python3 /root/syncphony/start_webui.py "$@" &
exec /usr/bin/chromium --no-sandbox --no-first-run "http://localhost:8501"