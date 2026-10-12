"""Add the 32 ASCII punctuation marks to a MaxOCR font, each borrowed from an open-licence donor face (rebuilt at the
MaxOCR cap height by maxocr/blend.py, single-ingredient recipe; position and advance follow the donor relative to
its cap height, so a monospaced donor brings its wide cells).

    python scripts/add_punct.py SRC.ttf DST.ttf --donor courierprime
    python scripts/add_punct.py SRC.ttf DST.ttf --map '{"!": "courierprime", "#": "lora"}' [--donor cousine]
--map sets the donor per mark (JSON), --donor the rest. --best-of-survey uses each mark's best OFL face in
out/report/punct_survey_marks.csv (restricted to --families if given).
"""
import argparse
import json
import string
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from add_lowercase import add_glyphs  # noqa: E402
from maxocr.blend import CharRecipe, Ingredient, Recipe, build_font  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
PUNCT = string.punctuation


def survey_best(families: list[str] | None = None) -> dict[str, str]:
    m = pd.read_csv(ROOT / "out" / "report" / "punct_survey_marks.csv")
    m = m[m.licence == "ofl"].copy()
    m["family"] = m.face.str.replace(" (OFL)", "", regex=False)
    if families:
        m = m[m.family.isin(families)]
    best = m.sort_values("acc", ascending=False).groupby("mark").head(1)
    return dict(zip(best.mark, best.family))


def add_punct(src: str, dst: str, donor_of: dict[str, str]) -> str:
    path_of = {f["family"]: f["path"] for f in json.loads((ROOT / "out" / "ofl_faces.json").read_text())["faces"]}
    recipe = Recipe({c: CharRecipe([Ingredient(path_of[donor_of[c]], 1.0)]) for c in PUNCT}, name="MaxOCR punctuation")
    tmp = dst.replace(".ttf", "_punct_blend.ttf")
    build_font(recipe, tmp)
    return add_glyphs(src, tmp, PUNCT, dst)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("dst")
    ap.add_argument("--donor", default="courierprime")
    ap.add_argument("--map", default="{}")
    ap.add_argument("--best-of-survey", action="store_true")
    ap.add_argument("--families", help="comma-separated families allowed for --best-of-survey")
    a = ap.parse_args()
    donor_of = {c: a.donor for c in PUNCT}
    if a.best_of_survey:
        donor_of.update(survey_best(a.families.split(",") if a.families else None))
    donor_of.update(json.loads(a.map))
    print(json.dumps(donor_of))
    print(add_punct(a.src, a.dst, donor_of))


if __name__ == "__main__":
    main()
