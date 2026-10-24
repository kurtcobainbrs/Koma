"""Entrada do executável Windows; inclui o cliente Flet para uso offline."""

import os
import sys
from pathlib import Path

if getattr(sys, 'frozen', False):
    os.environ['FLET_VIEW_PATH'] = str(Path(sys._MEIPASS) / 'desktop' / 'flet')

from koma.app import main

if __name__ == '__main__':
    raise SystemExit(main())
