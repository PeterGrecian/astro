#!/usr/bin/env python3
"""xoverpi-focus — read or set the focuser setting stamped into every frame.

A focus sweep that changes setting between nights is only analysable if each
frame records the setting it was taken at. This writes the one-line file the
capture daemon reads per frame and stamps as FOCUSPOS.

    python3 xoverpi/focus.py              # show current setting
    python3 xoverpi/focus.py 3            # set it (any short label)
    python3 xoverpi/focus.py "2.6mm-in"   # labels are free text
"""
import sys
from pathlib import Path

FOCUS_FILE = Path.home() / "xoverpi-focus"

if len(sys.argv) == 1:
    try:
        print(FOCUS_FILE.read_text().strip() or "unset")
    except OSError:
        print("unset")
else:
    value = " ".join(sys.argv[1:]).strip()
    FOCUS_FILE.write_text(value + "\n")
    print(f"focus set to: {value}")
