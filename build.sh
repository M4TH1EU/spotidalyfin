VERSION=1.0.0

echo "THIS BUNDLES YOUR SECRETS INSIDE THE EXECUTABLE; DO NOT SHARE"
wait 2

rm -rf buildenv build dist spotidalyfin*.spec
python -m venv buildenv
source buildenv/bin/activate
pip install -r requirements.txt pyinstaller

pip uninstall -y pyarrow pandas #  we don't need them / reduce exec size

# pyinstaller --noconfirm --onefile --hidden-import spotidalyfin --add-binary spotidalyfin/spotidalyfin.secrets:./ --console --name spotidalyfin-${VERSION}_linux_x86_64 "start.py" # old terminal interface
# pyinstaller --noconfirm --copy-metadata "streamlit" --collect-all "streamlit" --hidden-import "streamlit" --hidden-import spotidalyfin --add-data "spotidalyfin":"./spotidalyfin" --console --name spotidalyfin-${VERSION}_linux_x86_64 "start_webui.py"
pyinstaller --noconfirm \
    --copy-metadata "streamlit" \
    --hidden-import "streamlit.runtime.scriptrunner.magic_funcs" \
    --hidden-import "mutagen" \
    --hidden-import "tidalapi" \
    --hidden-import "cachebox" \
    --hidden-import "spotipy" \
    --hidden-import "pyacoustid" \
    --hidden-import "musicbrainzngs" \
    --hidden-import "Unidecode" \
    --add-data "assets":"./assets" \
    --add-data "spotidalyfin/ui":"./spotidalyfin/ui" \
    --add-data "buildenv/lib/python3.13/site-packages/streamlit/static":"./streamlit/static" \
    --console \
    --name spotidalyfin-${VERSION}_linux_x86_64  \
    "start_webui.py"
# It works but i have to include all submodules of spotidalyfin and all requirements....

deactivate
rm -rf buildenv