VERSION=1.0.0

echo "THIS BUNDLES YOUR SECRETS INSIDE THE EXECUTABLE; DO NOT SHARE"
wait 2

rm -rf buildenv build dist *.spec
python -m venv buildenv
source buildenv/bin/activate
#pip install -r requirements.txt
#pip install pyinstaller

# cleaner (less junk)
CFLAGS="-g0 -Wl,--strip-all" \
        pip install \
        --no-cache-dir \
        --compile \
        --global-option=build_ext \
        --global-option="-j 4" \
        -r requirements.txt
CFLAGS="-g0 -Wl,--strip-all" \
        pip install \
        --no-cache-dir \
        --compile \
        --global-option=build_ext \
        --global-option="-j 4" \
        pyinstaller

pyinstaller --noconfirm --onefile --hidden-import spotidalyfin --add-binary spotidalyfin/spotidalyfin.secrets:./ --console --name spotidalyfin-${VERSION}_linux_x86_64 "pyinstaller_start.py"
deactivate
rm -rf buildenv