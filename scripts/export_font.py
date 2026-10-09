"""Export a MaxOCR font for use outside the harness: complete name table (family, style, unique ID,
full name, version, PostScript name, on the Windows and Mac platforms), so Windows Font Viewer and
installers accept it. Harness builds carry only family/style/copyright/licence names.

    python scripts/export_font.py SRC.ttf DST.ttf "MaxOCR 0O 5S" [--version 0.1]
    python scripts/export_font.py --all-in out/fonts        (rename in place; family from the file name)
"""
import argparse
import re
from pathlib import Path

from fontTools.ttLib import TTFont


def export(src: str, dst: str, family: str, version: str = "0.1") -> None:
    f = TTFont(src)
    style = "Regular"
    ps = re.sub(r"[^A-Za-z0-9-]", "", family.replace(" ", "-"))[:29] + "-" + style
    full = f"{family} {style}"
    names = {1: family, 2: style, 3: f"{version};MAXOCR;{ps}", 4: full, 5: f"Version {version}", 6: ps}
    nt = f["name"]
    for nid, s in names.items():
        nt.setName(s, nid, 3, 1, 0x409)
        nt.setName(s, nid, 1, 0, 0)
    f["head"].fontRevision = float(version)
    f["OS/2"].achVendID = "NONE"
    f.save(dst)
    # Read back: every required record present on the Windows platform.
    g = TTFont(dst)
    have = {n.nameID for n in g["name"].names if n.platformID == 3}
    assert {1, 2, 3, 4, 5, 6} <= have, have


def family_from_stem(stem: str) -> str:
    s = stem.replace("MaxOCR-", "").replace("current-after-", "after ").replace("current-", "").replace("_g1", "")
    return "MaxOCR " + s.replace("-", " ")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src", nargs="?")
    ap.add_argument("dst", nargs="?")
    ap.add_argument("family", nargs="?")
    ap.add_argument("--version", default="0.1")
    ap.add_argument("--all-in", help="export every MaxOCR-*.ttf in this folder in place, family from the file name")
    a = ap.parse_args()
    if a.all_in:
        for p in sorted(Path(a.all_in).glob("MaxOCR-*.ttf")):
            fam = family_from_stem(p.stem)
            export(str(p), str(p), fam, a.version)
            print(f"{p.name}: '{fam}'")
    else:
        export(a.src, a.dst, a.family, a.version)
        print(f"{a.dst}: '{a.family}'")


if __name__ == "__main__":
    main()
