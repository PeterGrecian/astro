#!/usr/bin/env python3
"""astrocam cover control: SG90 servo on GPIO18.

Calibration (2026-06-09): min = open, mid = closed. max is the other open
extreme of the servo's travel and is not used by the cover.

Run on astrocam. Needs gpio group membership (or sudo) for /dev/gpiomem.
"""
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
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
