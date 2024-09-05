VERSION=1.0.0

echo "THIS BUNDLES YOUR SECRETS INSIDE THE EXECUTABLE; DO NOT SHARE"
wait 2

rm -rf buildenv build dist *.spec
python -m venv buildenv
source buildenv/bin/activate
pip install -r requirements.txt
pip install pyinstaller

pyinstaller --noconfirm --onefile --hidden-import spotidalyfin --add-binary spotidalyfin/spotidalyfin.secrets:./ --console --name spotidalyfin-${VERSION}_linux_x86_64 "start.py"
deactivate
rm -rf buildenv