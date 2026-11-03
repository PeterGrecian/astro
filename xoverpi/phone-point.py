#!/usr/bin/env python3
"""Live pointing feedback from the Pixel 6a strapped to the FirstScope (scopecam /pose).

The phone is rigid with the tube, so the change in ITS orientation since the start is the
change in the scope's. The gyro "game" quaternion has gravity right but an arbitrary yaw,
which is all we need for a change:
  turn = rotation about the vertical (exact, any yaw), + = west (azimuth falls)
  tilt = rotation about a horizontal axis, signed by whether the scope's own altitude fell
The scope's pointing at the start comes from the latest pole-point solve (muppet), and the
remaining move is that solve's tilt/rotation error minus what the phone has seen since.
Run on pip (the phone is LAN-only):  python3 phone-point.py  [--tilt T --turn R]
Ctrl-C to stop. Re-run to take a new reference after a fresh solve."""
import argparse, json, math, subprocess, sys, time, urllib.request

POSE = "http://192.168.0.29:8080/pose"


def qmul(a, b):
    ax, ay, az, aw = a; bx, by, bz, bw = b
    return (aw*bx + ax*bw + ay*bz - az*by, aw*by - ax*bz + ay*bw + az*bx,
            aw*bz + ax*by - ay*bx + az*bw, aw*bw - ax*bx - ay*by - az*bz)


def qconj(q):
    return (-q[0], -q[1], -q[2], q[3])


def rotvec(q):
    """rotation vector (deg) of a unit quaternion, xyz in the world (ENU) frame"""
    x, y, z, w = q
    if w < 0:
        x, y, z, w = -x, -y, -z, -w
    s = math.sqrt(x*x + y*y + z*z)
    ang = 2 * math.degrees(math.atan2(s, w))
    return (0, 0, 0) if s < 1e-12 else (ang*x/s, ang*y/s, ang*z/s)


def rot(q, v):
    p = qmul(qmul(q, (*v, 0.0)), qconj(q))
    return p[:3]


def pose():
    with urllib.request.urlopen(POSE, timeout=3) as r:
        return json.load(r)


def latest_solve():
    out = subprocess.run(["ssh", "muppet", "tail -40 ~/tmp/pole-point/solves.csv"],
                         capture_output=True, text=True, timeout=20).stdout.splitlines()
    for line in reversed(out):
        f = line.split(",")
        if len(f) > 9 and f[2] == "True":
            return f[0], float(f[4]), float(f[5]), float(f[8]), float(f[9])
    return None


ap = argparse.ArgumentParser()
ap.add_argument("--tilt", type=float, help="tilt still to make at the start, deg (+ up); default: latest solve")
ap.add_argument("--turn", type=float, help="rotation still to make, deg (+ east); default: latest solve")
a = ap.parse_args()
alt0 = None
if a.tilt is None or a.turn is None:
    s = latest_solve()
    if not s:
        sys.exit("no recent solve; give --tilt and --turn")
    t, alt0, az0, tilt0, rot0 = s
    print(f"reference solve {t[11:19]} UTC: alt {alt0:.2f} az {az0:+.2f}, needs tilt {tilt0:+.2f} rotation {rot0:+.2f}")
else:
    tilt0, rot0 = a.tilt, a.turn
q0 = tuple(pose()["game_quat_xyzw"])
print("hold still... reference taken. Move now. (tilt + = up, rotation + = east, as pole-point)")
# the scope's direction is unknown in the phone frame, but a horizontal-axis rotation's sign
# on the scope's altitude is set by the axis: a scope pointing north (az ~ 0) goes UP when it
# turns about +E... in the gyro frame north is unknown, so sign tilt by the phone's own pitch
# change instead, with the sign found from the first clear move (printed raw too).
while True:
    try:
        p = pose()
    except Exception as e:
        print(f"\r  pose failed: {e}            ", end="", flush=True); time.sleep(1); continue
    q = tuple(p["game_quat_xyzw"])
    dq = qmul(q, qconj(q0))                     # world-frame rotation since the reference
    wx, wy, wz = rotvec(dq)
    turn_east = -wz                              # +z (up) rotation moves the axis from N toward W
    horiz = math.hypot(wx, wy)
    dalt_phone = p["alt_deg"]
    print(f"\r  turned {turn_east:+6.2f} (still {rot0 - turn_east:+6.2f})   tilted {horiz:5.2f} about a horizontal axis"
          f" (need {abs(tilt0):.2f})   phone alt {dalt_phone:+6.2f} roll {p['roll_deg']:+7.2f}   ",
          end="", flush=True)
    time.sleep(0.25)
