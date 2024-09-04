import os
import sys

from spotidalyfin import cli

# Fix SSL cert issue with PyInstaller
os.environ['SSL_CERT_FILE'] = os.path.join(sys._MEIPASS, 'certifi', 'cacert.pem')

if __name__ == '__main__':
    cli.app()
