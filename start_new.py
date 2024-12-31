# Fix SSL cert issue with PyInstaller
import os
import sys

import streamlit

if hasattr(sys, '_MEIPASS'):
    os.environ['SSL_CERT_FILE'] = os.path.join(sys._MEIPASS, 'certifi', 'cacert.pem')

if __name__ == '__main__':
