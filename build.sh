VERSION=1.0.0

echo "THIS BUNDLES YOUR SECRETS INSIDE THE EXECUTABLE; DO NOT SHARE"
wait 2

rm -rf buildenv build dist syncphony*.spec
python -m venv buildenv
source buildenv/bin/activate
pip install -r requirements.txt pyinstaller

pip uninstall -y pyarrow pandas #  we don't need them / reduce exec size

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
    --add-data "syncphony/ui":"./syncphony/ui" \
    --add-data "buildenv/lib/python3.13/site-packages/streamlit/static":"./streamlit/static" \
    --console \
    --name syncphony-${VERSION}_linux_x86_64  \
    "start_webui.py"
# It works but i have to include all submodules of syncphony and all requirements....

deactivate
rm -rf buildenv