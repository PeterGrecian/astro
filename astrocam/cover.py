#!/usr/bin/env python3
"""astrocam cover control: SG90 servo on GPIO18.

Calibration (2026-06-09): min = open, mid = closed. max is the other open
extreme of the servo's travel and is not used by the cover.

Run on astrocam. Needs gpio group membership (or sudo) for /dev/gpiomem.

After each move the pin is released and driven low with pinctrl, so the
SG90 sees a steady 0 V between moves instead of a floating input it can
twitch on. config.txt sets gpio=18=op,dl for the same state from boot.
"""
import subprocess
import sys
from time import sleep

from gpiozero import Servo

SERVO_PIN = 18
SETTLE_S = 0.8

POSITIONS = {
    "open": lambda s: s.min(),
    "closed": lambda s: s.mid(),
}


def main(argv):
    if len(argv) != 2 or argv[1] not in POSITIONS:
        print(f"usage: {argv[0]} {{{'|'.join(POSITIONS)}}}", file=sys.stderr)
        return 2
    servo = Servo(SERVO_PIN)
    POSITIONS[argv[1]](servo)
    sleep(SETTLE_S)
    servo.close()
    subprocess.run(["pinctrl", "set", str(SERVO_PIN), "op", "dl"], check=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
