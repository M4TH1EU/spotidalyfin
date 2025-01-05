# Fix SSL cert issue with PyInstaller
import os
import sys

from streamlit.web import cli

if hasattr(sys, '_MEIPASS'):
    os.environ['SSL_CERT_FILE'] = os.path.join(sys._MEIPASS, 'certifi', 'cacert.pem')

if __name__ == "__main__":
    os.chdir(str(getattr(sys, '_MEIPASS', os.path.abspath(os.path.dirname(__file__)))))

    sys.argv = [
        "streamlit", "run",
        f"{str(getattr(sys, '_MEIPASS', os.path.abspath(os.path.dirname(__file__)))) + '/spotidalyfin/ui/'}streamlit_app.py",
        "--server.port=8501",
        "--global.developmentMode=false",
        "--client.toolbarMode=viewer",
        "--client.showErrorDetails=none",
        "--browser.gatherUsageStats=false",

        "--theme.primaryColor=#924BD1",
        "--theme.backgroundColor=#FFFFFF",
        "--theme.secondaryBackgroundColor=#FBF9FF",
        # "--theme.textColor=#000000",
        "--theme.font=sans serif",
    ]

    cli.main()
