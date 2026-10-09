#!/usr/bin/env bash
# Separate Iosevka copy for developing the MaxOCR parameter patch (rung 2). Does not touch worker copies.
set -e
W=~/maxocr-work/iosevka-fork
B=~/maxocr-work/iosevka
if [ ! -d "$W" ]; then
  mkdir "$W"
  for e in "$B"/* "$B"/.git "$B"/.gitignore; do
    n=$(basename "$e")
    case "$n" in .build|dist|private-build-plans.toml) continue;; esac
    if [ "$n" = node_modules ]; then cp -al "$e" "$W/$n"; else cp -a "$e" "$W/$n"; fi
  done
  rm -rf "$W"/packages/*/lib
fi
cd "$W/packages/font-glyphs/src"
python3 - <<'PY'
from pathlib import Path
z = Path("number/0.ptl"); s = z.read_text()
old = """		export : define [Shape top] : outlineT dispiro 0 0 top
		export : define [Mask top] : outlineT spiro-outline 1 1 top"""
new = """		# MaxOCR: horizontal inset of the zero's outline (font units), default 0.
		define inset : fallback para.maxocrZeroInset 0
		export : define [Shape top] : outlineT dispiro inset 0 top
		export : define [Mask top] : outlineT spiro-outline (inset + 1) 1 top"""
assert old in s or new in s; z.write_text(s.replace(old, new))
o = Path("letter/latin/o.ptl"); s = o.read_text()
old = """	create-glyph 'O' 'O' : glyph-proc
		include : MarkSet.capital
		include : OShape CAP 0 SB RightSB nothing ArchDepthA ArchDepthB"""
new = """	create-glyph 'O' 'O' : glyph-proc
		include : MarkSet.capital
		# MaxOCR: horizontal outset of the capital O (font units), default 0.
		local outset : fallback para.maxocrOOutset 0
		include : OShape CAP 0 (SB - outset) (RightSB + outset) nothing ArchDepthA ArchDepthB"""
assert old in s or new in s; o.write_text(s.replace(old, new))
PY
cd "$W"
grep -q maxocrZeroInset params/parameters.toml || sed -i 's/^onumZeroHeightRatio = 1.145/onumZeroHeightRatio = 1.145\n\n# MaxOCR fork parameters (rung 2). Defaults reproduce upstream Iosevka.\nmaxocrZeroInset = 0\nmaxocrOOutset = 0/' params/parameters.toml
git diff --stat
git diff > /mnt/c/Users/james.JAMESWORK2025/Repos/MaxOCR/iosevka/maxocr-params.patch
echo "patch saved"
