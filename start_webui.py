import os
import sys

from streamlit.web import cli

# Fix SSL cert issue with PyInstaller
if hasattr(sys, '_MEIPASS'):
    os.environ['SSL_CERT_FILE'] = os.path.join(sys._MEIPASS, 'certifi', 'cacert.pem')

if __name__ == "__main__":
    os.chdir(str(getattr(sys, '_MEIPASS', os.path.abspath(os.path.dirname(__file__)))))

    sys.argv = [
        "streamlit", "run",
        f"{str(getattr(sys, '_MEIPASS', os.path.abspath(os.path.dirname(__file__)))) + '/syncphony/ui/'}streamlit_app.py",
        "--server.port=8501",
        "--server.address=0.0.0.0",
        "--server.showEmailPrompt=false",
        "--global.developmentMode=false",
        "--browser.gatherUsageStats=false",

        "--theme.primaryColor=#00c6a1",
        "--theme.backgroundColor=#FFFFFF",
        "--theme.secondaryBackgroundColor=#eef5ff",
        # "--theme.textColor=#000000",
        "--theme.font=sans serif",
    ]

    if not os.environ.get("DEV", "false").lower() == "true":
        sys.argv.extend([
            "--server.headless=true",
            "--client.showErrorDetails=none",
            "--client.toolbarMode=minimal",
        ])

    cli.main()
