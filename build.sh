VERSION=1.0.0

echo "THIS BUNDLES YOUR SECRETS INSIDE THE EXECUTABLE; DO NOT SHARE"
wait 2

rm -rf buildenv build dist *.spec
python -m venv buildenv
source buildenv/bin/activate
pip install -r requirements.txt
pip install pyinstaller

# bundle streamrip
wget https://github.com/M4TH1EU/streamrip/releases/download/2.0.5/streamrip-2.0.5-linux -O ./spotidalyfin/streamrip
chmod +x ./spotidalyfin/streamrip

pyinstaller --noconfirm --onefile --hidden-import spotidalyfin --add-binary spotidalyfin/spotidalyfin.secrets:./ --add-binary ./spotidalyfin/streamrip:./ --console --name spotidalyfin-${VERSION}_linux_x86_64 "pyinstaller_start.py"
deactivate
rm -rf buildenv