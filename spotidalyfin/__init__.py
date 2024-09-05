import sys
from pathlib import Path

APPLICATION_PATH = Path(sys._MEIPASS).resolve() if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS') else Path(
    __file__).resolve().parent
