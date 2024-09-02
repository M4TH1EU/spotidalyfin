VERSION=1.0.0

echo "THIS BUNDLES YOUR SECRETS INSIDE THE EXECUTABLE; DO NOT SHARE"
wait 3

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
wget https://raw.githubusercontent.com/M4TH1EU/streamrip/dev/streamrip/config.toml -O config.toml # fix for streamrip

pyinstaller --noconfirm --onefile --hidden-import spotidalyfin --add-binary spotidalyfin/spotidalyfin.secrets:./ --add-binary config.toml:streamrip/ --console --name spotidalyfin-${VERSION}_linux_x86_64 "spotidalyfin/cli.py"
deactivate
rm config.toml
rm -rf buildenv