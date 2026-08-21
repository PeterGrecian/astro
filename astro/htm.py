"""htm — Hierarchical Triangular Mesh: sky positions as nested integer cells.

WHY HTM AND NOT HEALPix. Both tile the sphere with an exact 4:1 nesting, which
is the property the accumulator needs: four fine cells sit exactly inside one
coarse cell, so binning down is integer addition of children — no resampling,
no interpolation, no error baked in. HTM adds the thing that matters for a
progressive ladder: the cell id is a PREFIX CODE. A level-N id truncated by two
bits IS the level-(N-1) id containing it, so the coarse map is a `>> 2` away and
the ladder's rungs are the same numbers at different lengths.

The cost is that HTM trixels within a level are not equal-area — they vary by
about a factor of 2 between the middle of a base face and its corners. That is
fine here because the variation is DETERMINISTIC: each trixel's area is
computable exactly (`trixel_area`), so a surface-brightness accumulator divides
it out. An equal-area grid buys nothing we cannot compute.

Levels: 8 * 4**level trixels, mean area 41252.96 / (8 * 4**level) deg**2.

  level 0     8 trixels    5157 deg^2     ~110 deg on a side
  level 3   512 trixels    80.6 deg^2      ~13.6 deg
  level 4  2048 trixels    20.1 deg^2       ~6.8 deg
  level 8  524288          0.079 deg^2      ~0.4 deg
"""
import numpy as np

# Octahedron vertices: +z, the four equatorial directions, -z.
_V = np.array([
    [0.0, 0.0, 1.0],    # 0  north pole
    [1.0, 0.0, 0.0],    # 1
    [0.0, 1.0, 0.0],    # 2
    [-1.0, 0.0, 0.0],   # 3
    [0.0, -1.0, 0.0],   # 4
    [0.0, 0.0, -1.0],   # 5  south pole
])

# The eight level-0 faces, counter-clockwise seen from outside, in the
# canonical HTM order S0..S3 then N0..N3, which fixes ids 8..15.
_BASE = [
    ("S0", (1, 5, 2)), ("S1", (2, 5, 3)), ("S2", (3, 5, 4)), ("S3", (4, 5, 1)),
    ("N0", (1, 0, 4)), ("N1", (4, 0, 3)), ("N2", (3, 0, 2)), ("N3", (2, 0, 1)),
]


def radec_to_vec(ra_deg, dec_deg):
    ra, dec = np.radians(ra_deg), np.radians(dec_deg)
    return np.stack([np.cos(dec) * np.cos(ra),
                     np.cos(dec) * np.sin(ra),
                     np.sin(dec)], axis=-1)


def vec_to_radec(v):
    v = np.asarray(v, dtype=float)
    v = v / np.linalg.norm(v, axis=-1, keepdims=True)
    return (np.degrees(np.arctan2(v[..., 1], v[..., 0])) % 360.0,
            np.degrees(np.arcsin(np.clip(v[..., 2], -1, 1))))


def _inside(p, a, b, c):
    """True where p lies in the spherical triangle a,b,c (counter-clockwise)."""
    return ((np.cross(a, b) @ p.T >= 0)
            & (np.cross(b, c) @ p.T >= 0)
            & (np.cross(c, a) @ p.T >= 0))


def _children(a, b, c):
    """The four sub-triangles, in HTM child order 0..3."""
    def mid(u, v):
        w = u + v
        return w / np.linalg.norm(w)
    w0, w1, w2 = mid(b, c), mid(a, c), mid(a, b)
    return [(a, w2, w1), (b, w0, w2), (c, w1, w0), (w0, w1, w2)]


def htm_id(ra_deg, dec_deg, level):
    """Trixel id at `level` for one position. Ids are a prefix code: the id at
    level-1 is exactly `htm_id(..., level) >> 2`."""
    p = radec_to_vec(ra_deg, dec_deg)
    tri = None
    for n, (name, (i, j, k)) in enumerate(_BASE):
        a, b, c = _V[i], _V[j], _V[k]
        if _inside(p[None, :], a, b, c)[0]:
            ident, tri = 8 + n, (a, b, c)
            break
    if tri is None:                       # exactly on a shared edge
        raise ValueError(f"no base trixel for ({ra_deg}, {dec_deg})")
    for _ in range(level):
        for ci, kids in enumerate(_children(*tri)):
            if _inside(p[None, :], *kids)[0]:
                ident, tri = (ident << 2) | ci, kids
                break
        else:                             # numerical tie on an edge
            ident, tri = (ident << 2) | 3, _children(*tri)[3]
    return ident


def htm_name(ident):
    """Classic HTM name, e.g. 'N301' — readable, and the same prefix code."""
    bits = []
    while ident > 15:
        bits.append(ident & 3)
        ident >>= 2
    face = _BASE[ident - 8][0]
    return face + "".join(str(b) for b in reversed(bits))


def htm_level(ident):
    return (ident.bit_length() - 4) // 2


def trixel_vertices(ident):
    """The three corner unit vectors of a trixel id."""
    path = []
    while ident > 15:
        path.append(ident & 3)
        ident >>= 2
    i, j, k = _BASE[ident - 8][1]
    tri = (_V[i], _V[j], _V[k])
    for ci in reversed(path):
        tri = _children(*tri)[ci]
    return tri


def trixel_area(ident):
    """Exact spherical area (deg^2) by the spherical excess of the trixel."""
    a, b, c = trixel_vertices(ident)
    # side lengths, then the spherical excess via l'Huilier's formula
    A = np.arccos(np.clip(b @ c, -1, 1))
    B = np.arccos(np.clip(a @ c, -1, 1))
    C = np.arccos(np.clip(a @ b, -1, 1))
    s = (A + B + C) / 2
    t = np.tan(s / 2) * np.tan((s - A) / 2) * np.tan((s - B) / 2) * np.tan((s - C) / 2)
    return float(np.degrees(1) ** 2 * 4 * np.arctan(np.sqrt(max(t, 0.0))))


def n_trixels(level):
    return 8 * 4 ** level


def mean_area_deg2(level):
    return 41252.96124941928 / n_trixels(level)
