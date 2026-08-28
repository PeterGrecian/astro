#!/usr/bin/env python3
"""publish.py — publish one card file to the Astro Showcase collection.

    publish.py <card.md> [--root DIR] [--publish]
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from render import parse_card, render

REPO = Path(__file__).resolve().parent.parent
ADD = REPO / "bin" / "add-showcase"


def sections(path: Path) -> dict:
    body = re.sub(r"^---\n.*?\n---\n", "", path.read_text(), flags=re.S)
    out, cur = {}, None
    for line in body.splitlines():
        h = re.match(r"^#\s+([\w\s&]+)", line)
        if h:
            cur = h.group(1).lower().strip()
            out[cur] = []
            continue
        if cur:
            out[cur].append(line)
    res = {}
    for k, lines in out.items():
        if "highlight" in k or "evidence" in k or "bullet" in k:
            items, buf = [], ""
            for ln in lines:
                if ln.strip().startswith("- "):
                    if buf:
                        items.append(buf.strip())
                    buf = ln.strip()[2:]
                elif ln.strip():
                    buf += " " + ln.strip()
            if buf:
                items.append(buf.strip())
            res[k] = items
        else:
            paras = re.split(r"\n\s*\n", "\n".join(lines).strip())
            res[k] = "\n\n".join(" ".join(p.split()) for p in paras if p.strip())
    return res


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("card", type=Path, nargs="+")
    ap.add_argument("--root", type=Path, default=Path.home())
    ap.add_argument("--publish", action="store_true")
    args = ap.parse_args()
    cards = [c for c in args.card if not c.is_dir()]
    if len(cards) != 1:
        ap.error(f"expected exactly one card file, got {cards!r}")
    args.card = cards[0]

    meta = parse_card(args.card)
    sec = sections(args.card)
    img = render(meta, args.root)

    with tempfile.TemporaryDirectory() as td:
        png = Path(td) / f"{meta['id']}.png"
        img.save(png)
        cmd = [
            sys.executable, str(ADD), str(png),
            "--id", str(meta["id"]),
            "--title", str(meta["title"]),
            "--category", str(meta.get("category", "deep-sky")),
            "--date", str(meta.get("date", "")),
        ]
        if meta.get("target"):
            cmd += ["--target", str(meta["target"])]
        if meta.get("constellation"):
            cmd += ["--constellation", str(meta["constellation"])]
        if meta.get("featured"):
            cmd.append("--featured")
        if meta.get("time"):
            cmd += ["--time", str(meta["time"])]
        if meta.get("camera"):
            cmd += ["--camera", str(meta["camera"])]
        if meta.get("night"):
            cmd += ["--night", str(meta["night"])]

        eq = meta.get("equipment") or {}
        for k, flag in (("optics", "--optics"), ("focal_length", "--focal-length"),
                        ("f_ratio", "--f-ratio"), ("sensor", "--sensor"),
                        ("mount", "--mount"), ("filter", "--filter")):
            if eq.get(k):
                cmd += [flag, str(eq[k])]

        exp = meta.get("exposure") or {}
        if exp.get("subs"):
            cmd += ["--subs", str(exp["subs"])]
        if exp.get("sub_time"):
            cmd += ["--sub-time", str(exp["sub_time"])]
        if exp.get("total_integration"):
            cmd += ["--total-integration", str(exp["total_integration"])]
        if exp.get("iso_gain"):
            cmd += ["--iso-gain", str(exp["iso_gain"])]
        if exp.get("bortle"):
            cmd += ["--bortle", str(exp["bortle"])]

        if "caption" in sec:
            cmd += ["--caption", sec["caption"]]
        for k in sec:
            if "processing" in k or "observation" in k:
                cmd += ["--processing", sec[k]]
            elif "highlight" in k or "evidence" in k:
                for h in sec[k]:
                    cmd += ["--highlight", h]

        if args.publish:
            cmd.append("--publish")
        return subprocess.call(cmd)


if __name__ == "__main__":
    sys.exit(main())
