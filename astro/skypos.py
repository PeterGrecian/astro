"""skypos — pole distances of bright northern stars at an arbitrary epoch.

Everything the drift-scan geometry needs from the sky is *pole distance*: the
angle between a star and the celestial pole. It is invariant to time of night,
to field rotation and to which way is east, so a star's arc in an all-night
stack is a circle of that radius about the pole pixel — the one sky quantity
we can measure without solving a plate.

Pole distance is NOT constant over years. Precession moves the pole ~20"/yr,
and for Polaris — sitting almost on it — that is a large *fractional* change:
0.736 deg at J2000, 0.626 deg in 2026, heading for ~0.46 deg around 2100. A
hardcoded value goes stale fast and silently rescales anything derived from it,
so callers pass an epoch and get the value for that epoch.

Positions are ICRS J2000 + proper motion, precessed with the IAU-1976 angles to
the mean equator of date. Nutation (<10") and aberration (<21") are ignored:
both are far below the few-percent lens distortion that dominates our error
budget, and neither accumulates with time the way precession does.
"""
from datetime import datetime, timezone

import numpy as np

# name, RA J2000 (deg), Dec J2000 (deg), V mag, pmRA*(mas/yr), pmDec (mas/yr)
BRIGHT_NORTH = [
    ("Polaris",     37.9546, 89.2641, 1.97,   44.48,  -11.85),
    ("Kochab",     222.6764, 74.1554, 2.06,  -32.61,   11.42),
    ("Pherkad",    230.1822, 71.8340, 3.05,  -18.50,    1.90),
    ("Segin",       28.5988, 63.6701, 3.35,   34.50,  -18.60),
    ("Alderamin",  319.6449, 62.5856, 2.45,  149.91,   48.27),
    ("Dubhe",      165.9319, 61.7511, 1.81, -136.46,  -35.25),
    ("Gamma Cas",   14.1772, 60.7167, 2.04,   25.65,   -3.82),
    ("Ruchbah",     21.4540, 60.2353, 2.66,  297.60,  -49.10),
    ("Caph",         2.2945, 59.1498, 2.27,  523.50,  -180.0),
    ("Megrez",     183.8565, 57.0326, 3.31,  103.56,    7.81),
    ("Schedar",     10.1268, 56.5373, 1.94,   50.36,  -32.17),
    ("Merak",      165.4603, 56.3824, 2.34,   81.66,   33.74),
    ("Alioth",     193.5073, 55.9598, 1.76,  111.91,   -8.24),
    ("Mizar",      200.9814, 54.9254, 2.27,  121.23,  -22.01),
    ("Phecda",     178.4577, 53.6948, 2.41,  107.68,   11.01),
    ("Eltanin",    269.1515, 51.4889, 2.23,   -8.48,  -22.79),
    ("Mirfak",      51.0807, 49.8612, 1.79,   24.11,  -26.01),
    ("Alkaid",     206.8857, 49.3133, 1.86, -121.23,  -15.56),
    ("Capella",     79.1723, 45.9980, 0.08,   75.52, -427.11),
    ("Deneb",      310.3580, 45.2803, 1.25,    2.01,    1.85),
    ("Algol",       47.0422, 40.9556, 2.12,    2.39,   -1.44),
    ("Vega",       279.2347, 38.7837, 0.03,  200.94,  286.23),
]


def current_epoch():
    """Now as a fractional year — the sensible default for live frames."""
    now = datetime.now(timezone.utc)
    start = datetime(now.year, 1, 1, tzinfo=timezone.utc)
    end = datetime(now.year + 1, 1, 1, tzinfo=timezone.utc)
    return now.year + (now - start).total_seconds() / (end - start).total_seconds()


def pole_distance(ra_deg, dec_deg, epoch, pm_ra_mas=0.0, pm_dec_mas=0.0):
    """Angle (deg) from the celestial pole at `epoch`, from J2000 ICRS."""
    dt = epoch - 2000.0
    dec = dec_deg + pm_dec_mas * 1e-3 * dt / 3600.0
    ra = ra_deg + (pm_ra_mas * 1e-3 * dt / 3600.0) / np.cos(np.radians(dec))
    t = dt / 100.0
    zeta = np.radians((2306.2181 * t + 0.30188 * t**2 + 0.017998 * t**3) / 3600.0)
    theta = np.radians((2004.3109 * t - 0.42665 * t**2 - 0.041833 * t**3) / 3600.0)
    a0, d0 = np.radians(ra), np.radians(dec)
    sin_dec = (np.sin(theta) * np.cos(d0) * np.cos(a0 + zeta)
               + np.cos(theta) * np.sin(d0))
    return 90.0 - np.degrees(np.arcsin(sin_dec))


def polaris_pole_distance(epoch=None):
    """Polaris–pole separation (deg) at `epoch` (default: now)."""
    name, ra, dec, v, pmra, pmdec = BRIGHT_NORTH[0]
    return float(pole_distance(ra, dec, current_epoch() if epoch is None else epoch,
                               pmra, pmdec))


def bright_pole_distances(epoch=None, mag_limit=None):
    """[(name, V, pole_distance_deg)] sorted by pole distance, at `epoch`."""
    ep = current_epoch() if epoch is None else epoch
    out = [(n, v, float(pole_distance(ra, dec, ep, pmra, pmdec)))
           for n, ra, dec, v, pmra, pmdec in BRIGHT_NORTH
           if mag_limit is None or v <= mag_limit]
    return sorted(out, key=lambda row: row[2])
