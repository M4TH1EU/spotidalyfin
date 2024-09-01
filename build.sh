VERSION=1.0.0

rm -rf buildenv build dist *.spec
python -m venv buildenv
source buildenv/bin/activate
pip install -r requirements.txt # more junk
#CFLAGS="-g0 -Wl,--strip-all" \
#        pip install \
#        --no-cache-dir \
#        --compile \
#        --global-option=build_ext \
#        --global-option="-j 4" \
#        -r requirements.txt # cleaner (less junk)
pip install pyinstaller

pyinstaller --noconfirm --onefile --console --add-data config-tidal-dl-ng.json: --add-data config-minim.cfg: --name spotify-tidal-jellyfin${VERSION}_linux_x86_64 "main.py"
deactivate
# rm -rf buildenv