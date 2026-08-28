#!/usr/bin/env python3
"""publish.py — publish one card file to the Transients gallery.

Renders the image from the card's own `source:` recipe, then hands the front
matter and prose to bin/add-transient. This is the step that makes the git copy
the thing you EDIT rather than a transcript of what was published: edit the
card, run this, the gallery matches.

Reusing the `id` from the front matter is what makes a re-publish REPLACE the
entry rather than add a second one, so renaming a card's title is safe and
changing its id is not.

    publish.py <card.md> [--root DIR] [--publish]

Without --publish it is a dry run, like add-transient itself.

Registered as a Front Matter CMS custom action in frontmatter.json, so it is
also a button next to the card in VS Code.
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
ADD = REPO / "bin" / "add-transient"


def sections(path: Path) -> dict:
    """The prose, split on the '# Heading' lines. Evidence becomes a list of
    its bullets; the rest are joined into flowing paragraphs, because the card
    file is wrapped for reading and the gallery wants unwrapped sentences."""
    body = re.sub(r"^---\n.*?\n---\n", "", path.read_text(), flags=re.S)
    out, cur = {}, None
    for line in body.splitlines():
        h = re.match(r"^#\s+(\w+)", line)
        if h:
            cur = h.group(1).lower()
            out[cur] = []
            continue
        if cur:
            out[cur].append(line)
    res = {}
    for k, lines in out.items():
        if k == "evidence":
            items, buf = [], ""
            for ln in lines:
                if ln.startswith("- "):
                    if buf:
                        items.append(buf.strip())
                    buf = ln[2:]
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
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("card", type=Path, nargs="+",
                    help="the card file. Front Matter CMS passes <projectPath> "
                         "<filePath>, so a leading directory argument is "
                         "tolerated and skipped.")
    ap.add_argument("--root", type=Path, default=Path.home())
    ap.add_argument("--publish", action="store_true")
    args = ap.parse_args()
    cards = [c for c in args.card if not c.is_dir()]
    if len(cards) != 1:
        ap.error("expected exactly one card file, got %r" % [str(c) for c in args.card])
    args.card = cards[0]

    meta = parse_card(args.card)
    sec = sections(args.card)
    img = render(meta, args.root)

    with tempfile.TemporaryDirectory() as td:
        png = Path(td) / f"{meta['id']}.png"
        img.save(png)
        cmd = [sys.executable, str(ADD), str(png),
               "--id", str(meta["id"]),
               "--title", str(meta["title"]),
               "--category", str(meta["category"]),
               "--confidence", str(meta.get("confidence", "unknown")),
               "--date", str(meta["date"]),
               "--caption", sec.get("caption", ""),
               "--rationale", sec.get("reasoning", "")]
        for k, flag in (("time", "--time"), ("camera", "--camera"), ("night", "--night")):
            if meta.get(k):
                cmd += [flag, str(meta[k])]
        for e in sec.get("evidence", []):
            cmd += ["--evidence", e]
        if args.publish:
            cmd.append("--publish")
        return subprocess.call(cmd)


if __name__ == "__main__":
    sys.exit(main())
