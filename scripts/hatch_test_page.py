"""Print test for lighter hatched underlines (James, 2026-10-22: "make 3 options for lighter hatches so we can test all
in a single scan"). Fonts from scripts/hatch_layer.py in out/check_page/MaxOCR-Hatch<V>.ttf; each version gets its own
pages: codes at 8 pt, numbers at 8 pt, codes at 10 pt, numbers at 10 pt (40 lines each, out/check_page/truth.json),
two columns. Printed to PDF with Edge.

    python scripts/hatch_test_page.py   -> out/check_page/hatch_page.html, out/print_test/MaxOCR_hatch_test.pdf
"""
import json
import os
import subprocess

VERSIONS = {"B": "current: line 15, gap 75", "C": "thinner: line 10, gap 75", "D": "sparser: line 15, gap 120",
            "E": "thinner and sparser: line 10, gap 110"}
EDGE = "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"


def main():
    truth = json.load(open("out/check_page/truth.json"))
    css = "".join(f"@font-face{{font-family:H{v};src:url(MaxOCR-Hatch{v}.ttf)}}\n" for v in VERSIONS)
    html = ['<!doctype html><html><head><meta charset="utf-8"><style>', css,
            "@page{size:Letter;margin:0.6in}body{color:#000;background:#fff;margin:0}"
            "h1,h2{font-family:Segoe UI,Arial,sans-serif;font-weight:600} h1{font-size:12pt;margin:0 0 6pt}"
            " h2{font-size:9pt;margin:10pt 0 3pt;break-after:avoid}.l{margin:0;line-height:1.7}"
            ".cols{column-count:2;column-gap:0.5in}.brk{break-before:page}</style></head><body>",
            "<h1>MaxOCR Hatch test: print at 100% (no scaling), scan at 600 dpi in colour or greyscale</h1>"]
    for i, (v, desc) in enumerate(VERSIONS.items()):
        html.append(f'<div class="cols{" brk" if i else ""}">')
        for size in (8, 10):
            for kind in ("codes", "numbers"):
                html.append(f"<h2>{v} ({desc}): {kind}, {size} pt</h2>")
                html += [f'<p class="l" style="font-family:H{v};font-size:{size}pt">{t}</p>' for t in truth[kind][:40]]
        html.append("</div>")
    html.append("</body></html>")
    open("out/check_page/hatch_page.html", "w", encoding="utf-8").write("".join(html))
    pdf = os.path.abspath("out/print_test/MaxOCR_hatch_test.pdf").replace("\\", "/")
    page = "file:///" + os.path.abspath("out/check_page/hatch_page.html").replace("\\", "/")
    prof = os.path.abspath("out/edge_profile").replace("\\", "/")
    subprocess.run([EDGE, "--headless", "--disable-gpu", f"--user-data-dir={prof}", "--no-pdf-header-footer",
                    f"--print-to-pdf={pdf}", page], check=True, timeout=120)
    print(pdf)


if __name__ == "__main__":
    main()
