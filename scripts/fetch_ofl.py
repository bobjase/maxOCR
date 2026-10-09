"""Download the OFL ingredient pool (upright default faces) from google/fonts at a pinned commit.

Files go to vendor/ofl/ (not committed); out/ofl_faces.json lists face, path and sha256.
All fonts here are SIL Open Font License, so blends of them may be released under the OFL.

    python scripts/fetch_ofl.py
"""
import hashlib
import json
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "vendor" / "ofl"
COMMIT_API = "https://api.github.com/repos/google/fonts/commits/main"
FAMILIES = [
    # serif
    "gelasio", "ebgaramond", "crimsonpro", "sourceserif4", "literata", "lora", "merriweather", "librebaskerville",
    "ptserif", "notoserif", "spectral", "alegreya", "cormorantgaramond", "vollkorn", "bitter", "caladea", "tinos",
    "ibmplexserif",
    # sans
    "robotoflex", "roboto", "opensans", "firasans", "sourcesans3", "inter", "worksans", "carlito", "arimo",
    "lato", "publicsans", "ibmplexsans",
    # designed for legibility
    "atkinsonhyperlegible", "andika", "lexend",
    # mono
    "cousine", "courierprime",
]


def get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "maxocr"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def pick(files: list[str]) -> str | None:
    """The upright default face: a variable font without 'Italic', else '-Regular'."""
    upright = [f for f in files if f.endswith(".ttf") and "Italic" not in f]
    for f in upright:
        if "[" in f:
            return f
    for f in upright:
        if f.endswith("-Regular.ttf"):
            return f
    return upright[0] if upright else None


def main():
    commit = json.loads(get(COMMIT_API))["sha"]
    DEST.mkdir(parents=True, exist_ok=True)
    out = []
    for fam in FAMILIES:
        try:
            listing = json.loads(get(f"https://api.github.com/repos/google/fonts/contents/ofl/{fam}?ref={commit}"))
            name = pick([x["name"] for x in listing])
            if name is None:
                print(f"{fam}: no upright ttf"); continue
            path = DEST / fam / name
            if not path.exists():
                path.parent.mkdir(exist_ok=True)
                path.write_bytes(get(f"https://raw.githubusercontent.com/google/fonts/{commit}/ofl/{fam}/{name}"))
            out.append({"family": fam, "file": name, "path": str(path),
                        "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
            print(f"ok {fam}: {name}")
        except Exception as e:
            print(f"{fam}: {e}")
    (ROOT / "out").mkdir(exist_ok=True)
    (ROOT / "out" / "ofl_faces.json").write_text(json.dumps({"commit": commit, "faces": out}, indent=1))
    print(f"{len(out)} faces from google/fonts@{commit[:10]}")


if __name__ == "__main__":
    main()
