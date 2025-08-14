#!/bin/sh
ls -la /root/
exec /usr/bin/python3 /root/syncphony/start_webui.py "$@" &
exec /usr/bin/chromium --no-sandbox --no-first-run localhost:8501