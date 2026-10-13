# Decisions pending v0.4

The PRD (v0.3.1) is frozen until M1a exit. Deviations and clarifications made during M1a are logged here and folded into v0.4.

| Date | Ref | Decision | Rationale |
|---|---|---|---|
| 2026-10-08 | R0 | WSL Ubuntu 26.04 accepted instead of 24.04 | OS version does not affect results; engines and Python are pinned via pixi lockfile |
| 2026-10-08 | R0 | Environment via pixi (conda-forge): Python 3.12, Tesseract 5.5.3, Leptonica 1.87, Node 22, onnxruntime-gpu 1.30 | No sudo needed; lockfile satisfies R0 pinning; Node runs natively in WSL |
| 2026-10-08 | R16 | Tesseract pinned by conda package version + lockfile, not source commit | Equivalent reproducibility, far less build overhead; revisit only if a source build becomes necessary |
| 2026-10-08 | R11 | PP-OCRv6 medium run as the official ONNX export via onnxruntime CUDA, HF revision 50c7eac | Direct access to per-frame softmax; avoids paddlepaddle CUDA/Python coupling |
| 2026-10-08 | R11 | PaddleOCR output restricted to blank + corpus alphabet and renormalized | Mirrors Tesseract's whitelist (R12) so both engines choose from the same classes |
| 2026-10-08 | R11a | A CTC "run" is a maximal span of frames with the same non-blank argmax (standard greedy collapse), not any non-blank span between blanks | Adjacent distinct characters (e.g. `AB`) often have no blank between them; the PRD wording would merge them |
| 2026-10-08 | R12b | Rank computed after sorting ChoiceIterator alternatives by confidence | Measured: raw list order is non-monotonic in ~2% of symbols; chosen symbol is first in 100% |
| 2026-10-08 | R14 | Apple Vision omitted | No Mac available |
| 2026-10-08 | Sec. 7 | Severity is one dial s in [0, 1+] scaling all R5 operators together (`maxocr/degrade.py`); at s = 1 the blur, JPEG and dilation centre on the Section 7 placeholder, but every other operator is also active, so s = 1 is much harsher than the placeholder chain alone | Section 7 needs a single severity axis to sweep |
| 2026-10-08 | R29 | "No worse" means not statistically significantly worse (one-sided test), not a strict point-estimate comparison | With ~300 samples per character, a strict rule rejects good candidates on noise |
| 2026-10-08 | R11 (sizing) | Each engine's own input preprocessing is treated as part of the engine | Simplest faithful use of off-the-shelf engines |
| 2026-10-08 | Sec. 11 | OCR-B source: Matthew Skala's free OCR-B. Inter dropped from M1a | Free licence; Inter is proportional and complicates alignment for little go/no-go value |
| 2026-10-08 | R33 | Iosevka fork base: v34.9.0 | Latest stable release |
| 2026-10-08 | Sec. 7 | Operating point by relative rule (user decision); 2% absolute target replaced. **Superseded in procedure** by "Operating point procedure, corrected" below (first version interleaved font and severity choice). Final: s = 0.5, best baseline Source Code Pro | The 2% absolute target is unreachable: every font exceeds it at s=0 |

## Observations to carry into v0.4

- With DejaVu Sans Mono as a smoke-test font, the engines sit on very different error scales at the same severity: at s = 1.0, PaddleOCR ~4% vs Tesseract ~34% character error. Tesseract already makes ~6-9% errors on **clean** text (dominated by 0/O), independent of DPI. Section 7 step 3 ("1-5% on both engines") may have no solution; check with the real baseline fonts first.
- WSL is limited to 20 cores / 64 GB by `.wslconfig`; the PRD assumes 24 / 96. Affects R37b.

## M1a sweep findings (2026-10-08; 2,000 lines x 6 fonts x 2 suites per level; levels 0-0.5 by 0.1, 1.0, 1.5)

- Objective clusters (PaddleOCR, suite a, uncropped, s=0): {0,O,D} {8,B} {5,S} {2,Z} {1,I,L,6,G}. Stable under the R22b 2x check except the last, which splits into {1,I} and {6,G,L} at 2x.
- R22b fails for Tesseract: with ~9k samples per character, weak-but-consistent edges pass the Bonferroni test and chain 29 of 36 characters into one component. Edge rates decline smoothly (45% -> 0.6%), so there is no gap. Needs an effect-size floor; to be set in v0.4.
- Within-cluster substitution is already 2.8-12.7% (PaddleOCR) and 8.4-19% (Tesseract) at s=0. No baseline font reaches the Section 7 step 2 target of 2% at any severity. Section 7 as written has no solution.
- 0/O is close to a coin flip for both engines on every font, even fonts with a dotted or slashed zero; it dominates the off-diagonal mass.
- OCR-A is the worst baseline on both engines at low severity; OCR-B is mid-pack at s=0 and the most robust at s >= 1.0.
- Iosevka (advance 500 vs 600-723) degrades fastest; matched point size gives it physically smaller glyphs. Consider matching by advance width or cap height in v0.4.
- Above ~s=1.0 errors leave the clusters (unrelated misreads, deletions), so within-cluster rate falls; useful range is s <= ~0.6.
- Measured throughput: ~300 img/s end to end (24k images per level in 77-81 s), bottleneck PaddleOCR in the main process.

## Clean-condition check (R7a, 2026-10-08)

Undegraded renders (integer origin, no jitter, plain Otsu for suite a), same 2,000-line bank. Character error: PaddleOCR 1.1-5.0%, Tesseract 5.4-18%. The 0/O coin flip persists on clean input (e.g. PaddleOCR reads Iosevka's plain O as 0 in 49% of cases while reading its slashed zero correctly 95% of the time). The confusion is engine behaviour, not a harness artifact.

## R40b probe classifier (2026-10-08)

Small CNN (3 conv layers), 54k train / 10.8k test, middle glyph of 3-character strings, cropped stratum excluded, 3 seeds with the lowest-training-error seed kept (selection never uses test data). The table below used the provisional clusters (sweep, s=0, before the floors were added); `scripts/probe.py` now reads the final objective clusters, and the reference fonts are re-run with them.

| Font | Condition | Probe within-cluster % | PaddleOCR within-cluster % | Tesseract within-cluster % |
|---|---|---|---|---|
| Source Code Pro | clean | 0.000 | ~1 | ~5-7 |
| Source Code Pro | s=0.5 | 0.048 | 4.5 | 13.6 |
| IBM Plex Mono | s=0.5 | 0.072 | 5.5 | 14.7 |
| JetBrains Mono | s=0.5 | 0.121 | 7.2 | 16.4 |
| Iosevka | s=0.5 | 0.217 | 7.2 | 12.7 |
| OCR-A | s=0.5 | 0.000 | 17.4 | 22.0 |
| OCR-B | s=0.5 | 0.000 | 10.7 | 16.6 |
| Source Code Pro | s=1.0 | 3.329 | 11.1 | 9.7 |

- At the operating point every baseline font is separable almost perfectly by the probe, while the engines are 20-90x worse. Abort criterion 1 (best baseline within noise of the R40b estimate) does not fire: **go**.
- OCR-A and OCR-B, the worst fonts for the engines, are perfectly separable by the probe. Their engine errors are a mismatch between font and engine training, not visual ambiguity.
- The estimate is optimistic by construction (trains on the exact degradation distribution, single glyph cells).
- Seed check: one OCR-A seed diverged (11.8% train error) and was correctly discarded. "Diverged" means training error more than 1 pp above the best seed's.

## Cluster rule with floors (decided 2026-10-08)

R22b is kept (one-sided binomial vs uniform-error null, Bonferroni, alpha 0.01) and an edge c->d must also pass two floors (`maxocr/analysis.py`):
- **Share floor, 25%** (approved by James): d receives at least a quarter of c's errors. Without it, weak-but-consistent edges become significant at these sample sizes and chain most of the alphabet into one component (Tesseract at s=0; both engines at s=0.5).
- **Rate floor, 1%** (my call, same spirit, easy to reverse): the edge occurs in at least 1% of c's occurrences. The share floor alone admitted rare characters' dominant error (J->3 0.40%, 3->E 0.20%, 4->U/Y 0.24%), which still chained {0,O} and {8,B} with 3, E and J. Tesseract's gate edges are all >= 4.9%, so this only affects PaddleOCR.

Stability (R22b "2x either way") is reported with both floors halved and doubled. Applied identically to both engines.

**Final clusters, validation bank, s=0.5, suite (a), uncropped:**
- Objective (PaddleOCR): {0,8,B,D,E,O,Q} {6,G,L} {H,M,N} {1,I} {2,Z} {5,S} {9,A} {U,W}. At 2x floors the first splits into {0,D,O} and {8,B}; at 0.5x floors {U,W} gains V and {K,X} appears. The {0,O}-{8,B} link is real: PaddleOCR reads 0 as 8 in 10.2% of cases (dotted/slashed zeros).
- Gate (Tesseract): {1,3,9,I,J} {0,D,O} {2,Z} {4,A} {5,S} {6,G} {7,T} {8,B} {M,N} {V,Y}.

## Operating point procedure, corrected (2026-10-08)

My first implementation chose the best font first (averaged over severities) and then derived the severity from it, which interleaves the two steps PRD Section 7 keeps separate. Corrected order (`scripts/operating_point.py`, then `scripts/m1a_validation.py`):
1. Anchor font = lowest two-engine within-cluster rate at s=0 (provisional clusters from the sweep): **Iosevka**.
2. Lock severity = first swept s where the anchor's PaddleOCR within-cluster rate reaches 1.5x its s=0 rate: **s = 0.5** (unchanged).
3. Best baseline = lowest two-engine within-cluster rate AT s=0.5 on the validation bank with final clusters (PaddleOCR on objective, Tesseract on gate): **Source Code Pro 8.45%**, IBM Plex Mono 8.67%, OCR-B 9.38%, JetBrains Mono 9.46%, **Iosevka 11.04%**, OCR-A 12.52%.

The PRD's median-font anchor does not work with a relative rule: Tesseract's within-cluster rate barely grows below s=0.5 and then falls, so a two-engine median never reaches 1.5x, and a PaddleOCR-only median only gets there near s=1.0, where the metric no longer measures confusability.

**Iosevka, the font MaxOCR is built from, is 5th of 6 at the operating point.** Rung 0 must close ~2.6 points just to match the best baseline.

## R27b reliability curve (2026-10-08)

As written (per instance), the curve is degenerate: the R11a margin is read at the frame of the decoded run, so margin < 0 exactly when the instance is an error. Replaced with a per-glyph curve: median margin of each (font, character) over the validation bank vs that glyph's realized within-cluster error, with a weighted isotonic fit. All six fonts fall on one curve (the margin is font-independent as a predictor, which is what an optimization signal needs). Fitted error drops below 1% at a median margin of ~9.4 and to ~0 above ~11.3. Hinge (1.5x the first margin whose fitted error is under target): 14.2 for targets of 0.5% or 1%, 13.8 for 2% (`out/report/hinge.json`). Final hinge waits on the per-cluster targets (open question 1).

## Validation bank (R7)

5,000 lines, seed 202, sha256 `7644d190a6067344892df8551acf757a6434d6c40207fa6d91d8c6a6c9398fcb`, evaluated at s=0.5 for all 6 fonts x 2 suites (60k images, 205 s).

## Iosevka working copies (R33c) and build determinism (2026-10-08)

- First attempt hard-linked the whole checkout into each worker copy. A build compiles the glyph code into `packages/*/lib`, so 16 parallel first builds wrote into the same hard-linked files and corrupted them (`latin.mjs`: "Cannot read properties of undefined"). Fixed: only `node_modules` is hard-linked; everything else is copied, and `lib` is compiled per copy.
- The base checkout shared those files. It was cleaned and rebuilt; the rebuilt subset font is identical to the earlier baseline in every table and every glyph outline and advance. Only `head.created/modified` differ.
- Font file hashes are therefore not reproducible across builds (embedded timestamp). R45 comparisons must use font content (tables minus `head` timestamps), or builds must pin the timestamp (`SOURCE_DATE_EPOCH`, to be checked).

## Windows font survey (2026-10-08, approved by James)

Measurement only, PaddleOCR and Tesseract (PARSeq held out). 413 installed faces (25 monospaced) with all 36 primary characters, symbol fonts excluded, rendered at equal capital height (Source Code Pro at 8 pt), suite (a), clean (R7a) and s=0.5. Screening: 300 lines per face, cluster characters oversampled 3x (`scripts/font_survey.py`, `scripts/survey_analysis.py`). Fonts are read in place; only names and numbers are kept.

Screening (285 readable faces, mean character error < 15%):
- The O-to-0 width ratio is the strongest predictor of 0/O confusion (Spearman -0.82 among readable faces; -0.80 PaddleOCR clean, -0.47 Tesseract clean). Baselines sit at ~1.0-1.1; the best readable faces at 1.45-1.8.
- A dot or slash in the zero does not help (+0.13; none of the top 20 has one).
- Monospaced faces confuse 0/O about twice as often (PaddleOCR clean median 30% vs 15%, Mann-Whitney p ~1e-6).
- Short (old-style) zeros help somewhat (median 19% vs 26%).

Confirmation on a fresh 1,000-line bank (seed 707), same setup, top 20 readable + 3 Courier New + the 6 baselines (`scripts/survey_confirm_report.py`, `out/report/survey_confirm.csv`). 0/O pair confusion, pooled over both directions, Wilson 95% CI:

| Face | PaddleOCR clean | PaddleOCR s=0.5 | Tesseract clean | Tesseract s=0.5 |
|---|---|---|---|---|
| High Tower Text | 1.2 [0.5-3.1] | 4.6 [2.8-7.4] | 10.1 [7.3-13.8] | 9.5 [6.7-13.1] |
| Constantia | 4.3 [2.6-7.0] | 7.3 [5.0-10.7] | 12.2 [9.1-16.2] | 15.2 [11.8-19.5] |
| Book Antiqua | 2.7 [1.5-5.1] | 10.4 [7.5-14.1] | 26.5 [22.0-31.6] | 26.2 [21.8-31.2] |
| Courier New (best monospaced) | 16.8 [13.1-21.2] | 20.4 [16.4-25.1] | 35.1 [30.1-40.4] | 32.3 [27.5-37.6] |
| Source Code Pro (best baseline) | 22.6 [18.4-27.4] | 24.4 [20.1-29.3] | 49.7 [44.3-55.1] | 29.3 [24.6-34.4] |
| OCR-B | 44.8 [39.5-50.2] | 44.5 [39.2-49.9] | 44.8 [39.5-50.2] | 35.7 [30.7-41.0] |

- Confirmed: the best faces beat every baseline on 0/O with non-overlapping intervals on PaddleOCR (High Tower Text ~19x better than Source Code Pro clean).
- The two engines respond to different features. A wide O vs narrow 0 is enough for PaddleOCR (Book Antiqua, Garamond, Palatino: full-height zeros, 2.7-4.3% clean) but leaves Tesseract at ~26%. The faces that also do well on Tesseract (High Tower Text, Constantia, Corbel, MF Rinat: 10-20%) combine the wide O with a **short, old-style zero** (0 at 62-80% of cap height).
- Caveat for the basic-Latin expansion: a short zero approaches lowercase o. A short-zero design trades 0/O confusion for 0/o confusion once lowercase is in scope.

### All pairs (screening, 285 readable faces, `scripts/survey_pairs.py`)

Median pair confusion across readable faces (mean over engines and conditions): 0/O 25.3%, 5/S 12.4%, 1/I 8.8%, 8/B 4.0%, 9/I 2.8%, 6/G 1.9%, 4/A 1.9%, I/J 1.8%, 2/Z 1.4%; every other cluster pair is under 1% for the median face. Most of the objective-cluster pairs are problems of our baseline (programming/OCR) fonts rather than of fonts in general.

What separates the best faces from the worst (Spearman of generic shape features with pair confusion, plus the contact sheets in `out/report/survey_sheets/`, local only):
- **0/O**: width difference (-0.82) and overlap (+0.70): wide round O, narrow 0.
- **8/B**: width (-0.65) and ink (-0.60): a small or narrow 8 beside a wide B with a straight stem; worst are geometric sans faces where 8 and B have the same size and roundness.
- **5/S**: height (-0.47) and ink (-0.55): best are old-style 5s that drop below the baseline (Georgia, Constantia); worst are humanist sans and italics where 5 and S share curves.
- **1/I**: no generic feature predicts it; the sheet shows why: best faces give the 1 a flag and foot and the I full slab serifs (Cascadia, Consolas, Courier New, Verdana); worst are bare vertical bars (Gill Sans) where 1 and I are the same stroke. Monospaced faces do best on this pair: the fixed cell pushes the I to carry serifs.
- **I/J, O/Q**: height (-0.49, -0.47): a J or Q tail that descends below the baseline.
- General rule: confusable pairs are kept apart when their silhouettes differ in width, in vertical extent (above/below baseline), or by a distinctive appendage. Dots, slashes and other interior marks do not register. Screening only; per-pair results other than 0/O are not yet confirmed on a fresh bank.

Confirmation of 5/S, 1/I, 8/B (fresh 1,000-line bank, seed 808, top 10 readable faces per pair from screening plus the 6 baselines, equal capital height; `out/report/survey_confirm_pairs.csv`). Pair confusion %, pooled both directions, Wilson 95% CI:

| Pair | Engine, condition | Best upright faces | Iosevka (rung-0 parent) | Best baseline |
|---|---|---|---|---|
| 5/S | Tesseract clean | Georgia Bold 0.6 [0.2-2.0], Optima ExtraBlack 0.6 | 21.6 [17.7-26.1] | Source Code Pro 8.6 |
| 5/S | Tesseract s=0.5 | Georgia 8.0 [5.7-11.3] | 22.7 [18.7-27.3] | OCR-B 19.4 |
| 8/B | PaddleOCR s=0.5 | Bell MT, Bookman Old Style Bold 0.0 [0.0-1.2] | 8.6 [6.0-12.1] | Source Code Pro 1.8 |
| 8/B | Tesseract s=0.5 | MF Rinat 0.6 [0.2-2.2], Bookman Old Style Bold 1.5 | 13.8 [10.4-17.9] | OCR-A 9.5 |
| 1/I | Tesseract clean | Bookman Old Style Bold 1.2 [0.5-3.0], Cascadia 2.9 | 9.7 [7.0-13.4] | Source Code Pro 2.9 |
| 1/I | Tesseract s=0.5 | Courier New Bold 5.6 [3.6-8.6] | 12.7 [9.6-16.7] | Source Code Pro 6.2 |

- 5/S and 8/B: confirmed; the best faces beat every baseline, by the widest margin on Tesseract.
- 1/I: the best faces only match the best programming-font baselines (flagged 1, serifed I), which already handle this pair; Iosevka, OCR-A and OCR-B do not. The lesson for MaxOCR is to adopt that shape, not to look beyond it.
- On clean input PaddleOCR is near 0% for these pairs on almost every face; the differences appear under degradation and on Tesseract.
- Italic faces appear among the winners (Bell MT Italic, Georgia Bold Italic); MaxOCR is upright, so only upright faces are cited as design references.

## Iosevka levers for the survey lessons (2026-10-08, `scripts/iosevka_variants.py`)

Built-in variants of v34.9.0 for the confusable characters were built (one build per variant index, all characters at once) and inspected (`out/report/iosevka_variants.png`, `.csv`).

**Rung-0 shortlist (built-in variants that implement a survey lesson):**
- 1/I: `one = base-flat-top-serif` or `base-long-top-serif` (flag and foot) with `capital-i = serifed`: the Cascadia/Consolas/Courier shape that wins 1/I.
- 0/O: `zero = diamond-*`: the only zero body that changes the outline (standard and oval bodies are the O's shape; dots and slashes are interior marks, which the survey shows the engines ignore).
- 8/B: `capital-b = standard-bilateral-serifed` (straight stem with serifs, Bookman-like) or `more-asymmetric-interrupted-*`; `eight = crossing-asymmetric`.
- 5/S: `capital-s = bilateral-serifed` (serifed terminals the 5 lacks); `five` variants differ little.
- I/J: `capital-j = descending-*` (tail below the baseline). O/Q: `capital-q` tail styles (`detached-tailed`, `crossing`).

**Not reachable with variants or spacing (needs rung 2, i.e. forked shape parameters):**
- **O wider than 0**, the strongest 0/O lever. Iosevka draws both 0 and O between the same sidebearing lines (`SB`..`RightSB`; `number/0.ptl`, `letter/latin/o.ptl`), so their ink widths are identical (388 units) for every zero variant. Quasi-proportional spacing does not change them (it narrows I and widens M/W only). The fork is small: `ZeroShapeBase` already takes a horizontal inset (`offsetX`) for the zero, and the O needs a matching outset; Q reuses the O shape and must follow.
- A 5 that descends below the baseline; a short (old-style) zero; a smaller 8.

**Spec conflict to resolve in v0.4:** R2a sets the ink-box tolerance from the 95th percentile of the rung-0 variant set. No variant widens the O, so R2a as written forbids the single most effective change found by the survey. A monospaced cell still has room: at advance 500 the O's ink can grow from 388 toward ~460 and the 0 can narrow toward ~300 (ratio ~1.5; Courier New achieves 1.33 inside a fixed cell). Proposal: set R2a per glyph from the advance minus a minimum sidebearing, not from the rung-0 distribution.

## M2 rung 0: implementation decisions (2026-10-08, `scripts/rung0.py`, `maxocr/invariants.py`, `maxocr/build.py`)

- **R2c invariants implemented** (`maxocr/invariants.py`): per primary character, advance equal to the parent's; ink box within the R2a tolerance; ink area >= 85% of the parent's, rasterized at 1 px per font unit (robust to overlapping contours); every contour simple (shapely, curves flattened). Tested: the parent passes against itself; Source Code Pro fails on advances.
- **R2a tolerance** from the full rung-0 variant set: every single-cluster move relative to the parent is pre-built; per glyph, nearest-rank 95th percentile of each box side (a glyph with few variants keeps its extremes).
- **R2b applied literally at rung 0.** It rejects some designer variants: unslashed zeros (Iosevka's default zero is slashed, so removing the slash drops ink to ~81%), the bare-stroke 1 and the serifless I. R2b exists to stop stroke thinning; these are missing marks, not thinner strokes. Kept literal because the survey says slashes do not help and 1/I wants serifs anyway; revisit if needed.
- **Search shape:** clusters with at most 200 variant combinations are searched exhaustively ({1,I} 27, {5,S} 60, {9,A} 30, {2,Z} 108); larger ones ({0,8,B,D,E,O,Q}, {6,G,L}, {H,M,N}, {U,W}) by coordinate ascent within the cluster (one member character per candidate, up to 3 rounds). R32's "a few hundred combinations per cluster" does not hold for Iosevka v34 (e.g. 85k for the 0/O cluster).
- **Objective (R27):** mean over objective-cluster occurrences (uncropped) of min(margin, hinge), hinge 14.17 (R27b, 1% target); a deletion scores -hinge. Optimization bank: 500 lines, seed 909, objective-cluster characters oversampled 3x (R19 controlled frequency), suite (a), s=0.5.
- **Acceptance:** the best-ranked candidate must beat the current elite on the same lines (paired one-sided t-test over per-line mean objective, p < 0.05), otherwise the elite stands. Prevents chasing noise.
- **Gate (R28):** Tesseract within-gate-cluster substitution rate not significantly worse than the elite's (one-sided two-proportion z, p < 0.05) on suites (a) and (b). The measured substitution rate is used instead of the rank margin, which R12b already states is only a lower bound.
- **Clean floor (R29):** per primary character, on a 2,000-line clean bank (seed 303, ~310 occurrences per character), both engines, both suites: one-sided Fisher exact test against the parent, fail at p < 0.01.
- **Stopping (R35):** a full sweep with no accepted change is a fixed point (the greedy space is exhausted); otherwise at most 5 sweeps. Elite validated on the validation bank after each sweep.
- **Joint step:** weight shape 360-460 in steps of 20 with the final variant set, subject to R2c; chosen on the optimization bank, reported on the validation bank.
- **R30 (shape-distance ceiling)** is not enforced at rung 0: the PRD gives no ceiling value, and rung-0 shapes are designer variants. To be set before rung 2.

- **Incidents during the first rung-0 launch (fixed):** (1) the invariant cache was smaller than the variant set, so computing the tolerance re-measured every font once per glyph (~2.8 h instead of seconds); measurement is now cached without bound, done once per font, and rasterized at 1/4 px per unit (ink areas agree within 0.02%, 445 fonts in 12 s). (2) The R2a percentile was taken over all fonts rather than over each glyph's distinct shapes; since ~430 of 443 fonts carry the default glyph for any given character, the tolerance collapsed to the default box and rejected 40% of candidates (mostly serifed letters). With distinct shapes the rejection rate is 9% (42 of 444), all R2b ink area, under R31's 20% review threshold. No candidate had been accepted under the faulty tolerance; search state was reset, builds and scores kept. (3) `kill_workers.sh` missed drivers started as plain `python scripts/...` (a stale run kept going alongside its restart until killed by PID); it now matches drivers by script location, anchored to the start of the command line.

## Direction change: amalgam fonts instead of a single parent (2026-10-08, owner direction)

James judged a single parent font (Iosevka) too limiting for an idealized font and proposed building each glyph as a weighted mix of several fonts. Implemented (`maxocr/blend.py`): each ingredient glyph is normalized to a common box and the shapes are blended as weighted signed distance fields; geometry (ink width and height, baseline offset, sidebearing, advance, in cap-height units) is blended separately; tiny debris is removed; the result is traced to TrueType outlines and assembled with fontTools FontBuilder (cap height 700/1000). Ingredients: 35 OFL families from google/fonts at commit 2eb0b48d5f (`scripts/fetch_ofl.py`), so blends can be released under the OFL.

Findings:
- A single-ingredient recipe reproduces its source font; serif+serif blends are clean; serif+sans blends leave partial-serif debris, so blends are made within one style.
- OFL ingredient survey (35 faces, `out/survey_ofl/`, seed 1001): serif faces lead (Gelasio, Cormorant Garamond, Spectral, Source Serif 4).
- **First amalgam experiment** (`scripts/amalgam.py`): per character, the 3 best ingredients of one style, weighted by 1/(error + 0.005). Validation bank, s=0.5, suite (a), rung-0 metrics:

| Font | PaddleOCR within objective % | Tesseract within gate % | PaddleOCR 0/O % | Char error % |
|---|---|---|---|---|
| Serif amalgam top-3 blend | 1.23 | 6.97 | 7.51 | 5.56 |
| Serif amalgam best glyph per char | 1.51 | 6.91 | 7.59 | 6.49 |
| Sans amalgam top-3 blend | 1.59 | 9.23 | 13.12 | 6.56 |
| Spectral (best single OFL serif) | 2.79 | 8.65 | 14.47 | 8.10 |
| Source Code Pro (best baseline) | 3.59 | 13.32 | 25.30 | 10.16 |
| Iosevka rung-0 elite (partial sweep 1) | 4.84 | 14.25 | 31.70 | 16.87 |

- **Matched capital height** (`scripts/amalgam_fair.py`, all at Source Code Pro's cap height): serif amalgam 1.57 / 7.93 / 8.85 / 6.62 vs Source Code Pro 3.59 / 13.32 / 25.30 / 10.16. The advantage holds (-56% PaddleOCR, -40% Tesseract). Proportional glyphs are wider, so lines are longer at equal cap height.
- Tesseract 0/O stays at ~34% in every font tried; the amalgam fixes PaddleOCR's 0/O, not Tesseract's.
- Visually, the top-3 blend reads as one coherent serif; "best glyph per character" looks patched together (a hairline O from Cormorant Garamond beside heavier glyphs). Blending is what makes it a font.
- **Iosevka rung 0 paused** after sweep 1 reached 1/I (resumable from `out/rung0/run.db`). Accepted so far: zero oval-dotted, capital-d more-rounded-bilateral-serifed, capital-b standard-bilateral-serifed, capital-g toothed-serifless-capped; objective 7.76 -> 8.16. It stays as the monospaced reference.

Spec impact (to be drafted as v0.5): the parent becomes an ingredient pool; R2 (fixed advance per glyph) and R32-R33 (Iosevka variant and PatEL search) are replaced by per-glyph blend weights and geometry knobs; R2a/R2b/R2c need amalgam equivalents (consistency of stroke weight and cap height, outline validity); R47 release becomes an OFL blend with recipe.

### Amalgam rung 2, first run: cluster {0,8,B,D,E,O,Q} (2026-10-08, `scripts/amalgam_opt.py`)

CMA-ES, 25 generations x 16, 63 parameters (per glyph: softmax weights over its 5 best serif ingredients, width, height, baseline shift, stroke offset); start P0 = serif top-3 amalgam. Accepted at generations 1 and 6 (both improved Tesseract as well). Validation bank: PaddleOCR within-objective 1.23% -> **1.03%**, Tesseract within-gate 6.97% -> **6.45%**, objective 11.35 -> 11.48.

What changed (`out/report/amalgam_opt_08BDEOQ.md`): 0 narrower (x0.92) and taller (x1.07); O mostly Libre Baskerville (wide, round); 8 drops below the baseline (-0.095 cap) and is lighter; D wider (x1.14); B, D, E, O heavier (+0.46 to +0.76 stroke).

Lessons for the optimizer:
- Generations 20-24 each found a candidate with a significantly better PaddleOCR objective that failed the clean floor on Tesseract's 8 (clean accuracy 89.6% -> 72-82%). CMA-ES sees only the objective, so its distribution drifted into a region the gate rejects. Constraints should enter the fitness as penalties (R31's "penalty with repair"), not only as an acceptance filter.
- Stroke weights drifted apart (capitals heavier than digits): a stroke-consistency constraint is needed.
- PaddleOCR is near its ceiling on this cluster (1.0%); Tesseract (6.5%) is the larger remaining error but is only a gate (R28). Whether Tesseract should enter the objective is a spec question for James.

## Held-out engine: PARSeq (2026-10-08, `maxocr/engines/parseq.py`, `scripts/parseq_eval.py`)

PARSeq base, repo commit 1902db04 (`baudm/parseq`), weights `parseq-bb5792a6.pt` sha256 bb5792a68e367476abca029cbf8699abc805f3d3dc7e57aae45c8ec4f7b7cd00; non-autoregressive decode, no refinement; output restricted to the corpus alphabet; each image resized to 32x128 independently. Never used for any selection. Validation bank, s=0.5, suite (a), uncropped, every font at Source Code Pro's cap height:

| Font | within objective % (all / len 1 / len 8+) | char error % (all) | 0/O pair % |
|---|---|---|---|
| Amalgam optimized (0/O cluster) | 6.12 / 0.40 / 6.88 | 5.31 | 30.1 |
| Amalgam P0 (serif top-3) | 6.54 / 0.80 / 7.31 | 5.46 | 33.8 |
| Amalgam sans top-3 | 6.19 / 0.60 / 7.04 | 4.57 | 30.6 |
| Spectral (best single OFL serif) | 7.78 / 5.43 / 8.54 | 7.14 | 34.1 |
| Source Code Pro (best baseline) | 8.61 / 7.44 / 9.60 | 7.25 | 34.0 |
| Iosevka (baseline) | 13.35 / 12.68 / 14.29 | 13.32 | 28.0 |

- The amalgam's gains transfer to the held-out engine (-29% within-cluster vs the best baseline), and the PaddleOCR-driven optimization step transferred too (6.54 -> 6.12).
- Length 1 (R13b's cleanest test): 0.40% vs 7.44%. Transfer criterion (Section 7.5, headroom closed on PARSeq >= 50% of that closed on PaddleOCR, PARSeq floor approximated by the probe estimate): length 1 passes (~95% closed); length 8+ ~28% closed vs ~72% on PaddleOCR, ratio ~0.4, **does not pass**. PARSeq's internal language model on long strings is the likely reason (R13b caveat).
- 0/O stays ~30% on PARSeq for every font, as on Tesseract: only PaddleOCR's 0/O is fixed by the amalgam.

## Discovery direction (owner feedback, 2026-10-08)

James: blending tweaks existing fonts and finds a local best, "a good first step", but has no discovery or mutation. Plan: glyphs as skeletons (centerline strokes) plus a stroke profile; mutation operators on geometry (move, bend, angle, curvature, thickness, contrast) and structure (add/remove spur, serif, crossbar, tail, notch, flat side, gap; open/close/join/split strokes); quality-diversity search (MAP-Elites) that keeps the best design per kind of shape; seeds from amalgam skeletons and from primitives. Guards against engine-fooling: PARSeq transfer, degradation in the loop, R40c pixel distance, probe classifier, minimum feature size, human study. First target: 0/O, still ~30% on PARSeq and Tesseract.

### Discovery run 1: reward hacking (2026-10-08)

The first MAP-Elites run (2,025 evaluations) reported 0/O confusion falling to 0% on both engines. It was reward hacking: the fitness only penalized 0<->O swaps and substitutions within clusters, so the search made the O read as **C** (PaddleOCR 92%, Tesseract 72%) and the 0 as deleted, 1, 4 or I. Correct reads fell to ~0-5% (base: 0 90.7%, O 93.7% on PaddleOCR; 61.1% / 74.0% on Tesseract) and overall character error rose to 22% / 29% (base 2.2% / 12.3%). Outputs kept in `out/discover/0O_reward_hacked/` as a record.

Fixes:
- Discovery fitness now rewards reading each pair glyph **correctly** (mean accuracy over both engines) and penalizes any rise in overall character error above the base font (x2).
- Validation reports per-glyph accuracy and overall character error on all three engines, not just the pair rate.
- **R27 has the same loophole in milder form**: the margin is taken against the strongest *in-cluster* rival, so a glyph drifting toward an unrelated class keeps a good margin while being misread. `paddle_margin(..., any_class=True)` measures against the strongest rival of any class; the amalgam optimizer uses it from now on. The earlier amalgam results are not affected in practice (overall character error fell on all three engines), but v0.5 should define R27 against any class.

### Discovery run 2 (correctness fitness): real Tesseract gains, mixed transfer (2026-10-08)

MAP-Elites, 2,026 evaluations, 26 cells; fitness = mean correct-read accuracy of 0 and O on PaddleOCR and Tesseract minus 2x any rise in overall error. The search rediscovered the survey's lesson (small, short, slightly slanted 0 next to a heavier round O) and added new features (spurs/nicks on the 0, an inner hook on the O). Validation bank, 5,000 lines, s=0.5 (`out/discover/0O/validation.csv`):

| | R40c pixel distance | PaddleOCR 0/O correct % | Tesseract 0/O correct % | PARSeq (held out) 0/O correct % | Tesseract clean pair acc % |
|---|---|---|---|---|---|
| Base (optimized amalgam) | 0.180 | 94.0 / 94.9 | 55.4 / 73.7 | 52.6 / 80.8 | 64.1 |
| #1 | 0.191 | 96.2 / 95.6 | 71.5 / 78.4 | 48.4 / 83.7 | 83.1 |
| #4 | 0.191 | 94.5 / 97.1 | 69.6 / 80.2 | 46.8 / 84.8 | 86.0 |
| #6 | 0.190 | 97.3 / 98.1 | 51.7 / 83.0 | 54.3 / 82.7 | 70.6 |
| #8 | 0.174 | 96.2 / 96.2 | 52.3 / 74.3 | 55.6 / 84.4 | 67.3 |

- Real: Tesseract 0 accuracy +16 points, clean pair accuracy +19 points, overall Tesseract error 10.1% -> 9.6%; pixel distance up, so the glyphs are genuinely more different.
- Mixed transfer: the family that helps Tesseract most lowers PARSeq's 0 accuracy by 4-6 points; another family helps PARSeq but not Tesseract's 0. No design improves 0 on all three engines yet. Part of the gain is engine-specific; the likeliest carriers are the tiny spurs/nicks on the 0.
- Next: a third optimizing engine (EasyOCR, R15) so designs must satisfy three architectures, PARSeq still held out; a minimum feature size so sub-legible marks cannot score.

## Context decides 0 vs O for three of four engines (2026-10-08, isolation tests suggested by James)

Isolation bank (`scripts/discover_pair.isolation_bank`, `scripts/isolation_eval.py`): each target alone, and in the middle of 6 neighbours that are mixed (3 letters + 3 digits, shuffled, e.g. 4K?TWX7), all letters, or all digits; neighbours never come from the target's clusters, so there is no comparison partner. s=0.5, suite (a), 30 lines per cell.

- **Adversarial context wins on EasyOCR, PARSeq and Tesseract for every font tested**: a 0 among letters is read as O (0-10% correct) and an O among digits as 0 (0% correct). Fonts: amalgam, Source Code Pro, run-2 discoveries, and zero styles slashed (Iosevka, Consolas, Atkinson Hyperlegible), dotted (Cascadia Mono, JetBrains Mono), plain (Courier New, OCR-A). Slashed zeros do not help and Iosevka's is the worst. PaddleOCR is the only engine that mostly reads shape (amalgam: 0 among letters 77%, O among digits 70%, the only non-zero O-among-digits result of any font).
- **A lone round glyph defaults to "0"** on EasyOCR, PaddleOCR and Tesseract (amalgam's lone O: 0%, 17%, 30%).
- **Mixed context** (no letter/digit prior) is where shape shows: amalgam 0/O correct 37/90 (EasyOCR), 100/100 (PaddleOCR), 73/83 (PARSeq), 70/53 (Tesseract) vs Source Code Pro 60/67, 100/37, 50/37, 40/43.
- Implication: for context-driven recognizers, 0/O in random alphanumeric codes is limited by the engine's prior, not only by glyph shape. Discovery run 3 tests whether any shape can override the prior (fitness: single, mixed and adversarial contexts on PaddleOCR, Tesseract and EasyOCR; minimum feature size 0.10 cap; PARSeq held out). If none can, the practical levers are format rules (e.g. codes that exclude O, as VINs do) or engine-side constraints, and the font's contribution is the mixed-context and PaddleOCR-class gains.

### High-contrast and italic zeros (2026-10-08, James's example)

Isolation test of high-contrast and italic faces (Bodoni MT and Bodoni MT Italic, Bell MT Italic, Goudy Old Style Italic, Perpetua Italic, Times New Roman Italic; `out/report/isolation_italic_styles.csv`): none overcomes the context prior (0 among letters 0-3% on EasyOCR and PARSeq, 0-13% on Tesseract; O among digits 0-37% on every engine), and in mixed context they are mostly worse than the upright amalgam (O on PaddleOCR / PARSeq: Bodoni Italic 23 / 43% vs amalgam 100 / 83%). Contrast and stress still enter the discovery search space: new `stress` (rotate a counter) and `contrast` (anisotropic counter scale) operators, and OFL high-contrast seeds (Bodoni Moda, Playfair Display, Libre Bodoni).

### Discovery run 3 and feature transplants (2026-10-08)

Discovery run 3 (isolation fitness: single, mixed and adversarial contexts; PaddleOCR, Tesseract, EasyOCR; 2,026 evaluations, 34 archive cells). Best fitness 0.556 (start) to 0.626. The top designs make the O much wider than the 0 (width ratio 1.4-2.4) and add small hooks or spurs to both.

Feature transplants from fonts James tried on "BO0K" (`scripts/feature_transplant.py`): each idea is put into the optimized amalgam, changing only the 0 and/or the O, so the test measures the idea rather than a whole different font. Ideas: stencil gaps, script entry curl on the O, short old-style 0, squared (superellipse) 0 or O, white 0 on a black disk, blackletter faceted 0 (normal and short). Not tested: rough outlines (noise, not a feature) and number names written inside digits (about 3 px tall at 8 pt/200 dpi, so they blur into a dot; at large sizes they would be read as extra text).

Isolation test, s=0.5, suite (a), 30 trials per cell (`out/report/isolation_transplant.csv`, compact view `scratch/summarize_iso.py`). Mean over the four engines of six cells (0 and O: alone, mixed line, adversarial neighbours):

| Font | 0 among letters | O among digits | O alone | Average of six |
|---|---|---|---|---|
| amalgam (control) | 21 | 19 | 32 | 52 |
| discovery run 3 #1 / #2 / #3 | 12 / 22 / 20 | 32 / 29 / 25 | 58 / 57 / 53 | 59 / 59 / 58 |
| short old-style 0 | **35** | 19 | 32 | 49 |
| stencil 0, stencil O + 0 | 22 | 19 / 18 | 32 / 33 | 49 |
| curl O (script) | 21 | 12 | 33 | 51 |
| squared 0 / squared O | 5 / 21 | 19 / 13 | 32 / 6 | 44 / 45 |
| faceted 0 / faceted short 0 | 8 / 19 | 19 | 32 | 44 / 41 |
| white 0 on black disk | 1 | 19 | 32 | 36 |

- Only the short 0 moves the hardest cell (0 among letters): Tesseract 7 to 50%, PaddleOCR 77 to 90%; EasyOCR and PARSeq stay at 0%. It costs the lone 0 (PARSeq 83 to 30%, Tesseract 77 to 50%), and it will collide with lowercase o in the basic-Latin phase. A height dial (0.70, 0.78, 0.86 cap; on the control and on run 3 #2) is queued to find out whether a milder shortening keeps the gain without the cost.
- Marking the O with a script curl does nothing at this size; discovery's gains on the O come from width.
- The inverted, squared and faceted zeros are read worse as zeros (engines don't map them to 0).
- Discovery run 3 #4 shows why PARSeq is held out: its lone 0 drops to 0% on PARSeq while the three optimizing engines are fine.
- EasyOCR: 0% in both adversarial cells for every font so far. No shape tested overrides its context prior.

Ordinary lines (validation bank, 5,000 random lines, s=0.5, suite (a), uncropped; `out/report/validation_transplant.csv`). 0/O pair confusion, % of 0 and O occurrences read as the other:

| Font | PaddleOCR | Tesseract | EasyOCR | PARSeq (held out) | 0 read correctly, mean of 4 | O read correctly, mean of 4 |
|---|---|---|---|---|---|---|
| amalgam (control) | 5.5 | 29.6 | 42.5 | 30.9 | 54.8 | 85.0 |
| short old-style 0 (0.70) | **3.3** | **12.7** | **31.2** | 30.0 | 51.4 | 84.6 |
| discovery run 3 #1 / #2 / #3 | 6.6 / 3.9 / 4.0 | 28.0 / 31.1 / 32.2 | 43.2 / 42.5 / 43.2 | 29.4 / 24.0 / 27.1 | 48.8 / 51.8 / 52.9 | **92.0** / 88.9 / 88.8 |
| discovery run 3 #4 | 4.3 | 17.9 | 36.0 | 19.4 | 62.5 | 87.7 |
| faceted short 0 | 4.1 | 11.7 | 24.3 | 27.9 | 37.7 | 84.6 |
| white 0 on black disk | 30.1 | 30.5 | 40.6 | 39.7 | 25.5 | 84.7 |

- The short 0 halves Tesseract's 0/O confusion in ordinary lines and cuts EasyOCR's by a quarter; Tesseract's clean accuracy on the pair rises 64 to 81%. PARSeq's confusion is unchanged, but it reads the short 0 correctly less often (53 to 38%; the misreads go to characters other than O).
- A low pair rate alone can mislead: the faceted short 0 has the lowest pair confusion but the 0 is read correctly only 38% of the time.
- Discovery run 3 #4: the best ordinary-line numbers on PARSeq, but 0% for a lone 0 on PARSeq and the lowest R40c pixel distance (0.152 vs 0.180), so its 0 and O are more alike in pixels. Treat it as suspect (engine-specific cues).
- Overall character error (mean of the four engines; control 8.1%) is within 0.2 points for every font except the inverted 0 (9.0), the faceted short 0 (8.6) and the squared 0 (8.5).

Short-0 height dial (isolation test, `out/report/isolation_dial.csv`): on the control, height 0.78 keeps most of Tesseract's gain for a 0 among letters (47% vs 50% at 0.70 and 7% at full height) and halves the cost for a lone 0 (PARSeq 53% vs 30% at 0.70, 83% at full height); at 0.86 the gain is gone (17%). On run 3 #2 the short 0 gives no gain (0-7% among letters on Tesseract at every height): the two ideas don't stack in that combination. Risk to keep in view: an engine allowed to output lowercase will likely read a short 0 as o (context check, open question 2).

Discovery run 4: resumes from run 3's 34 elites plus the original seeds, each also with the 0 at 0.78 height (`--resume`, `--short-zero 0.78`, output `out/discover/0O_run4`).

**The short 0's gain is mostly an artifact of the restricted alphabet** (`scratch/lowercase_risk.py`). PARSeq allowed to output any of its 94 characters, isolation-bank 0s (30 each):

| 0 design | alone: read as 0 / o | among letters: read as O / o |
|---|---|---|
| full height (control) | 25 / 0 | 29 / 0 |
| 0.70 height | 5 / 13 | 3 / 27 |
| 0.78 height | 13 / 9 | 8 / 22 |
| 0.86 height | 18 / 7 | 27 / 3 |

Among letters the engine still reads a letter, now lowercase o. With the output limited to 0-9A-Z, the o reading is masked and the choice falls between O and 0, which is where the measured gain came from. If downstream software upper-cases (common for codes), o becomes O and the error is back.

Discovery run 4 result (2,013 evaluations, 36 cells, best fitness 0.658 vs run 3's 0.626; every elite descends from the Libre Baskerville seed). Isolation test (`out/report/isolation_run4.csv`, mean of four engines, average of six cells): control 52, run 4 #1-#4 52-58, **run 4 #5 61** (best so far; PARSeq 64 vs control 54; PARSeq lone 0 / mixed 93 / 87%; PaddleOCR 0 among letters 97%). Run 4 #1, #3 and #4 collapse on the held-out PARSeq (lone 0 at 0-3%): their 0s carry detached specks (pieces of 0.05-0.19 of the main body's area, outside its box) that the 0-9A-Z whitelist makes free. Fix: debris rule in `maxocr/strokes.py` (`drop_debris`: pieces under 0.4x the largest must lie inside the body's box); stencil-style halves are kept.

Run 4 follow-up checks:
- Unrestricted PARSeq (`scratch/lowercase_risk.py`) reads run 4 #1, #3 and #4 at the wrong length (27-30 of 30): the specks become extra characters. Run 4 #2 (short-0 lineage) is read as o. Run 4 #5 (clean): 0 alone 27/30, in a mixed line 26/30, among letters 4/30 (control 25, 22, 0).
- Case-folded isolation test (`out/report/isolation_casefold.csv`; PaddleOCR, EasyOCR and PARSeq read printable ASCII and fold case, Tesseract keeps its whitelist): the short 0 drops below the control (average of six cells 39 at 0.70 height and 44 at 0.78, vs control 52; PaddleOCR reads it as o, so 0 in a mixed line falls from 100 to 7%). Run 4 #5 stays at 61 (PaddleOCR 96, PARSeq 64).
- Ordinary lines (`out/report/validation_run4.csv`): run 4 #5 cuts 0/O confusion on PaddleOCR (5.5 to 1.7%) and PARSeq (30.9 to 21.0%), leaves EasyOCR unchanged (42.5%) and Tesseract's flat (29.9%), with its 0 read correctly less often on Tesseract (55 to 42%). R40c pixel distance 0.197 vs 0.180, so the gain comes from more distinct shapes. Overall character error 8.0 vs 8.1%.
- Best 0/O design after run 4: run 4 #5 (`~/maxocr-work/keep/0O_run4_5.ttf`).

Discovery run 5 result (2,001 evaluations, 37 cells, best fitness 0.659 under the stricter rules). Checks with case-folded reading (`out/report/isolation_0O_run5.csv`, `out/report/validation_0O_run5.csv`, lowercase check in `~/maxocr-work/logs/0O_run5_lower.out`):

| | control | run 4 #5 | **run 5 #1** |
|---|---|---|---|
| isolation, average of six cells, four engines | 52 | 61 | **63** |
| isolation, PARSeq (held out) | 54 | 64 | **67** |
| ordinary lines, 0/O pair: PaddleOCR / Tesseract / EasyOCR / PARSeq | 5.2 / 29.6 / 43.0 / 30.9 | 1.5 / 29.9 / 42.2 / 20.8 | 2.3 / 24.6 / 41.1 / 21.6 |
| ordinary lines, Tesseract 0 read correctly | 55 | 42 | 54 |
| R40c pixel distance | 0.180 | 0.197 | 0.217 |
| overall character error, mean of four | 8.2 | 8.1 | 8.1 |
| unrestricted PARSeq, 0 in a mixed line | 22/30 | 26/30 | 30/30 |

- **Current best 0/O design: run 5 #1** (`~/maxocr-work/keep/0O_run5_1.ttf`, copy in `out/fonts/MaxOCR-0O-run5-1.ttf`): a tall narrow 0 with a heavy left side and a small flare at top left; a wide O. Specimen `out/discover/0O_run5/best_specimen.png`.
- Run 5 #4 is run 4 #4 carried over: its marks are attached to the 0 (or inside its box), so the debris rule keeps them, and PARSeq still reads them as extra characters. The optimizing engines don't penalize this (PaddleOCR and EasyOCR ignore the marks, Tesseract's whitelist has no punctuation). Possible guard for later runs: Tesseract without a whitelist as an extra fitness engine, so a mark read as punctuation costs a length error.
- EasyOCR: still 0% for a 0 among letters and 0-7% for an O among digits, for every design.

### Next pairs (2026-10-09)

Confusion ranking of the current font (run 4 #5; differs from run 5 #1 only in 0/O), validation bank, s=0.5, suite (a), uncropped, case-folded reading (`scripts/confusions.py`, `out/report/confusions_run4_5.csv`). Unordered pair rate, % of the pair's occurrences read as the other:

| Pair | EasyOCR | PaddleOCR | PARSeq | Tesseract | Mean |
|---|---|---|---|---|---|
| 0O | 42.2 | 1.5 | 20.8 | 29.9 | 23.6 |
| **5S** | 36.4 | 0.1 | 13.6 | 14.0 | 16.0 |
| **1I** | 28.5 | 5.5 | 14.5 | 13.2 | 15.4 |
| 2Z | 20.6 | 0.6 | 2.5 | 1.8 | 6.4 |
| 8B | 16.4 | 0.1 | 2.3 | 5.3 | 6.0 |
| 4A | 20.6 | 0.0 | 1.3 | 1.0 | 5.7 |
| 8S | 3.5 | 0.0 | 2.6 | 10.4 | 4.1 |
| 7T | 9.7 | 0.2 | 0.7 | 2.6 | 3.3 |

Decision: discovery next on 5/S, then 1/I, each evolved in the current best font (`--base`), so gains accumulate. Same rules as 0/O run 5 (case-folded reading, debris rule), checks with `scratch/check_run.sh`. 5/S run 1: `out/discover/5S_run1`, base = run 5 #1.

### 5/S run 1 (2026-10-09)

2,027 evaluations, 35 cells, best fitness 0.796; all top designs descend from the Gelasio and Tinos seeds. The search makes the 5 an old-style figure (descending below the baseline, matching the amalgam's existing 3, 4, 7 and 9) and the S larger and heavier. Checks with case-folded reading, control = the base font (`out/report/isolation_5S_run1.csv`, `out/report/validation_5S_run1.csv`):

| | control | **5/S #1** |
|---|---|---|
| isolation, average of six cells, four engines | 70 | **80** |
| isolation, PARSeq (held out): 5 among letters / S among digits | 30 / 77 | **77 / 93** |
| isolation, EasyOCR: S alone / S among digits | 30 / 7 | **80 / 40** |
| unrestricted PARSeq, 5 among letters read as 5 | 9/30 | **23/30** |
| ordinary lines, 5/S pair: PaddleOCR / Tesseract / EasyOCR / PARSeq | 0.2 / 14.2 / 36.7 / 13.5 | 0.0 / **3.0** / 35.9 / **6.1** |
| R40c pixel distance | 0.086 | 0.196 |
| overall character error, mean of four | 8.1 | 8.0 |

- Unlike 0/O, the 5/S design overcomes the context prior on the held-out engine (PARSeq 5 among letters 30 to 77%).
- EasyOCR in ordinary lines is unchanged (5 read correctly 27 to 22%, pair 36.7 to 35.9%).
- Adopted. **Current best font: `~/maxocr-work/keep/current_0O_5S.ttf`** (0/O run 5 #1 + 5/S #1; copy `out/fonts/MaxOCR-current-0O-5S.ttf`; specimen `out/report/current_specimen.png`).

1/I run 1: `out/discover/1I_run1`, base = the current best font.

### 1/I run 1: a trade, not adopted (2026-10-09)

2,027 evaluations, 48 cells, best fitness 0.741 (Atkinson Hyperlegible and Source Serif seeds). The search makes the I much wider and heavier with slab serifs and the 1 shorter and lighter with a strong flag. Checks (`out/report/isolation_1I_run1.csv`, `out/report/validation_1I_run1.csv`):

| | control | 1/I #1 | 1/I #2 |
|---|---|---|---|
| isolation, average of six cells, four engines | 58 | 68 | 68 |
| ordinary lines, I read correctly (mean of four) | 81 | 93 | 92 |
| ordinary lines, 1 read correctly (mean of four) | **76** | **58** | 68 |
| ordinary lines, Tesseract 1 read correctly | 83 | 39 | 59 |
| ordinary lines, 1/I pair, mean of four | 15.5 | 11.4 | 12.6 |
| overall character error, mean of four | 8.0 | 8.4 | 7.9 |

- The fitness averages over both glyphs, so the search bought gains on the I with losses on the 1. #1 also reads its heavy I as x (8/30) on unrestricted PARSeq.
- Not adopted. Fix: `--regress W` in `discover_pair.py`; every rewarded engine x glyph x context cell that falls below the base font's accuracy costs W x the drop.
- 1/I run 2: resumed from run 1, `--regress 1.0` (`out/discover/1I_run2`); checks include run 1 #2 as a reference.

### 1/I run 2: adopted (2026-10-09)

2,011 evaluations, 50 cells, best fitness 0.804 (with the regression penalty). The top designs slant both glyphs: a tapered 1 with a curved flag, a heavy slanted slab-serif I. Checks (`out/report/isolation_1I_run2.csv`, `out/report/validation_1I_run2.csv`):

| | control | run 1 #2 | run 2 #1 | **run 2 #4** | run 2 #5 |
|---|---|---|---|---|---|
| ordinary lines, 1/I pair: Tesseract / EasyOCR / PARSeq | 12.8 / 29.3 / 14.6 | 14.0 / 25.6 / 9.5 | 3.0 / 8.0 / 3.0 | **2.7 / 7.9 / 3.3** | 4.4 / 11.0 / 3.4 |
| ordinary lines, 1 read correctly (mean of four) | 76.4 | 68.4 | 83.9 | 81.5 | 79.5 |
| ordinary lines, I read correctly (mean of four) | 81.1 | 92.3 | 93.7 | 93.8 | 94.1 |
| overall character error, mean of four | 8.0 | 7.9 | 7.4 | **7.4** | 7.6 |
| isolation, average of six cells | 58 | 68 | 73 | 74 | 75 |
| isolation, lone 1 (mean of four) | 88 | 91 | 78 | 83 | 88 |
| unrestricted PARSeq, lone 1 read as 1 | 25/30 | 24/30 | 13/30 | 20/30 | 22/30 |

- The regression penalty worked: both glyphs improve in ordinary lines and overall character error falls on every engine (EasyOCR 17.4 to 16.4%).
- Remaining weakness: a lone slanted 1 is sometimes read as 7, 2 or 4.
- Adopted run 2 #4: as good as #1 in lines, with a better lone 1. **Current best font: `~/maxocr-work/keep/current_0O_5S_1I.ttf`** (copy `out/fonts/MaxOCR-current-0O-5S-1I.ttf`).

### Progress check after three pairs (2026-10-09)

Confusion ranking, original amalgam vs current font (`out/report/confusions_amalgam.csv`, `out/report/confusions_current_0O_5S_1I.csv`; mean of four engines, case-folded reading, validation bank):

| Pair | original | current |
|---|---|---|
| 0O | 27.2 | 22.9 |
| 5S | 16.1 | 11.4 |
| 1I | 15.1 | 3.7 |
| 2Z | 6.4 | 6.6 |
| 8B | 5.7 | 6.0 |
| 4A | 5.8 | 5.9 |
| 8S | 4.0 | 3.8 |
| 7T | 3.5 | 3.4 |
| **1A** | **0.1** | **2.9** |

- Sum of all pair rates: 122.6 to 109.1. What remains of 0O (41%) and 5S (36%) is mostly EasyOCR.
- New regression: 1A (EasyOCR 8.0%), from the slanted 1. The 1/I regression penalty only covers the pair's own cells. Directed counts (`confusions_<name>_directed.csv`) will show which way it goes.
- Next pair: 2/Z (`out/discover/2Z_run1`, `--regress 1.0`, base = current font).
- Directed counts: the 1A confusion is the new 1 read as A (EasyOCR 97, Tesseract 37, PARSeq 8 of the 1s; A read as 1 only 5 times). Not a net loss: EasyOCR reads the 1 correctly 59% of the time vs 40% before; its remaining 1 errors now land on A instead of I. Watch it; if it grows, a later 1/I run can score 1 against A as well.

### 2/Z run 1: adopted #4 (2026-10-09)

2,027 evaluations, 35 cells, best fitness 0.842. The search makes the 2 small (old-style, about x-height) and the Z large and heavy. Checks (`out/report/isolation_2Z_run1.csv`, `out/report/validation_2Z_run1.csv`):

| | control | #1 | **#4** |
|---|---|---|---|
| ordinary lines, 2/Z pair, mean of four | 6.6 | 1.4 | **3.1** |
| ordinary lines, 2/Z pair, EasyOCR | 21.2 | 4.5 | 11.6 |
| ordinary lines, 2 read correctly, EasyOCR | 50.4 | 76.6 | 60.8 |
| overall character error, mean of four | 7.4 | 7.3 | 7.5 |
| unrestricted PARSeq, Z among digits read as Z | 17/30 | 18/30 (12 wrong length) | **25/30** |
| isolation, average of six cells | 73 | 81 | 82 |

- #1 has the best line numbers but PARSeq reads extra characters into its Z (12/30 wrong length among digits), and PARSeq's line error rises 3.4 to 3.7%: the same pattern as the speckled zeros. #4 is clean on the held-out engine.
- Adopted #4. **Current best font: `~/maxocr-work/keep/current_0O_5S_1I_2Z.ttf`** (copy `out/fonts/MaxOCR-current-0O-5S-1I-2Z.ttf`).
- Next pair: 8/B (`out/discover/8B_run1`, `--regress 1.0`).

### 8/B run 1: adopted #5 (2026-10-09)

2,027 evaluations, 32 cells, best fitness 0.900 (base 0.852: the amalgam was already optimized on this cluster). Checks (`out/report/isolation_8B_run1.csv`, `out/report/validation_8B_run1.csv`):

| | control | #1 | #3 | **#5** |
|---|---|---|---|---|
| ordinary lines, 8/B pair, mean of four | 6.2 | 4.3 | 5.0 | **3.6** |
| ordinary lines, 8 read correctly, mean of four | 78.2 | 81.2 | 76.2 | **83.6** |
| overall character error, mean of four | 7.5 | 7.4 | 7.9 | **7.3** |
| unrestricted PARSeq, 8 in a mixed line: wrong length | 1/30 | 0/30 | 27/30 | 4/30 |
| clean (undegraded) Tesseract, 8/B pair read correctly | 88.9 | 81.7 | 95.3 | 84.4 |

- #3 and #4 carry marks on the 8 that PARSeq reads as extra characters (wrong length 18-27/30; PARSeq line error 3.5 to 5.4%). Rejected.
- Adopted #5. Cost to watch: clean-image Tesseract accuracy on the pair drops 88.9 to 84.4% (all clean candidates show it); every degraded measure improves. **Current best font: `~/maxocr-work/keep/current_0O_5S_1I_2Z_8B.ttf`** (copy `out/fonts/MaxOCR-current-0O-5S-1I-2Z-8B.ttf`).
- Next pair: 4/A (`out/discover/4A_run1`, `--regress 1.0`).

### 4/A run 1: adopted #1 (2026-10-09)

2,027 evaluations, 21 cells, best fitness 0.953 (base 0.817). The top designs add dark blobs at the feet of the 4 and the A. Checks (`out/report/isolation_4A_run1.csv`, `out/report/validation_4A_run1.csv`):

| | control | **#1** | #2 | #5 |
|---|---|---|---|---|
| ordinary lines, 4/A pair, mean of four | 5.9 | **1.9** | 1.3 | 1.5 |
| ordinary lines, 4/A pair, EasyOCR | 21.5 | 7.4 | 4.9 | 5.0 |
| ordinary lines, 4 read correctly, mean of four | 84.5 | 91.6 | 90.0 | 88.4 |
| overall character error, mean of four (PARSeq) | 7.3 (3.6) | **7.1 (3.6)** | 7.3 (4.5) | 7.6 (5.0) |
| isolation, average of six cells | 84 | **94** | 90 | 87 |
| unrestricted PARSeq, A among digits read as A | 30/30 | 30/30 | 21/30 (9 wrong length) | 10/30 |

- #2, #3 and #5 have the extra-character pattern on PARSeq; #1 and #4 are clean.
- Adopted #1. **Current best font: `~/maxocr-work/keep/current_5pairs_4A.ttf`** (0/O, 5/S, 1/I, 2/Z, 8/B, 4/A; copy `out/fonts/MaxOCR-current-0O-5S-1I-2Z-8B-4A.ttf`).
- Observation: the adopted 8 (8/B #5) carries a small mark at its lower left; PARSeq read it at the wrong length 4/30 in mixed lines. Minor, but it is the same pattern. A guard that would catch it during search rather than after: Tesseract without a whitelist as an extra optimizing engine (proposed under 0/O run 5).

### Progress after six pairs, and the discovery guard (2026-10-09)

Confusion ranking of the current font (`out/report/confusions_current_6pairs.csv`), mean of four engines: 0O 22.8 (original 27.2), 5S 11.7 (16.1), 1I 3.8 (15.1), 8S 3.7 (4.0), 7T 3.6 (3.5), 8B 3.3 (5.7), 2Z 3.2 (6.4), 6G 3.0 (3.0), IJ 2.8 (2.4), 1A 2.6 (0.1), 9I 2.5 (2.5), 4A 1.9 (5.8). Sum of all pair rates 122.6 to 103.2. What remains of 0O and 5S is mostly EasyOCR (41 and 37%).

Extra-character marks kept reaching the top of the archive (0/O run 4, 2/Z #1, 8/B #3-4, 4/A #2-3-5) and were caught only afterwards with PARSeq, which erodes its held-out status. Why the search missed them:
- the fitness scored aligned characters only, so an inserted character never counted as an error;
- PaddleOCR and EasyOCR ignore such marks (`scratch/len_check.py`: 4/A #5 wrong length 3.8 / 27.5% vs control 2.1 / 23.3%; EasyOCR's high baseline is stray ~ and , with the general alphabet, plus cropped instances).

Tesseract without a whitelist does read them (`scratch/tess_open_check.py`, uncropped 4/A isolation bank, wrong length: control 6.8%, #2 21.4% with the blob read as ".", others 10-13%).

Decision: `discover_pair.py --guard` adds Tesseract without a whitelist (`tesseract_open`, general alphabet, case-folded; `evaluate.run(tess_open=True)`) as a fourth optimizing engine and counts insertions in every engine's overall error. Costs about 40% more time per evaluation. PARSeq stays held out. All runs from here: `--casefold --regress 1.0 --guard`.

0/O run 6: guard on, resumed from run 5's archive, base = current font (`out/discover/0O_run6`). Progress is slow (0.627 to 0.631 after 1,170 evaluations): 0/O looks close to its limit for shape changes; what remains is mostly the context prior.

### Adoption rule and pipeline (2026-10-09)

The adoption judgement is now codified (`scripts/adopt.py`) and reproduces the four manual decisions (2/Z #4, 8/B #5, 4/A #1, 1/I run 2 #4). A design replaces the current font only if, against the control: the pair's line confusion falls; overall character error rises by at most 0.05 points; PARSeq's character error rises by at most 0.2; neither glyph's accuracy falls by more than 2 points; and unrestricted PARSeq shows at most +3/30 wrong-length reads and at most -5/30 correct reads in any glyph x context cell. Lowest character error wins; if none passes, the font stays. PARSeq acts only as a veto on finished candidates.

Pipeline (`scratch/run_pipeline.sh`, `scratch/pair_pipeline.sh`, `scratch/adopt_step.sh`): applies the rule to 0/O run 6, then for 8S, 7T, 6G, IJ, 9I, 1A in turn runs guarded discovery (`--casefold --regress 1.0 --guard`, run name `<pair>_g1`), the checks and the rule, carrying the current font forward (path in `~/maxocr-work/keep/CURRENT`; log `~/maxocr-work/logs/pipeline.out`). Every adoption is reviewed afterwards.

Discovery run 5: debris rule, PaddleOCR and EasyOCR on case-folded general-alphabet reads (`--casefold`), resumed from run 4's elites (`out/discover/0O_run5`).

Decision: every validation from now on also reads with an unrestricted alphabet and case-folds the output (o counts as O). This is the realistic general-use check; the restricted reading stays as the "code reader with a whitelist" scenario (a legitimate deployment mode, e.g. Tesseract's char whitelist). Next discovery run: score PaddleOCR and EasyOCR on case-folded unrestricted reads, so the search can't win by pushing a glyph outside the allowed set.

## Open questions for James

1. **Per-cluster targets (Section 7 step 4).** The rule "if the R40b estimate is above 0.1%, target = 2x the estimate" gives Source Code Pro at s=0.5 a {0,O,D} target of 0.22% (estimate 0.111%) and leaves the other clusters with no stated target (estimates at or below 0.1%). The PaddleOCR baseline is 4.5%, so a ~0.2% target means closing ~95% of the gap with font changes alone. That is probably unreachable and would make the success criterion meaningless. Proposal: express targets as a fraction of headroom closed (R41), e.g. "close at least 50% of the gap between the best baseline and the probe estimate, per objective cluster". That matches the 50% figure the PRD already uses for the transfer test. **Decided 2026-10-09: accepted (James).**
2. **Context check (proposed addition, measured only).** Evaluate fonts with context available (Tesseract dictionaries on, PaddleOCR with no alphabet restriction, real words and format-constrained codes such as VIN-style strings) to confirm gains don't reverse when an engine can use context. Not an optimization target. Extends the PRD's existing R13b word control. Note: VINs already exclude I/O/Q and UPCs are digits-only, and most measured confusions are digit-vs-letter, so the expected gain is largest for unconstrained alphanumeric codes (serials, licence keys, part numbers). **Decided 2026-10-09: accepted (James).** Partly in place already: every validation reads with the general alphabet and folded case.

3. **Best baseline is a near tie.** At the operating point Source Code Pro (8.45%) leads IBM Plex Mono (8.67%) by 0.21 points, and an earlier, mis-ordered version of the procedure ranked Iosevka first. Proposal: any font within noise of the best counts as co-best and MaxOCR must beat all of them; Source Code Pro is the R40/R40b reference. **Decided 2026-10-09: accepted (James).** v0.4 frozen; M1a complete.
5. **Tesseract in the objective?** With the amalgam, PaddleOCR is near its ceiling (about 1%) while Tesseract is at about 6.5%; R28 keeps Tesseract as a gate only. Options: keep (PARSeq remains the held-out check either way), or optimize a combination of both engines.
4. **R2a ink-box tolerance vs the O-width lever** (see "Iosevka levers"): proposal to set the tolerance per glyph from the advance minus a minimum sidebearing.

## R37b worker allocation (measured 2026-10-08)

One synthetic generation, repeated for each worker split: 32 candidate builds (weight 380..411, every glyph rebuilt), each candidate evaluated on a 500-line optimization bank, suite (a), PaddleOCR on all 16,000 images and the Tesseract gate on all 32 candidates (worst case). Builds and evaluation overlap. `scripts/timing.py`, `out/report/timing.json`.

| Build workers x Tesseract workers | Generation wall | Mean build | PaddleOCR time |
|---|---|---|---|
| 4 x 16 | 69.7 s | 8.0 s | 50.8 s |
| **8 x 12** | **62.8 s** | 9.3 s | 53.7 s |
| 12 x 8 | 65.0 s | 11.8 s | 54.0 s |
| 16 x 4 | 65.7 s | 14.2 s | 53.3 s |

- R37b allocation: **8 build workers, 12 Tesseract workers**. The split barely matters; PaddleOCR running serially in the parent (~3.3 ms/image) bounds the generation.
- R38: a generation takes ~1 minute against the 10-minute cap (and inside the PRD's "under 2 minutes" estimate). Population or bank size can grow ~5-10x before the cap binds. If needed, a second PaddleOCR process on the GPU is the next lever, not more cores.
- One-time compile: 16 working copies doing their first build in parallel took 197 s each (vs 16.7 s alone). One-time per copy; does not affect generations.

## Early timings (reference machine, single build, Iosevka v34.9.0 @ 2487637)

| Step | Measured | PRD assumption |
|---|---|---|
| First subset build incl. one-time compile | 16.7 s | — |
| Subset rebuild after a glyph change (candidate cost) | 5.2–5.4 s | 18 s (R33b) |
| Full-charset build | 22.1 s | 59 s (R33b) |
| PP-OCRv6 medium rec, one 8-char line, GPU, unbatched | ~3 ms | — |

Verified that a variant change alters only the target glyph's outline and leaves advances at 500. The subset build's cmap holds 56 code points (36 requested plus Iosevka's required extras). The ~5 s candidate cost is mostly fixed tool startup, so parallel workers (R33c) should scale well. R38's 10-minute generation budget looks comfortable.

### Planned final step: the golden mean (James, 2026-10-09)

The discovered glyphs work for OCR but some look messy (the 1 especially). At the end, produce two fonts:
- **MaxOCR Machine**: the maximum-OCR glyphs, for machine-primary use.
- **MaxOCR Text**: readable, "pretty" glyphs that keep most of the gain, for human documents.

Method: for each changed glyph, a slider from the stock glyph to the discovered one (SDF blend, 0-100% in steps), each step cleaned (smoothed outlines, straight stems, stroke weight matched to the font), and the full checks run on every step. Rule (James, 2026-10-09): human acceptability is a hard constraint, judged by James; within it, keep as much of the gain as possible (no fixed share). The current 1 (slanted, tapered, curved flag) is not acceptable and is the first glyph to fix.

### Pair pipeline results (2026-10-09)

Adoption rule (`scripts/adopt.py`, with the within-cluster guard added after James pointed out that 1, I and J are one group). Line numbers: pair confusion and overall character error, mean of four engines, case-folded reading.

| Run | Decision | Pair before -> after | Character error before -> after |
|---|---|---|---|
| 0O_run6 | none passed | 22.8 | 7.08 |
| 8S_g1 | #4 | 3.70 -> 2.19 | 7.08 -> 7.05 |
| 7T_g1 | #2 | 3.59 -> 1.87 | 7.05 -> 6.80 |
| 6G_g1 | #1 | 2.73 -> 1.54 | 6.80 -> 6.74 |
| IJ_g1 | #3 | 3.27 -> 0.22 | 6.74 -> 6.46 |
| 9I_g1 | none passed (all raise character error) | 2.52 | 6.46 |
| 1A_g1 | none passed (unrestricted PARSeq loses 7-14 of 30 correct reads in a cell, mostly the lone 1) | 2.18 | 6.46 |

**Current font: `~/maxocr-work/keep/current_after_IJ_g1.ttf`** (export `out/fonts/MaxOCR-current-after-IJ_g1.ttf`): 0/O, 5/S, 1/I, 2/Z, 8/B, 4/A, 8/S, 7/T, 6/G, I/J. Character error across the four engines 8.2% (original amalgam, case-folded) to 6.46%. The 1 is left for the golden-mean step.

### Held-out VLM check: Qwen2.5-VL-3B (2026-10-09)

Vision-language model reader, never used in the search (`maxocr/engines/qwenvl.py`, `scripts/vlm_eval.py`; open vocabulary, case folded; prompt says the text is random letters and digits). Speed 24 lines/s on the RTX 4060 Ti (batch 32). Validation bank (all ~4,000 uncropped lines) and the isolation test for 12 pairs, s=0.5, suite (a) (`out/report/vlm_lines.csv`, `out/report/vlm_isolation.csv`):

| | Source Code Pro | original amalgam | current |
|---|---|---|---|
| character error | 4.98 | 1.97 | **1.67** |
| lines read exactly | 70.8 | 85.0 | **87.0** |
| 0O pair | 31.7 | 11.6 | **7.8** |
| 5S pair | 6.3 | 0.9 | 0.6 |
| 1I pair | **2.1** | 11.1 | 3.9 |
| IJ pair | **0.1** | 0.5 | 1.3 |
| isolation, adversarial context: 0O / 5S / 8B | 21 / 62 / 62 | 43 / 77 / 81 | **53 / 94 / 83** |
| isolation, adversarial context: 1I / 9I / IJ | **64 / 64** / 34 | 45 / 49 / 38 | 51 / 53 / 28 |

- The gains transfer to a VLM reader: character error 5.0% (Source Code Pro) to 1.7%, and the 0/O confusion falls from 32% to 8%.
- Weak spot: the 1/I/J/9 group, where Source Code Pro (serifed I, flagged 1 with a base) is still read better. The current slanted 1 is both the least readable glyph for people and a weak point for the VLM; it is the first target of the golden-mean step.

### Readable font (MaxOCR Text), step 1 (2026-10-09)

James: A, I, J, 1 and Z are too sloppy even in the 25% mix; J and F look bad even in the original. Text base Mix E (`golden_mean.py --mix "02BOST:1,45678G:0.25,1IJAZF:0"`). Clean search (`discover_pair.py --clean`: whole-glyph typographic mutations only, 16 OFL serif seeds) with guard and regression penalty, on the text base.

Clean 1/I (`out/discover/1I_clean`): all designs clean (short old-style 1, heavier I; James: OK). 1/I confusion 15.9 to 8.8% (#1) and 9.8% (#3), character error 7.45 to 7.16 / 7.23 (messy version: 3.9%). The adoption rule picks #3 (#1 loses 9/30 lone-1 reads on unrestricted PARSeq); James: they look identical, take the one with fewer errors. **Chosen: #1** (`~/maxocr-work/discover/1I_clean/c01882.ttf` glyphs 1 and I). J/F replacement: waiting for James's pick from `out/golden/jf_options.png`.

Text base F (`~/maxocr-work/golden/mixF.ttf`, export `out/fonts/MaxOCR-Text-mixF.ttf`): Mix E + 1 and I from clean 1/I #1 + J and F from Noto Serif (James: "all things equal, I like Noto Serif best"; J and F are not big confusion sources, I/J ~2%, E/F under 1%). The clean 4/A search was interrupted (stopping the old loop killed it) and resumes from its archive on Mix F (`4A_clean2`); then 2/Z and I/J (`scratch/clean_rest.sh`).

### Digits only, MICR, and a sizing mistake (2026-10-10)

`scripts/digits_eval.py`: 3,000 random digit strings, s=0.5 and clean, four engines (0-9A-Z output). MICR E-13B via GnuMICR 0.30 (GPL-2; github.com/alerque/gnumicr tag v0.30, archive sha256 e087b0a8...; measurement only, `vendor/fonts/GnuMICR.ttf`, not redistributed). Mean character error, s=0.5:

| MICR E-13B | OCR-A | OCR-B | Source Code Pro | original amalgam | MaxOCR Machine | MaxOCR Text (base F) |
|---|---|---|---|---|---|---|
| 15.5 | 9.4 | 1.9 | 2.6 | 0.97 | 1.25 | 1.02 |

- MICR is the worst for general OCR engines (Tesseract 37%, EasyOCR 19%); it is designed for magnetic readers and dedicated E-13B recognizers.
- Mistake caught: the first run sized each font by its 0. The new 0 is taller than the capitals, so Machine and Text were rendered at 6.4 pt instead of 8 pt and looked 6-7x worse (the "digits regression" and the dropped-digit analysis came from that). Sizes now match on the capital H (on the 0 only for MICR, which has no letters); all MaxOCR fonts render at 8 pt, as in every other test.
- Digit heights (James's idea, `scripts/digit_heights.py`, `out/report/digits_variants.csv`): current digits 1.02%, all full height 1.62, original heights 1.12, all short 10.9, short with slashed 0 14.5, short with dotted 0 15.0. Keep the current digits.

### Real-text check (R13c): Gettysburg Address (2026-10-10)

`scripts/text_eval.py`: the address in capitals without punctuation (the fonts have 0-9, A-Z, space), lines of at most 22 characters, 8 degraded draws per line at s=0.5 plus clean; engines use language: PaddleOCR, EasyOCR, PARSeq on the general alphabet with case folded, Tesseract without a whitelist and with dictionaries on, Qwen2.5-VL with a plain transcription prompt. Mean character error at s=0.5 (`out/report/text_eval.csv`): Source Code Pro 5.87, original amalgam 1.89, MaxOCR Machine 1.81, MaxOCR Text (bold I) 1.89, MaxOCR Text (normal I) 2.06. Qwen2.5-VL 0.1-0.3% for every font.

- On real words the pair-by-pair gains largely disappear: language context already resolves most confusions. The gains are for context-free strings (codes, serials, part numbers), as the PRD anticipated (R13c note).
- The blend itself stays about 3x better than Source Code Pro (EasyOCR 18% vs 2-3%).
- I options measured on the validation bank (`out/report/confusions_mixG*.csv`): bold I 1/I 8.8%, character error 7.40%; normal I 10.3%, 7.51%.

### MaxOCR Text final choices (James, 2026-10-10)

- 2/Z: blend option #2 (fewer errors overall than #1).
- I: the big bold I from the clean 1/I search (James: "we have to go with bold I, even though it looks weird"); 1/I 8.8% vs 10.3% for the normal I.
- **MaxOCR Text** = Mix G (`~/maxocr-work/keep/MaxOCR-Text.ttf`, export `out/fonts/MaxOCR-Text.ttf`): 0, O, 2(blend), B, S, T and Z(blend) from the OCR search; 4, 5, 6, 7, 8, G at the 25% slider; 1 and I from the clean 1/I search; J and F from Noto Serif; A original.
- **MaxOCR Machine** = the pair-pipeline font (`~/maxocr-work/keep/MaxOCR-Machine.ttf`, export `out/fonts/MaxOCR-Machine.ttf`).

Size sweep (`scripts/size_sweep.py`, `out/report/size_sweep.csv`; random codes, s=0.5, mean of four engines): 8 pt / 200 dpi Source Code Pro 12.0, original 8.2, Machine 6.3, Text 7.2; 12 pt / 300 dpi 6.6, 4.7, 4.2, 4.3. The gain over the original shrinks from ~25% to ~10% as text gets larger; MaxOCR stays about a third below Source Code Pro at every size. On random codes Tesseract and EasyOCR still miss 6-11% even at 12 pt / 300 dpi; PaddleOCR is near perfect from 8 pt up.

### Final comparison (2026-10-10)

Held-out VLM (Qwen2.5-VL-3B, `out/report/vlm_lines_final.csv`, `vlm_isolation_final.csv`): character error Source Code Pro 4.98, original amalgam 1.97, MaxOCR Machine 1.67, **MaxOCR Text 1.51**; isolation test (10 pairs, single/mixed/adversarial) correct 76.3 / 84.4 / 87.3 / 87.0%.

| Mean character error (%) | Source Code Pro | original amalgam | MaxOCR Machine | MaxOCR Text |
|---|---|---|---|---|
| random codes, 8 pt / 200 dpi, four engines | 12.0 | 8.2 | 6.3 | 7.2 |
| random codes, 12 pt / 300 dpi, four engines | 6.6 | 4.7 | 4.2 | 4.3 |
| digits only, four engines | 2.6 | 1.0 | 1.3 | 1.0 |
| Gettysburg Address, five readers | 5.9 | 1.9 | 1.8 | 1.9 |
| VLM (held out), random codes | 5.0 | 2.0 | 1.7 | 1.5 |

MICR E-13B on digits only: 15.5. Open: EasyOCR's context bias on 0/O; lowercase and punctuation (basic Latin); spec v0.5.

### Against the best existing fonts; letter spacing (2026-10-11)

James: Source Code Pro was the best of the six spec baselines, not of the 414-font Windows survey, so the comparison set now includes the survey's best (Bookman Old Style, Sitka Text, Courier New, Georgia, Verdana; `maxocr.fonts.SURVEY_BEST`, measurement only). All fonts at equal capital height (`maxocr.fonts.matched_size`; Source Code Pro had been ~6% small at equal point size).

| Mean character error (%) | MaxOCR Machine | MaxOCR Text | original | Sitka Text | Courier New | Bookman | Source Code Pro | Verdana | Georgia |
|---|---|---|---|---|---|---|---|---|---|
| random codes, 8 pt / 200 dpi | 6.29 | 7.13 | 8.16 | 9.12 | 9.46 | 9.94 | 10.24 | 10.30 | 12.45 |
| random codes, 12 pt / 300 dpi | 4.27 | 4.33 | 4.58 | 5.29 | 5.94 | 5.89 | 6.58 | 5.92 | 6.00 |
| VLM (held out), random codes | 1.73 | 1.48 | 1.98 | 3.18 | 2.17 | 3.29 | 3.88 | 3.31 | 4.42 |
| Gettysburg, four engines | 2.05 | 2.27 | 2.45 | 3.43 | 6.43 | 4.39 | 6.43 | 4.79 | 4.37 |

(`out/report/size_sweep_vs_best.csv`, `vlm_lines_vs_best.csv`, `text_eval_vs_best.csv`.) The Gettysburg run with the VLM stalled with the GPU memory full (VLM plus three engines); rerun without the VLM.

Letter spacing (`scripts/letter_spacing.py`, shapes unchanged; `out/report/size_sweep_spacing.csv`): gap between letters relative to cap height: Georgia 0.09, Sitka 0.14, MaxOCR Text 0.15, Courier New 0.21. MaxOCR Text with gaps x1.5 / x2: 8 pt 7.13 to 6.00 / 5.50, 12 pt 4.89 to 4.64 / 4.26; lines 6% / 13% longer. Wider gaps cut errors by about a quarter at small size, more than the whole Machine-vs-Text difference. Testing x2.5, x3 and Machine x2 next.
Wider gaps (`out/report/size_sweep_spacing2.csv`), random codes, mean of four engines, 8 pt / 12 pt: Text x2 5.50 / 4.26 (+13% line length), x2.5 5.40 / 3.93 (+19%), x3 5.23 / 3.72 (+26%); Machine 6.29 / 4.83, Machine x2 5.08 / 4.04. Most of the gain is in by x2; proposal: x2 for both fonts (waiting for James on the extra width).

### MaxOCR Smart: context-dependent glyphs and spacing (James's idea, 2026-10-11)

Engines read all-letter words and all-digit numbers well; they fail where a letter touches a digit. `scripts/smart_font.py` builds on MaxOCR Text: (A) `kern` feature adding 100 units at every letter-digit and digit-letter boundary; (B) `calt` contextual alternates swapping in the MaxOCR Machine form of a glyph whose neighbour is of the other kind; (C) both. Words and numbers render exactly as MaxOCR Text; applications that ignore calt/kern show MaxOCR Text. The renderer keeps calt off except with `MAXOCR_CALT=1` (set for these runs).

Random codes, mean of four engines (`out/report/size_sweep_smart.csv`):

| | 8 pt / 200 | 12 pt / 200 | 8 pt / 300 | 12 pt / 300 |
|---|---|---|---|---|
| MaxOCR Text | 7.13 | 4.89 | 5.08 | 4.33 |
| MaxOCR Machine | 6.29 | 4.83 | 4.78 | 4.27 |
| Text, gaps x2 everywhere | 5.50 | 4.26 | 3.97 | 3.68 |
| Smart A (space at boundaries) | 5.60 | 3.83 | 3.88 | 3.34 |
| Smart B (OCR glyphs at boundaries) | 6.30 | 4.78 | 4.82 | 3.98 |
| **Smart C (both)** | **5.12** | **3.50** | **3.71** | 3.40 |

Smart C: 28% fewer errors than Text at 8 pt / 200 dpi without widening words or numbers. Smart A gets most of the gain with clean glyphs everywhere. Waiting for James: C or A as the main font.

James chose Smart A (clean glyphs everywhere). Boundary space tuning (`out/report/size_sweep_smartA.csv`, mean of four engines, 8 pt/200 | 12 pt/300): 100 units 5.60 | 3.34, 150 5.04 | 2.95, 200 4.76 | 2.38. **But** the harness metric ignores spaces, and wide boundary gaps make engines insert word spaces into codes (`scratch/space_check.py`, 600 code lines, share read with a space, PaddleOCR / EasyOCR / Tesseract): Text 0 / 2 / 1%, Smart A 100: 0 / 7 / 6%, 150: 2 / 19 / 15%, 200: 11 / 47 / 34%. A stray space breaks a serial number, so the spacing is now scored with spaces counted (`scripts/space_aware_eval.py`: Levenshtein distance between code and upper-cased reading, spaces kept).

Space-aware scores (`out/report/space_aware.csv`, Levenshtein with spaces, PaddleOCR / EasyOCR / Tesseract whole-line text, 1,000 code lines, s=0.5): 8 pt: Text 9.83, Smart A 50 8.70, Smart A 100 8.68; 12 pt: 6.60, 5.97, 5.91. Lines with a stray space (EasyOCR / Tesseract): A 50 2.0 / 1.0%, A 100 3.5 / 3.3% at 8 pt. An earlier pass that dropped Tesseract's spaces had Smart A 150 and 200 at 8.50 and 10.72 (200 worse than Text). 50 and 100 tie on error; **50 chosen** (fewer stray spaces, closer to normal spacing).

**MaxOCR (final) = Smart A, 50 units** (`out/fonts/MaxOCR.ttf`): MaxOCR Text glyphs everywhere, 50 units of extra space where a letter meets a digit (kern feature); about 11% fewer errors than MaxOCR Text on codes with stray spaces counted; words and numbers identical to MaxOCR Text. MaxOCR Machine stays available for machine-only use.

### Optical sizes (James, after Sitka's six optical sizes; 2026-10-11)

Variants of MaxOCR (`scripts/weight_variant.py` outline offset +-12/24 units, `scripts/letter_spacing.py` x0.7 / x1.5), space-aware error, PaddleOCR / EasyOCR / Tesseract, 800 code lines, s=0.5 (`out/report/space_aware_optical.csv`):

| | 6 pt | 8 pt | 12 pt |
|---|---|---|---|
| MaxOCR | 20.74 | **8.85** | 5.91 |
| wider (gaps x1.5) | **18.35** | 9.04 | 6.27 |
| bolder (+12) | 23.70 | 9.46 | 5.85 |
| bolder + wider | 20.55 | 9.15 | **5.66** |
| much bolder (+24) | 29.27 | 11.39 | 5.84 |
| lighter (-12) | 25.54 | 11.68 | 8.24 |
| tighter (gaps x0.7) | 25.14 | 10.61 | 6.65 |

- 6 pt: wider spacing cuts errors by 12%; heavier hurts (counters fill in). 8 pt: MaxOCR (tuned there) is best. 12 pt: bolder + wider is only ~4% better.
- Decision: ship **MaxOCR Small** (MaxOCR with gaps x1.5, `out/fonts/MaxOCR-Small.ttf`) for print under about 7 pt; no separate large size.

Final fonts in `out/fonts/`: **MaxOCR.ttf** (main: readable glyphs, extra space where letters meet digits), **MaxOCR-Small.ttf** (wider spacing, under ~7 pt), **MaxOCR-Text.ttf** (no contextual spacing), **MaxOCR-Machine.ttf** (maximum OCR, machine-only). Intermediate exports moved to `out/fonts/intermediate/` (paths quoted earlier in this log under `out/fonts/` now live there; the canonical copies are in `~/maxocr-work/keep/`).

### VV / W merges and splits (James, 2026-10-11)

`scripts/merge_split_eval.py`: 6-character codes with VV or W inserted (fillers exclude U, V, W, I, O, Q), s=0.5, equal capital height, four engines (`out/report/merge_split.csv`). Mean over engines: VV read as W: MaxOCR 0.3%, original 0.1, Sitka 0.9, Courier New 0.0, Source Code Pro 1.5, Verdana 9.9. W read as VV: 0% for every font. Codes read exactly: MaxOCR 68.9%, original 64.2, Sitka 59.1, Courier New 58.8, Source Code Pro 52.9, Verdana 47.8. Not a problem for MaxOCR; lowercase merges (rn/m, cl/d) remain for the basic-Latin phase.

### Basic Latin, step 1: lowercase draft and first case-sensitive ranking (2026-10-11)

Lowercase a-z added to MaxOCR Text as an equal blend of IBM Plex Serif, Spectral and Gelasio (the faces that dominate the capitals' recipes; `scripts/add_lowercase.py`). Case-sensitive harness: `confusions.py --alnum` (5,000 random 0-9A-Za-z strings, every engine restricted to 0-9A-Za-z, no case folding), fonts at equal capital height.

Character error, mean of four engines: Courier New 13.01, **MaxOCR (untuned lowercase) 13.05**, Sitka Text 13.56, Source Code Pro 15.20, Georgia 18.54. Top MaxOCR pairs (%): I/l 17.5 (Source Code Pro 2.1, Courier 2.4: their l has a foot or tail), 0/O 17.0, J/j 11.7 (Courier 5.9), 5/S 8.0, W/w 8.0, 2/z 7.9, Z/z 7.5, 0/o 7.4 (Sitka 38.4), V/v 7.4, 1/l 7.3 (Courier 39.2), 5/s 6.9, c/e 6.4 (others 1.0-2.4), I/f 6.0 (others under 1: the bold I reads as f), 1/i 5.6. Same-shape case pairs (W/w, V/v, Z/z, X/x, C/c) are partly inherent in random mixed-case strings; the x-height is a lever to test.

Disk and memory incident (2026-10-11): C: filled up (0 bytes free) and Windows hit its memory commit limit (108.6 of 109.5 GB) because of ~400 Microsoft Edge automation processes and their `edge-drive-*` temp profiles (not MaxOCR). James killed the automated Edge processes; the temp profiles were deleted (22 GB free after). On the MaxOCR side: the Qwen model (7.1 GB) and the pixi package cache were removed (the model re-downloads in ~9 min); the WSL disk was made sparse; `scripts/smart_font.py` (restored from git) and `scripts/add_lowercase.py` (rewritten) had been emptied by a failed write.

### Basic Latin, step 2: first lowercase tuning (2026-10-11)

`scripts/text_opt_lc.py` (case-sensitive blend search, 400 random 0-9A-Za-z lines oversampling the pair, PaddleOCR / Tesseract / EasyOCR restricted to 0-9A-Za-z, PARSeq held out; ingredients IBM Plex Serif, Spectral, Gelasio, Noto Serif, Source Serif 4, Courier Prime; `--only` holds the other glyph): l (vs I), j (vs J), c and e, f (vs I). Combined into `~/maxocr-work/lc/Text-lc-tuned1.ttf` (`out/golden/lc_tuned_sheet.png`; the old f had a stray crossbar from the equal blend; the new f and j are a little bolder).

Validation (`confusions.py --alnum`, 5,000 lines, four engines incl. PARSeq): character error 13.05 to **11.83** (PARSeq 9.39 to 8.41), now below Courier New 13.01, Sitka 13.56 and Source Code Pro 15.20. Pairs: J/j 11.67 to 6.60, c/e 6.39 to 3.25, I/f 5.95 to 0.07, I/l 17.54 to 16.18 (Courier 2.37, Source Code Pro 2.05: their l has a foot or tail), 1/l 7.34 to 8.42. Next: the l again with ingredients whose l has a tail or foot (Courier Prime, Andika, Atkinson Hyperlegible; run `Il_lc2`).

### Measurement bias found: line padding (2026-10-11)

The renderer's line image spans the font's ascender to descender (plus 4 px), so each font brought its own vertical padding; engines normalize line height (PaddleOCR to 48 px), so more padding means smaller letters. Canvas height / cap height: Sitka 1.57, Georgia 1.64, MaxOCR 1.65, Verdana 1.67, Bookman 1.72, OCR-B 1.76, Source Code Pro 1.92, Courier New 1.98. Cross-font comparisons therefore favoured MaxOCR against Source Code Pro and Courier New (their letters ~15% smaller in the engine input) and slightly favoured Sitka. Comparisons between MaxOCR variants (same metrics) are unaffected. Fix: `MAXOCR_CROP=ink` crops each line to its ink plus 0.25 x the font's cap height above and below (how a detector crops a real line); the cross-font comparisons are being rerun with it (`scratch/rerun_fair.sh`).

Found while testing a taller lowercase l: glyph parts above the font's ascent (900 units in MaxOCR builds) are clipped by the renderer and by Windows, so the final fonts need an ascent that covers their tallest glyph. Taller-l test with equal, unclipped metrics (ascent 1,060 for every variant; `scratch/l_taller.py`), l read correctly PaddleOCR / Tesseract / EasyOCR: current (830 units, 1.19 x cap) 69 / 40 / 51%, x1.10 83 / 53 / 69%, x1.15 84 / 56 / 76%, x1.20 86 / 62 / 76%, x1.25 92 / 67 / 79% (overall Tesseract error rises from x1.20). Pure tailed or footed l's (Courier Prime, Cousine, Andika, Atkinson) did worse than the current l (their l reads as 1); the l is mostly misread as I (421 of 5,000-line errors), Courier's as 1 (843).

Fair rerun (`MAXOCR_CROP=ink`; `out/report/size_sweep_fair.csv`, `confusions_fair_lc_*.csv`, `text_eval_fair.csv`):

| Mean character error (%) | MaxOCR (final) | Machine | Text | original | Courier New | Sitka | Source Code Pro | Bookman | Verdana | Georgia |
|---|---|---|---|---|---|---|---|---|---|---|
| codes 0-9A-Z, 8 pt / 200 dpi | **5.65** | 6.00 | 6.74 | 7.03 | 7.48 | 8.34 | 8.80 | 8.88 | 9.39 | 10.87 |
| codes 0-9A-Z, 12 pt / 300 dpi | **3.56** | 4.17 | 4.35 | 4.19 | 5.02 | 5.29 | 5.70 | 5.09 | 5.63 | 5.40 |
| Gettysburg, four engines | 2.06 | 1.88 | 2.06 | **1.80** | 4.70 | 2.88 | 5.43 | 3.69 | 4.36 | 3.86 |

Case-sensitive codes (0-9A-Za-z): Courier 11.42, MaxOCR (tuned lowercase) 11.56, Sitka 13.22, Source Code Pro 13.43, Georgia 17.51; MaxOCR I/l 14.7% (Courier 2.8), Courier 1/l 38.2% and 0/O 27.1% (MaxOCR 8.6 and 17.9).

- The strongest existing font is Courier New once padding is fair. MaxOCR (final) makes 24% fewer errors than Courier at 8 pt / 200 dpi and 29% fewer at 12 pt / 300 dpi on capital-and-digit codes; on mixed-case codes they tie (I/l is MaxOCR's gap). Earlier cross-font claims (e.g. "31% fewer than Sitka") are superseded by this table.

Taller l under fair cropping (`confusions_fair_lc_l114/120.csv`): I/l 14.7 to 10.8 / 9.4% and 1/l 8.6 to 6.4 / 5.2%, but overall error 11.56 to 11.77 / 11.86% (lines containing l get taller, so every letter is smaller after height normalization). Not adopted; the current l stays.

Fonts exported with lowercase, version 0.2 (`out/fonts/MaxOCR.ttf`, `MaxOCR-Small.ttf`, `MaxOCR-Text.ttf`; 0-9, A-Z, a-z, space; letter-digit spacing now also covers lowercase; the caps-only versions are in `out/fonts/intermediate/*-caps-only.ttf`). Metrics checked: tallest glyph 848 (I) under ascent 900; deepest -251 (j) within Windows descent 300. MaxOCR Machine stays capitals and digits only.

### Per-character comparison (James: "did you measure each char alone?", 2026-10-11)

`confusions.py` now writes per-character error (`confusions_<name>_perchar.csv`). 13 fonts, case-sensitive codes, fair cropping (`out/report/perchar_winners.csv`): mean error Courier New 11.31, MaxOCR 11.53, Sitka 13.17, Source Code Pro 13.38, IBM Plex Serif 13.54, Andika 14.47, Courier Prime 14.73, Source Serif 4 15.50, Noto Serif 15.78, Literata 16.40, Cousine 16.64, Georgia 17.43, Atkinson Hyperlegible 18.04. MaxOCR is the best font for D T W G Y K f l S O 0 j. Largest gaps to the best open-licence glyph (MaxOCR -> best OFL, % error): J 26.7 -> 9.5 (Courier Prime), t 14.8 -> 1.5 (Courier Prime), 1 30.3 -> 18.0 (Cousine), r 14.9 -> 2.9 (Cousine), h 12.9 -> 1.4 (Cousine), z 27.6 -> 16.8 (Andika), a 12.7 -> 3.0 (Courier Prime), g 13.3 -> 4.1, I 14.2 -> 5.2 (Courier Prime).

Best-of variants (`scratch/bestof.py`, sheet with numbers `out/golden/bestof_labeled.png`): swapping in the best OFL glyph for each weak character: 11.56 -> **9.81** keeping the bold I and short 1, **9.38** swapping those too (PARSeq 8.39 -> 6.27); 50/50 SDF blends 10.99 (artifacts). The swaps mix monospace sans letters into the serif lowercase. Waiting for James: accept the mix, make the lowercase one consistent style around the winners, or borrow only letters that fit.
Real mixed-case text (`text_eval.py --mixed-case`: the Gettysburg Address as written, case-sensitive, fair cropping; `out/report/text_eval_mixed.csv`), mean of four engines at s=0.5 (clean in brackets): swap incl. I and 1 **5.22** (2.02), swap keeping I and 1 5.37 (2.09), Sitka 5.79 (2.27), Courier New 5.89 (3.60), MaxOCR now 7.59 (2.94; EasyOCR 20.4%), Source Code Pro 8.17 (4.98). The swaps also win on real text; the current lowercase is weak there. Sheet with both numbers: `out/golden/bestof_labeled2.png`.
**James chose option 3** (best open-licence glyph swapped in for each weak character, including I and 1, replacing the bold I and short 1): MaxOCR v0.3 = `~/maxocr-work/lc/bestof1.ttf` + letter-digit spacing (`~/maxocr-work/keep/MaxOCR-v03.ttf`). Checks running: capitals-and-digits codes (v0.3 vs v0.2 vs Courier New) and per-character scores for the next round.
v0.3 checks (`out/report/size_sweep_v03.csv`, `confusions_pc_v03*.csv`): capitals-and-digits codes 8 pt / 12 pt: v0.3 5.04 / 3.78, v0.2 5.65 / 3.88, Courier New 7.48 / 5.31 (the borrowed I, 1, J, 3, 7, 9 help on capitals too); case-sensitive codes 9.38. Borrowed letters mostly keep their scores inside MaxOCR (z 16.8, J 10.7, 1 21.2; i 28.4 vs 21.1 in Courier Prime). Weakest characters now come in clusters: l 46.2, i 28.4, 1 21.2 (with I); 0 39.8, o 19.2 (with O); 5 31.2, s 15.6 (with S); Z 19.5, z 16.8, 2 16.5. Exported as version 0.3 (`out/fonts/MaxOCR.ttf`, `MaxOCR-Small.ttf`, `MaxOCR-Text.ttf`; v0.2 in `out/fonts/intermediate/`). Next: joint cluster searches (`text_opt_lc.py --pair <cluster> --only <glyphs>`).

### Cluster round 1 (v0.4 candidate, 2026-10-11)

Joint blend searches on v0.3 (`text_opt_lc.py`, ingredients Courier Prime, Cousine, Andika, IBM Plex Serif, Spectral, Gelasio): cluster l/I/i/1 changing l, i; o/O/0 changing o; 5/S/s changing 5, s; Z/z/2 changing all three. Search fitness 0.71 -> 0.79, 0.75 -> 0.77, 0.82 -> 0.88, 0.76 -> 0.86. Combined: `~/maxocr-work/keep/MaxOCR-Text-v04c.ttf` (+ letter-digit spacing `MaxOCR-v04c.ttf`). Checks, fair cropping: case-sensitive codes 9.38 -> **8.29** (PARSeq 6.27 -> 5.46); mixed-case Gettysburg at s=0.5 5.22 -> **3.80** (clean 2.02 -> 2.31); capital-and-digit codes 8 pt 5.04 -> 5.20, 12 pt 3.78 -> 3.81. Per character: i 28.4 -> 4.7, s 15.6 -> 9.1, Z 19.5 -> 11.4, z 16.8 -> 10.4, 2 16.5 -> 12.7, 5 31.2 -> 27.9, o 19.2 -> 15.9; l unchanged (46%). Sheet with numbers: `out/golden/v04_labeled.png`.

### Consistent lowercase heights (James: "the r is much taller than the o", 2026-10-11)

Borrowed letters keep their source font's x-height (Cousine, Courier Prime are taller than the serif blend). `scripts/normalize_xheight.py` scales each lowercase glyph uniformly so its top matches the same glyph in the equal serif blend (`--tall`: the reference heights x the median ratio of the borrowed letters a g n r s x z). James: digits and symbols may keep different heights. Results (fair cropping; `confusions_pc_v04n/t*`, `text_eval_v04n/t.csv`):

| | mixed codes | real text s=0.5 | real text clean |
|---|---|---|---|
| A. v0.4 as is (uneven heights) | 8.29 | 3.80 | 2.31 |
| B. heights matched to the serif letters (shorter) | 8.30 | 5.00 | 2.30 |
| C. heights matched to the borrowed letters (taller) | 8.96 | 3.71 | 2.25 |
| Courier New | 11.42 | 5.89 | 3.60 |

Shorter heights hurt damaged real text (EasyOCR 8.3 to 12.7%); taller heights help real text but cost mixed codes (lowercase closer in size to capitals: Tesseract 10.8 to 12.1%). Sheet: `out/golden/v04_heights.png`. Waiting for James.
James: the heights still look inconsistent (s vs c in "score", i vs z in "sizes"). Measured: tops in options B and C agree within ~1%; the visible differences are widths and stroke weights (against the serif reference: z 43% wider and heavier, s 31% wider, a 29% wider, n 22% narrower, x much heavier). Option D (`--tall --match-width`: reference proportions at the taller scale): mixed codes 9.34, real text 4.42 at s=0.5, 2.07 clean (`confusions_pc_v04w*`, `text_eval_v04w.csv`). Sheet `out/golden/v04_width.png`. The remaining unevenness is style (sans and monospace letters among serif ones), which scaling cannot remove.
Correction (James: C still uneven): option C matched only the tops. The CMA-ES blends also moved letters up or down (`bottom_shift`): in C, s and e dip ~4% below the baseline, z ~3%, i floats ~2% above it. `normalize_xheight.py --align-bottom` also puts each bottom at the reference's (baseline, overshoot or descender, x the same factor). Option E (`--tall --align-bottom`, `~/maxocr-work/keep/MaxOCR-Text-v04e.ttf`): mixed codes 9.08 (EasyOCR 16.22, Paddle 1.89, PARSeq 6.19, Tesseract 12.02), real text 4.17 at s=0.5, 2.03 clean (`confusions_pc_v04e*`, `text_eval_v04e.csv`). Close-up with guide lines: `out/golden/v04_ce.png`.
James: in E the u is still shorter than the o (round letters overshoot, as in normal type; flat letters were also a few units short). `scripts/exact_heights.py` stretches each lowercase letter vertically (widths kept) so its ink spans exactly one band: x-height letters [0, 541], ascenders b d f h k l [0, 828], descenders g j p q y [-235, 541], t [0, 668]; i/j by the stem top. Option F (`~/maxocr-work/keep/MaxOCR-Text-v04f.ttf`, from E): mixed codes 9.15 (EasyOCR 16.28, Paddle 1.85, PARSeq 6.35, Tesseract 12.13), real text 4.17 at s=0.5, 2.04 clean: same as E within noise. Sheet: `out/golden/v04_ef.png`.
F against the survey's best on mixed-case real text (`text_eval_v04f_vs_best.csv`, fair cropping), mean of four engines, s=0.5 (clean): MaxOCR F 4.17 (2.04), Georgia 9.13 (2.14), Verdana 9.25 (3.24), Bookman 8.59 (2.95); earlier runs: Sitka 5.79 (2.27), Courier New 5.89 (3.60). Clean print is close (Georgia within 0.1); on damaged print MaxOCR has half the errors of Georgia, Verdana and Bookman (EasyOCR 9.6 vs 24-26%).
Held-out VLM on mixed-case real text (Qwen2.5-VL-3B, case kept, `text_eval.py --vlm-only`, `text_eval_vlm_mixed.csv`, fair cropping), character error at s=0.5 (clean): MaxOCR F **0.26** (0.69), Courier New 0.57 (0.08), Sitka 0.60 (0.09), Georgia 0.61 (0.00), Bookman 0.64 (0.01), Verdana 0.74 (0.16). The clean 0.69 is two lines repeated 8 times (Qwen skipped "little" in "world will little note"; added a "c" after "the"). Clean at 7/7.5/8/8.5/9/10 pt (`scratch/vlm_clean_sizes.py`), mean: MaxOCR 0.35, Sitka 0.22, Courier New 0.13, Georgia 0.09. On damaged print MaxOCR halves the VLM's errors; on clean print the VLM reads ordinary fonts slightly better (about 1 character in 300 vs 1 in 1,000).

### v0.4 adopted (option F, 2026-10-11)

James: "F is a good first step, but we need to keep in mind that we're 3-4x worse for LLMs (which are a very normal use case)". Exported as version 0.4 (`scratch/export_v04.sh`: `out/fonts/MaxOCR.ttf` with letter-digit spacing, `MaxOCR-Small.ttf` with gaps x1.5, `MaxOCR-Text.ttf`; v0.3 in `out/fonts/intermediate/*-v03.ttf`). Next target: clean-print reading by VLMs. `scripts/vlm_clean_eval.py` reads clean renders of everyday prose written for the project (`maxocr/prose.py`, not memorizable), the same words shuffled, and mixed codes at 6-10 pt, and tallies misread characters and skipped words per font.
Clean-print VLM results (`out/report/vlm_clean_base*.csv`, `_preds.jsonl`; Qwen2.5-VL-3B, case kept, 6-10 pt, 200 dpi). All sets, character error: Sitka 0.60, Courier New 0.81, MaxOCR Small v0.4 0.82, MaxOCR v0.4 0.91, Georgia 1.00, IBM Plex Serif 1.02, Verdana 1.04, MaxOCR v0.3 1.18. The shuffled-words set is dominated by the model rewriting word salad into sentences ("order will lights opens The" -> "The lights will open"), which alignment counts as misreads; it is not a realistic input. Prose and codes only: **Courier New 0.243, MaxOCR Small 0.243, MaxOCR v0.4 0.272**, Sitka 0.324, IBM Plex Serif 0.387, Verdana 0.445, Georgia 0.451, MaxOCR v0.3 0.618. Letter misreads (substitutions) on prose and codes: MaxOCR Small 4, MaxOCR v0.4 7, MaxOCR v0.3 10, Courier New 12, IBM Plex Serif 17, Georgia 21, Sitka 22, Verdana 38. Most remaining errors are at line ends (last short word dropped, "in the" -> "in", or a letter appended, "the" -> "thec"), for every font (Sitka 10, Courier 13, MaxOCR 18, Georgia 18, Verdana 19 lines): a VLM habit, not a font problem. Conclusion: the "3-4x worse for LLMs" from the Gettysburg clean run was a small-sample artifact (2 lines x 8 identical repeats, on a text the model knows by heart); on unseen clean text MaxOCR is level with the best fonts and has the fewest letter misreads. The clean VLM test is now part of the checks for every change.

### Even capitals (James: "did you do the same with the uppercase?", 2026-10-11)

Capitals in v0.4 range from cap height 700 to S 840 (+20%), B 759, O 741, Z 739 (floating +19), G 733, E 728 (floating +32), T 728. `exact_heights.py --caps` puts every capital on [0, 700] (Q by its bowl, tail below); `--uniform-caps` scales both ways (proportions kept). Option G (vertical squash) and U (uniform), `~/maxocr-work/keep/MaxOCR-Text-v04g/u.ttf`: mixed codes F 9.15 -> G 9.73 / U 9.83; real text s=0.5 4.17 -> 4.22 / 4.18, clean 2.04 -> 2.40 / 2.35; VLM clean prose+codes 0.27 -> 0.30 / 0.31 (noise level; letter misreads 7 -> 4 / 4). Per character (mixed codes): S 2.9 -> 15.4 / 18.4% (the tall S kept it apart from s and 5), Z 13.9 -> 19.4, O 12.4 -> 16.1, C 10.6 -> 13.2, B 1.9 -> 4.4. Sheet `out/golden/v04_caps.png`.
James: not U as it is; keep working on the S ("always a little ugly anyway, kinda looked like a snake"); revisit the font survey for the most reliable S. The 2026-10-08 survey read capitals only (5/S, not S/s), so `scripts/s_survey.py` reran it case-sensitively: 453 faces (413 Windows, measurement only; 38 OFL; MaxOCR F and U), 400 lines oversampling S s 5 8, s=0.5, three engines (`out/report/s_survey.csv`). S correct-read rate: MaxOCR F (tall S) 96.0, best Windows faces ~89-90 (High Tower Text, XB Niloofar, Times New Roman), best OFL Tinos 88.3, Lora 86.5, Public Sans 86.2, Spectral 84.5, Crimson Pro 83.0; MaxOCR U 71.2 (S read as s 141 times). Across 218 faces the height ratio s/S predicts S accuracy (Spearman -0.44) and s accuracy (+0.46) in opposite directions: S/s is mostly a size trade-off; MaxOCR's ratio is 0.77 (best S faces 0.65-0.72). Next: the top OFL S shapes inside U (`scripts/s_candidates.py`).
S candidates inside U (`scripts/s_candidates.py`, `out/report/s_candidates*.csv`; same 400-line S-focused bank, three engines): F (tall S) S 95.0 / overall 10.36; U 76.2 / 11.62. Donor S shapes at normal width: Tinos 79.4, Lora 76.4, Public Sans 76.2, others 68-75: shape alone barely helps, because S and s have the same proportions (aspect 0.79 vs 0.81) and differ only in size. Width does: narrower S 0.75x 50-63 (worse), wider S 1.3x 83-86, 1.45x 85-87, 1.6x 86-88 (Lora 1.45x 87.1 / 11.12; Tinos 1.6x 87.3 / 11.27; Public Sans 1.6x 88.4 / 11.12). Boldness 1 changes nothing for a single-ingredient S (SDF distances are integers); 2 has no clear effect. Sheet `out/golden/s_options.png`.
James picked option 3 (Lora S at 1.45x width, even height; `~/maxocr-work/keep/MaxOCR-Text-v04s.ttf`) and approved a search around it: `text_opt_lc.py --pair Ss58 --only S --exact-caps --width-range 1.25,1.75`, ingredients Lora, Tinos, Public Sans, Spectral, Crimson Pro, Libre Baskerville (new flags: capitals set on [0, cap height] after every build; width bounds and start).
S search (`out/discover/S_even/`, 30 generations): fitness 0.849 (option 3) -> 0.858; best recipe Lora 0.37, Tinos 0.43, Public Sans 0.13, Libre Baskerville 0.05, width 1.33, boldness -1.1 (`~/maxocr-work/keep/MaxOCR-Text-v04s2.ttf`). Fresh checks (5,000-line case-sensitive bank, real text, VLM clean): S misread F 2.9 / U 18.4 / option 3 11.7 / search 11.4%; mixed codes 9.15 / 9.83 / 9.78 / 9.75; real text s=0.5 4.17 / 4.18 / 4.18 / 4.18, clean 2.04 / 2.35 / 2.35 / 2.35 (the address has no capital S); VLM clean prose+codes 0.27 / 0.31 / 0.30 / 0.29. The search's gain over option 3 is within noise; option 3 (pure Lora, James's pick) stays. The wide S recovers about 40% of the S loss, but evening the capitals costs the most on other letters too (Z 13.9 -> 19.4, O 12.4 -> 16.1, C 10.6 -> 13.2, B 1.9 -> 4.4), so mixed codes stay at 9.8 vs 9.2. Sheet `out/golden/s_final.png`.
James: the tall S is by far the best but weird-looking; try the Lora S taller. `s_candidates.py --heights --below` (uniform enlargement, extra height mostly above the cap line like v0.4's S, or half below), base U, S-focused bank (`out/report/s_candidates_tall.csv`), S correct / overall error: v0.4 tall S 95.0 / 10.36; Lora normal width at 1.05/1.1/1.15/1.2x 84.6 / 90.5 / 93.0 / 93.9; Lora 1.45x wide at 1.05/1.1/1.15/1.2x 89.8 / 93.0 (overall 10.40) / 95.5 / 96.8. Putting half the extra below the baseline is no better. A normal-looking S matches the tall S once it is 10-15% taller. Sheet `out/golden/s_tall.png`.
James picked A (Lora S, 1.45x wide, 10% taller than the other capitals, which are even; `~/maxocr-work/keep/MaxOCR-Text-v04sa.ttf`). Full checks running.
A full checks (`confusions_pc_v04sa*`, `text_eval_v04sa.csv`, `vlm_clean_sa*`): S misread 5.2% (F 2.9, U 18.4, option 3 11.7); mixed codes 9.73 (F 9.15, U 9.83); real text 4.18 at s=0.5, 2.35 clean (as U); VLM clean prose+codes 0.28 (F 0.27). The rest of the gap to F is the other evened capitals: Z 19.6 vs 13.9, O 16.2 vs 12.4, C 13.3 vs 10.6, B 4.5 vs 1.9. Sheet `out/golden/sa_vs_f.png`.

### Z, O, C, B at even height (James: "go", 2026-10-11)

Misreads in A: Z as z (245) and 2 (40); O as o (126) and 0 (97); C as c (154); B as 8, R, E. Donor screen inside A (`scripts/cap_candidates.py`, was `s_candidates.py`: any capital, `self` = the current glyph; every OFL face, even height, normal width; `out/report/cand_<L>_screen.csv`), correct-read rate, A -> best donor (v0.4 F): Z 69.4 -> Libre Baskerville 75.5 (79.0); O 75.9 = our own wide O, donors 61-68 (83.3); C 81.1 -> EB Garamond 85.6, Tinos 84.5 (86.2); B 93.5 -> IBM Plex Serif 96.6, Literata 96.4 (97.8). Next: width x height grid for the best shapes (`cand_<L>_grid.csv`).
Width x height grid inside A (`cand_<L>_grid.csv`), correct-read rate (v0.4 F in brackets). Even height: Z from Libre Baskerville 1.4x wide 82.2 (79.0); C from EB Garamond 1.4x 89.7, Tinos 1.4x 89.9 (86.2); B from IBM Plex Serif 1.15x 97.2 (97.8); O best 77.2 (83.3). 10% taller: Z 85-89, O (own, 1.15x wide) 87.9 / (own) 86.0, C 93-95.5, B 97-98.6 (at 1.05x). As for the S, height is the strongest lever and width the next. Built A2e = A + Z (Libre Baskerville 1.4x), C (EB Garamond 1.4x), B (IBM Plex Serif 1.15x), all even height; A2t = A2e + O 10% taller (`~/maxocr-work/keep/MaxOCR-Text-v04a2e/t.ttf`, `scratch/build_a2.py`). Sheet `out/golden/a2.png`; full checks running.
A2e / A2t full checks (`confusions_pc_v04a2e/t*`, `text_eval_v04a2.csv`, `vlm_clean_a2*`): mixed codes 9.48 / 9.38 (v0.4 F 9.15, A 9.73); misread Z 11.8 / 11.4 (F 13.9), O 16.4 / 10.3 (F 12.4), C 7.5 / 7.6 (F 10.6), B 1.9 / 1.9 (F 1.9), S 5.0 (F 2.9); real text 4.16 at s=0.5 (F 4.17), clean 2.39 (F 2.04); VLM clean prose+codes 0.31 / 0.31 (F 0.27, noise level: letter misreads 8 / 5). The remaining 0.2-point gap to F is spread thinly over many characters (w, Q, s, 1, v, x, z, k, 8: 1.5-2.5 points each, near the noise of a 5,000-line bank). Sheet `out/golden/a2.png`.

### v0.5 adopted (A2t, 2026-10-11)

James picked A2t. Exported as version 0.5 (`scratch/export_v05.sh`; `out/fonts/MaxOCR.ttf` with letter-digit spacing, `MaxOCR-Small.ttf`, `MaxOCR-Text.ttf`; v0.4 in `out/fonts/intermediate/*-v04.ttf`): v0.4 + even lowercase (exact bands) + even capitals on [0, 700], except S (Lora, 1.45x wide) and O (own, wide) 10% taller; Z from Libre Baskerville 1.4x wide, C from EB Garamond 1.4x wide, B from IBM Plex Serif 1.15x wide. Demo sheet `out/golden/v05_demo.png`. Versus Courier New: mixed codes 9.38 vs 11.42; real text 4.16 vs 5.89 at s=0.5, 2.39 vs 3.60 clean; VLM clean prose+codes 0.31 vs 0.24 (noise level).

### Consistent digit heights (James: "should we consider dropping them all?", 2026-10-11)

v0.5 digits: 0 on [-32, 838] (20% above the cap height), 4, 5, 8 drop ~10% below the baseline, 2 floats +19, the rest on ~[0, 700] (the 1 is not dropped). `scripts/digit_variants.py` puts every digit on one band (uniform scale) and scores 400 lines oversampling digits and their look-alikes (`out/report/digit_variants*.csv`): overall error / digits read right: current 12.56 / 88.8; even on the baseline 12.75 / 87.2; all dropped 5/10/15% (same size) 13.58 / 12.73 / 14.06; all extended below (taller, bottom at -d) 10% 12.32 / 90.3, **15% 11.95 / 91.2**, 20% 12.56, 25% 13.15, 30% 13.80; bands reaching above the cap height worse (12.6-13.5). Dropping digits as a group does not help; taller digits that hang 15% below the line do (deeper helps the digits but hurts the letters: the lines get taller). Full check of [-105, 700] running (`~/maxocr-work/keep/MaxOCR-Text-v05d.ttf`). Sheet `out/golden/digits.png`.
Full check of digits on [-105, 700] (`confusions_pc_v05d*`, `vlm_clean_v05d*`; v0.5 = `confusions_pc_v04a2t*`): mixed codes 9.38 -> 9.29; digits mean misread 17.0 -> 15.8 (1 21.0 -> 16.6, 5 30.2 -> 26.6, 3 7.8 -> 5.3, 7 9.8 -> 7.3, 2 13.0 -> 11.1) but 0 40.4 -> 44.7 and O 10.3 -> 12.1 (the 10% taller O now stands above the 0, which was the tallest glyph); VLM clean prose+codes 0.31 -> 0.29, codes alone 0.76 -> 0.51. James: maybe the 0 should be special to keep it apart. Queued: the old tall 0 inside v05d, and v05d's 0 taller at the top (1.1x, 1.2x) and narrower (0.8x, 0.9x) (`cand_0_special.csv`).
Special 0 (James: "maybe 0 should be special, to keep differentiation?"; `cand_0_special.csv`, focus 0 O o Q D): inside v05d, the old tall 0 (v0.5's, [-32, 838]) gives the lowest error and the best 0: 12.55 / 0 read right 56.6 (v05d 13.42 / 55.1, v0.5 12.97 / 56.1); v05d's 0 taller at the top 1.1x / 1.2x 12.73 / 12.97; narrower 0s worse (0.9x, 0.8x: 47-53, read as l and I). Candidate: digits on [-105, 700] except the tall 0 (`~/maxocr-work/keep/MaxOCR-Text-v05d_old0.ttf`).

### Lowercase merges (James: "have we yet checked vv/w?", 2026-10-12)

Capital VV/W was checked on 2026-10-11 (0.3%). `merge_split_eval.py --lower` (case-sensitive; vv/w, rn/m, cl/d, ri/n, in/m; 150 codes per form; `merge_lower.out`; the 60-minute cap stopped it during Georgia, so Georgia and Verdana are missing and no CSV was written; the timeout left the Python child running, killed by hand). Merge rate (pair read as the single letter), mean of four engines: vv -> w MaxOCR 15.8, MaxOCR Small 36.6, Courier New 0.0, Sitka 0.0; rn -> m 0.0 / 0.0 / 0.2 / 1.8; cl -> d 0.2 / 0.0 / 0.0 / 0.4; ri -> n and in -> m 0 for all; splits (w -> vv etc.) ~0. Cause: MaxOCR's v, w, y have negative sidebearings (v -13/-13), so vv touches; `letter_spacing.py` multiplied negative sidebearings by 1.5, making Small worse. Fixes: `letter_spacing.py` leaves negative sidebearings alone; `scripts/min_sidebearings.py` gives v, w, y a minimum gap (0/20/40/60 tested next, `merge_vv_fix.csv`).
vv fix (`merge_vv_fix.csv`, on v05d_old0): vv read as w, mean of four engines: as now 21.2%; v w y sidebearings >= 0: 9.2; >= 20: 0.9; **>= 40: 0.0** (codes with vv or w read exactly 69.7%, Courier New 62.9); >= 60: 0.0. rn/m 0 throughout. Chosen: 40 units.

8 (James: "we should also re-visit 8"; `cand_8_screen.csv`, every OFL 8 placed on the digit band [-105, 700] inside v05d, focus 8 S B g s 3): 8 is read as S, B, g, s. Best donors Gelasio 87.6, Crimson Pro 87.2 vs our own 86.8 (v0.5 87.0): within noise; the 8 stays.

### Punctuation survey (James: "look at open source fonts to see who does punctuation best", 2026-10-12)

`scripts/punct_survey.py`: 38 OFL faces + Windows faces with all 32 ASCII marks, 400 lines over 0-9A-Za-z + punctuation (marks x6), s=0.5, three engines, general alphabet, case-sensitive. First 192 faces (all OFL): best overall Courier Prime (OFL) 64.6% of marks read right, Cousine (OFL) 59.2, Cascadia Mono/Code 49.1, Crimson Pro 45.1, Gelasio 44.8, Garamond Bold 43.4, Work Sans 43.1; proportional faces mostly 20-40%: monospaced cells give marks room. Hardest marks (median over faces): ` 0, ! 7.8, ] 8.8, } 9.9, | 11.1, ' 11.1, ; 13.3, , 13.6; easiest + 60, > 48, < 43. Batch 4 crashed in the renderer (a glyph wholly outside the canvas gave mismatched slices; `maxocr/render.py` now skips it; earlier results unaffected, that case always crashed). Remaining faces resumed.
Punctuation survey complete (450 faces, `out/report/punct_survey*.csv`): marks read right, Courier Prime (OFL) **64.6** (first of all 450), Courier New 59.8, Lucida Console 59.4, Cousine (OFL) 59.2, Sitka Text 57.4, Verdana Bold 56.0, Consolas 55.8; best proportional OFL Crimson Pro 45.1, Gelasio 44.8. Sheet `out/golden/punct_survey.png`. Plan: borrow mostly from Courier Prime and Cousine with generous spacing, then test the marks inside MaxOCR.

v0.6 candidate full checks (`~/maxocr-work/keep/MaxOCR-Text-v06c.ttf`: v0.5 + digits on [-105, 700] except the tall 0 + v w y sidebearings >= 40; `confusions_pc_v06c*`, `text_eval_v06c.csv`, `vlm_clean_v06c*`): mixed codes **8.97** (v0.5 9.38, v0.4 9.15); digits mean misread 15.1 (v0.5 17.0), 0 39.7 (40.4), v 15.3 (21.3), w 16.2 (18.7), y 6.6 (7.9); real text 3.96 at s=0.5 (v0.5 4.16), clean 2.44 (2.39); VLM clean prose+codes 0.335, codes 0.69 (v0.5 0.31 / 0.76; letter misreads 7, noise level).

### v0.6 adopted (2026-10-12)

James: yes. Exported as version 0.6 (`scratch/export_v06.sh`; v0.5 in `out/fonts/intermediate/*-v05.ttf`): v0.5 + digits on [-105, 700] except the tall 0 + v w y sidebearings >= 40 (Small: 60, now that `letter_spacing.py` leaves negative sidebearings alone). Full character set sheet `out/golden/v06c_charset.png`.

### Punctuation, round 1 (2026-10-12)

`scripts/add_punct.py` adds the 32 ASCII marks, each rebuilt from an OFL donor at the MaxOCR cap height (donor position and advance relative to its cap height, so monospaced donors bring wide cells); `scripts/punct_eval.py` scores fonts on the survey's bank at equal capital height. Candidates on v0.6 Text: all marks from Courier Prime; all from Cousine; per mark the better of the two (survey); per mark the best OFL face (survey). References: Courier Prime, Cousine, Courier New.
Round 1 results (`out/report/punct_eval*.csv`), marks read right / letter-digit error: MaxOCR + best OFL face per mark **71.6** / 13.39; + Courier Prime marks 67.5 / 13.32; + better of Courier Prime and Cousine 67.6 / 13.84; + Cousine 63.3 / 14.73; references Courier Prime 68.4 / 24.18, Cousine 62.9 / 22.40, Courier New 63.3 / 18.90. The per-mark best set (Courier Prime for most; Cousine " * , : ; ? [; Lora #, Work Sans $, IBM Plex Sans %, Libre Baskerville &, Gelasio =, Tinos @) beats every reference. Weakest marks in it: ` 25, | 33, ] 45, ! 46, ^ 55, \ 56, * 60, $ 63, ? 65. Sheet `out/golden/punct_round1.png`. Next: shape, size and position search for the weak marks (`cap_candidates.py --general`).
Round 2 (`scratch/punct_round2.py`, `out/report/punct2_*.csv`, `punct2_summary.csv`): each weak mark's own glyph at widths 1/1.3 and sizes 1/1.25/1.5 (growing up, both ways, down) and the top three survey donors; pick = best mark accuracy with overall error within +0.3: | 50 -> 67 (1.25x, growing down), ] 61 -> 77 (Cousine 1.25x), ! 52 -> 69 (1.5x), * 78 -> 90 (1.3x wide, 1.5x), ? 73 -> 84 (Courier Prime 1.25x), $ 68 -> 72, ^ 49 -> 55, \ 60 -> 62, ` 27 -> 30; partners [ like ], / like \. Combined set (`punct_eval2/3.csv`): marks 74.1 but letter-digit error 13.39 -> 17.19, because 8 enlarged marks reached beyond the letters' span [-235, 838] (taller line boxes shrink everything after height normalization, as with the digits). Kept inside the span (uniform shrink + shift, `scratch/punct_clamp.py`): marks 74.0, letter-digit error 14.43, overall 23.45 (round 1 24.88). The survey bank packs far more marks per line than real text, so the choice between the round 1 and round 2 sets goes to the grocery story with punctuation (`text_eval.py --story`, `text_eval_story.csv`).
Grocery story with punctuation (`text_eval_story.csv`, 22-character lines, 4 draws, four engines, case-sensitive), mean error s=0.5 / clean: MaxOCR + round 1 marks 4.65 / 2.25; MaxOCR + round 2 marks (in span) 4.54 / 2.37; Courier New 6.54 / 3.49; Sitka 7.01 / 2.85; Courier Prime 8.14 / 3.21; Georgia 10.59 / 3.14. MaxOCR with punctuation leads every reference on real text with marks. Round 1 and round 2 tie within noise; the choice is the look (round 2: bigger ! ? * $ | [ ] ^ \ /). Sheet `out/golden/punct_r1_r2.png`.

### v0.7 adopted (punctuation, 2026-10-12)

James picked round 1. Exported as version 0.7 (`scratch/export_v07.sh`; 95 characters: 0-9, A-Z, a-z, space and the 32 ASCII marks; v0.6 in `out/fonts/intermediate/*-v06.ttf`). Full character set sheet `out/golden/v07_charset.png`. James asked whether ligatures should separate vv/w and similar: not needed; the sidebearing fix brings vv -> w to 0% and works in every application, while ligatures and pair kerning are features some applications ignore (Word has kerning off by default). Pair kerning stays the option if a new merge appears.

### Cleanup round (at the end; James, 2026-10-12)

1. Punctuation spacing: marks borrowed from monospaced faces keep wide cells ("$8.49.", "1,305" look gappy). Try tightening and measure the cost.
2. Bowls of b and d (and similar) too tall: their counters reach 509 / 511 vs the o's 466 (x-height 541), so the bowls rise ~8% of the x-height above the round letters; p 481, q 485 slightly high too (g 457, e 493). Bring the bowls down to the o's height (shape edit within the glyph, not a scale of the whole letter) and measure.

### Lowercase l (James: "go", 2026-10-12)

v0.7's l is misread 44.9% (mixed codes; PARSeq 55, Tesseract 52, EasyOCR 42, Paddle 30), mostly as I (415) and 1 (215). The earlier taller-l test helped I/l but cost overall (taller lines). Donor screen inside v0.7 at the ascender band (`cand_l_screen.csv`, focus l I 1 i): Work Sans 72.7 (overall 12.77) vs our l 62.4 (13.12); Fira Sans, Noto Serif 66.9; widening our l makes it worse (1.2x 63.1, 1.4x 55.3, 1.6x 48.2: read as 1). Work Sans and Fira Sans l's end in a small tail to the right. Grid (`cand_l_grid.csv`, focus l I 1 i L): Work Sans at normal width 68.5 vs v0.7 59.0 (overall 11.90 vs 12.07); a wider tail is read as L (Work Sans 1.3x 63.5, 1.5x 55.8). Full checks of v0.7 + Work Sans l running (`MaxOCR-Text-v07l.ttf`).
Full checks (`confusions_pc_v07l*`, `text_eval_story_v07l.csv`, `vlm_clean_v07l*`), v0.7 -> v0.7 + Work Sans l: l misread 44.9 -> 37.3; mixed codes 8.97 -> 8.92; story s=0.5 4.65 -> 4.54, clean 2.25 -> 2.28; VLM clean prose+codes 0.335 -> 0.393, but the extra substitutions are mostly one prose line the model reordered ("summer holidays begin The" -> "The summer holidays begin"); it misread the new l once. James: yes.

### v0.8 adopted (2026-10-12)

Exported as version 0.8 (`scratch/export_v08.sh`; v0.7 in `out/fonts/intermediate/*-v07.ttf`): v0.7 + lowercase l from Work Sans. Full character set sheet `out/golden/v08_charset.png`.

### Lowercase style matching (James: "1", 2026-10-12)

Sources of v0.8's lowercase: Courier Prime (typewriter slab) a, b, g, t; Cousine (monospace sans) h, n, r; Andika/Cousine-heavy blends o, s, x, z; Work Sans l; the rest (c d e f i j k m p q u v w y) from the serif blend. For a, b, g, t, h, n, r, x, s, o, z: every serif OFL face's glyph inside v0.8 at the exact lowercase bands, scaled uniformly (`exact_heights.py uniform_lower`, so donors keep their proportions), scored on a bank oversampling the letter and its top confusions (`scratch/lc_style.py`, `out/report/lcstyle_u00XX.csv`).
Quick test per letter (`lcstyle_summary.csv`; best serif donor, letter read right now -> serif, overall error change): a Merriweather 94.7 -> 92.9 (-0.54), b Spectral 97.4 -> 97.6 (+0.06), h PT Serif 96.1 -> 96.8 (-0.32), n Libre Baskerville 95.0 -> 96.6 (-0.17), o Source Serif 4 85.5 -> 85.9 (-0.25), x PT Serif 84.8 -> 82.8 (+0.13); t Literata 97.2 -> 93.5 (+0.41), z Lora 87.9 -> 84.2 (+0.74); s Tinos 90.2 -> 83.7 (+0.37), g Merriweather 94.8 -> 86.2 (+0.76), r Literata 96.8 -> 87.2 (+0.47). Built S1 (serif a b h n o x), S2 (+ t z), S3 (all eleven); full checks running.
Full checks (`confusions_pc_v08S1/2/3*`, `text_eval_story_v08s.csv`, `vlm_clean_v08s*`), v0.8 / S1 / S2 / S3: mixed codes 8.92 / 8.89 / 9.08 / 9.56; story s=0.5 4.54 / 4.78 / 4.73 / 5.60, clean 2.28 / 2.00 / 2.18 / 2.32; VLM clean prose+codes 0.39 / 0.31 / 0.31 / 0.26 (noise level). S1 is free on codes, slightly worse on damaged text, better on clean; S3 costs a point on damaged text (g 3.5 -> 10.3, r 2.0 -> 11.1, s 12.1 -> 16.9). Recommended S1. Sheet `out/golden/lcstyle.png`, published page https://claude.ai/artifact/WP7xVFZ6xaLPWD7wAYdcdw (images go out as private pages now that direct file sending is gone).
James: S1.

### v0.9 adopted (2026-10-12)

Exported as version 0.9 (`scratch/export_v09.sh`; v0.8 in `out/fonts/intermediate/*-v08.ttf`): v0.8 + serif lowercase a (Merriweather), b (Spectral), h (PT Serif), n (Libre Baskerville), o (Source Serif 4), x (PT Serif). Still non-serif for accuracy: t, z (moderate cost), s, g, r (high cost), l (Work Sans). Full character set sheet `out/golden/v09_charset.png`.
Specimen page for the current version (republished on each release): https://claude.ai/artifact/TrVjxydoADdpD2kbuTHU9N (`scratch/specimen_page.py`).

### f, g, j look weird (James, 2026-10-12)

f: bulky, blobby top (serif blend); g: Courier Prime typewriter g; j: lumpy hook (blend artifact). Screen of every OFL face inside v0.9 (`out/report/fgj_u00XX.csv`, focus f E F i / g 9 G J / j i J 5), letter read right (overall error): f now 93.7 (8.87), Lato 94.1 (8.42), Work Sans 93.4 (8.25), Open Sans 93.0, Merriweather 90.8 (8.55), Tinos 89.7 (8.29); g now 93.8 (9.44) = Courier Prime, every serif g 82-86 (read as 8, 9, E; error +1.0-1.7); j now 94.1 (11.09), donors 75-87. `maxocr/blend.py` CharRecipe gains `smooth` (Gaussian blur of the SDF): our own glyphs rebuilt smoothed (`smooth_{f,g,j}.csv`): g smooth 6 94.0 (9.27), j smooth 2 / 4 / 6 93.0 / 92.0 / 87.8, f smooth 6 93.0 (heavier). Options page https://claude.ai/artifact/JxNKAGK7qA38MAUD93roHc (`out/golden/fgj.png`).
James: "all are terrible. You didn't visually look at the chars in the context of the other chars"; "don't measure anything. LOOK". Looking at f, g, j in words (`scratch/look_fgj.png`, `context_{f,g,j}.png`): all three are darker than the rest of the lowercase; f has a blobby top hook and thick crossbar, g is the heavy typewriter g with a flat ear (the darkest letter on the page), j has a lumpy hook and slab top. Variants (`scratch/fgj_look.py`): blends of the serif trio break f and lose the j hook at lighter weights; our own glyphs made lighter keep their odd shapes (the j falls apart). Single serif donors fit: IBM Plex Serif, Gelasio, Lora (f, j), and two-storey g from Spectral, Plex Serif, Source Serif, Lora. Combinations from one face each (`combo_*.ttf`): Plex Serif looks cleanest; Lora's j crowds the word before it; Gelasio's g a touch heavy; Spectral's g lighter. Accuracy (quick test, f g j focus, `fgj_combos.csv`): v0.9 f 93.6 g 92.8 j 91.2 (error 8.61); Plex f g j 78.8 / 88.1 / 72.6 (11.97); heavier Plex is worse (`fgj_plex_bold.csv`). Story (`text_eval_story_fgj.csv`): v0.9 4.78 / 2.00; Plex f g j 5.05 / 1.95; Plex f j + Spectral g 5.03 / 1.95. The current f, g, j score through distinctive shapes (the g's flat ear vs 9, the j's slab and hook vs i), not weight. Codes check running.

### Real curves (James: "the left of the e looks cut flat. Are these vectors or bitmaps?", 2026-10-12)

The glyphs are vector outlines, but every one made through `maxocr/blend.py` is a polygon: the blend traces blended bitmaps with straight segments only (e 468 points, all on-curve; no curve points in any glyph), so curves show flats and wobbles when enlarged. `scripts/curve_outlines.py` (new dependency `potracer`, pixi pypi) renders each glyph at one pixel per font unit, optionally blurs it (Gaussian, font units) and traces it with potrace into Bezier curves (corners kept where the outline turns sharply), converted to TrueType quadratics (cu2qu), advance kept, TrueType contour direction. Plain tracing reproduces the polygon flaws exactly; blur 4 too little, **8** removes flats and jagged edges while keeping serif corners crisp, 12 rounds the serif corners (`scratch/curves_blur.png`). Shape-level flaws survive any blur: the bulge at the O's lower left and the wavy j tail (need reshaping). The codes check of the Plex Serif f g j (`confusions_pc_fgj_*`): codes 8.89 -> 9.67 (f 4.8 -> 20.0, g 3.5 -> 10.7, j 5.8 -> 22.1); Plex f j + Spectral g 9.74. James: "there are more than 2 options" (serif shapes plus the one distinguishing feature; a serif-only search). Whole font converted with blur 8 (`MaxOCR-Text-v09c.ttf`); full checks running.
Curve version full checks (`confusions_pc_v09c*`, `text_eval_story_v09c.csv`, `vlm_clean_v09c*`), v0.9 -> curves: codes 8.89 -> 8.81; story 4.78 -> 4.76, clean 2.00 -> 2.16; VLM 0.31 -> 0.31. No accuracy cost.

f g j with real donor outlines (`scripts/copy_glyph.py`: the donor's own vector outline scaled to cap 700 and set on the exact band; composites decomposed). Looked at in words (`scratch/real_{f,g,j}.png`): sturdier serifs match the weight of our serif letters (f, g, j: Merriweather, Literata, Source Serif, Noto Serif, PT Serif for g; Gelasio for j); Plex Serif, Lora, Spectral, Crimson Pro read light. Options on v0.9 curves (quick test, f g j oversampled, `fgj_options.csv`; error / f / g / j read right): now 8.42 / 93.3 / 93.6 / 91.0; Merriweather f g j 11.83 / 89.4 / 87.5 / 56.6; Literata 12.53 / 82.7 / 81.2 / 68.7; Source Serif 11.66 / 88.2 / 82.9 / 68.7; Noto Serif 12.73 / 78.5 / 83.2 / 60.2; Plex Serif 11.70 / 79.7 / 84.1 / 69.3; Merriweather g only 9.22 / 92.4 / 87.5 / 89.7; Merriweather f g + our j 9.55 / 89.4 / 87.5 / 89.9. Every serif j is read as i; our j's slab and long hook carry it. Option 8 adds our j traced with heavy smoothing (blur 16). Story test of the main options running.
Story (`text_eval_story_fgj2.csv`, s=0.5 / clean): now (curves) 4.76 / 2.16; Merriweather f g j 4.83 / 2.10; Source Serif f g j 4.97 / 2.14; Merriweather g only 4.79 / 2.14; Merriweather f g + our j 4.83 / 2.10 (also smoothed). On real text the serif f g j cost is within noise; the cost is on random codes (j read as i or J). More j's (`j_more.csv`, focus j i J 5): ours 93.7, ours made lighter (SDF -1, then curves) 91.4, Crimson Pro 81.6, Source Serif 79.1, Plex 76.8, Merriweather 60.3 (read as J). Looked at four j choices with Merriweather f g (`fgj_final_look.png`): all-Merriweather most even; Crimson Pro and Source Serif j fit as well; our lighter j still has a slab head unlike the i. Quick test (`fgj_final.csv`, error / f / g / j): now 8.50 / 93.3 / 93.6 / 90.4; A Merriweather f g j 11.83 / 89.4 / 87.5 / 56.6; B + Crimson Pro j 10.27 / 88.5 / 88.4 / 78.0; C + our lighter j 9.46 / 89.4 / 87.8 / 90.2; D + Source Serif j 11.48 / 88.2 / 87.8 / 68.7. Page https://claude.ai/artifact/JxNKAGK7qA38MAUD93roHc (`out/golden/fgj_final.png`).

### Lowercase cleanup by un-averaging (James, 2026-10-12)

James rejected all f g j options ("TERRIBLE"), asked for our own letters drawn cleanly ("resemble our letters, but not look like a sloppy mess"), pointed at the q (notch where bowl meets stem, lump at the bottom, foot sticking out), and asked about a cleanup skill (none exists; a skill is instructions, not a capability). Tried: constructing f g j q from parts of our i and o with drawn hooks and arches (`scripts/construct_lc.py`, skia-pathops added): q clean, but hooks and ball ends looked mechanical ("worse and worse"); morphological cleanup (fill notches / shave bumps before tracing, `curve_outlines.py --close/--open`): joins went blobby. Cause of the mess: the lowercase is an equal SDF blend of IBM Plex Serif, Spectral and Gelasio, and where their joins and serifs differ the average has notches and lumps (b d h k m n p q r), plus the bitmap tracing. `scripts/unblend.py`: for each letter, each source's real outline fitted to our glyph's ink box; the closest (overlap / union of ink) replaces ours (q Gelasio, r Plex, n Plex, m Spectral, d Gelasio, b Spectral, p Plex, h Plex, k Spectral, c Spectral, e Plex, u Spectral, v Gelasio, w Spectral, y Gelasio, f Spectral, j Gelasio, g Gelasio fitted by height only). Looks clean and coherent at our sizes. Quick test (`unblend_quick.csv`, these letters oversampled): error 8.29 -> 10.70; g 95.7 -> 85.3, j 90.2 -> 74.0, n 97.0 -> 93.4, h 97.2 -> 93.5, r 96.2 -> 93.6, others within ~1.5. Page https://claude.ai/artifact/4UL5H8TJWZn2buupoWw4zE. Full checks running.

### Deliberate outline edits (James, 2026-10-12)

James: "NO. YOU TOOK ANOTHER FONT" (un-averaging dropped), "STOP RUNNING CHECKS!! STOP COMPARING ACCURACY!", "as long as it looks like a child's chicken scratch it is NOT useful". Work now on our own outlines only, judged by looking (outline view with on-curve points black, handles red: `scratch/outline_view.py`), no accuracy runs during look work (memory: looks-first-no-checks). `scripts/glyph_edit.py mirror_foot` (James: "bottom right of the f should mirror bottom left. Same with foot of q"): the stem centre from a slice through the stem, the kept half of the foot mirrored across it, joined by boolean union. `scripts/fair_outlines.py` redraws a glyph's outline: corners kept (turn measured over a short and a longer stretch), V-shaped shallow notches dropped as corners (square inside corners kept), stems straight (long runs; short straight runs only at corners), curved stretches smoothed and drawn one curve per quarter between extremes (James: "on a circle there should be 4 black dots and a few red dots ... on the OUTSIDE of the g you have many black dots which flattens the left edge for NO REASON"), split only when one curve misses by more than 12 units. Base: a crisp trace of v0.9 (`curve_outlines.py --open 8 --close 8`, no blur: slivers from blended ghost serifs shaved, corners not rounded), f and q feet mirrored (`~/maxocr-work/keep/crisp_e1.ttf`), g redrawn (`crisp_e2.ttf`).
James on the redrawn g: "I asked you to clean up and simplify the shapes, then you add weird soft edges, changed the shape, made it harder to read AND uglier" (arrows on the dip, rounded ear, bottom-right point, soft hook end). `fair_outlines.py` default is now shape-keeping: no smoothing, every corner kept (inside corners included), curves follow the outline within 3 units, straight runs only at corners or when stem-long (150+); closed loops without corners (counters, o, dots) are drawn like circles: one point mid-side at left, top, right, bottom, one curve per quarter (James: "inside of the circle on the left is still screwed up"). James: "g is right". All glyphs cleaned this way from the mirrored-feet version (`~/maxocr-work/keep/clean_all.ttf`). The j kept its wavy, thickening stem and slab hook (shape, not outline), so it is rebuilt from our own shapes (`scripts/j_from_f.py`): our i's head serif, a stem as wide as the i's, and our f's top arch rotated half a turn as the hook; dots of i and j made perfect circles centred over the stem (James); the j gets the i's right-side spacing (`clean_jf.ttf`).
James: j "much better, but has a sharp corner" where stem meets hook; "f is still too bold"; "the left and right arms of the f should be symmetric"; "arms should be FLAT at the top and bottom, with a subtle rounded end"; "dot of the i and j should be centered over the stem". Done: the j's hook now comes from the f's own stem and arch as one piece (crossbar removed), joined to an i-width stem, light smoothing (12 units) only on i and j so the joins flow (`fair_outlines.py --corner/--smooth`); the f is lightened from the sides only (`curve_outlines.py --erode-x 12`: stems lose 24 units, crossbar and arch keep their thickness) and spaced so its longer left arm keeps the old left sidebearing (`scratch/keep_lsb.py`); `glyph_edit.py flat_bar` replaces the crossbar with one flat-topped, flat-bottomed bar, symmetric about the stem at the longer arm's length, corners rounded by 0.3 x thickness; dots are perfect circles centred on the stem as measured below the head (i stem 127-219, dot centre 172; j stem 127-216, dot centre 172). `~/maxocr-work/keep/clean_v5.ttf`.
James: "left arm of f is now longer than right" (measured equal, 195 units each side of the stem; the arch above leans right, so equal arms look unequal) -> `flat_bar --left-trim` (optical correction: 15 and 30 units shown). James: "why is there a notch?" (a sliver of the old, taller rounded bar end poked out of the new, shorter bar). `flat_bar` now removes the old bar with its rounded ends and brackets (14 units above and below) beside the stem, and continues the arch's own edges straight down along their slope onto the bar (no flare, no vertical cut, no kink).
James: "30" (left arm 30 units shorter looks even). Working font `~/maxocr-work/keep/clean_v6.ttf` (copy `out/golden/clean_v6.ttf`). Full alphabet before / after the cleanup: `scratch/alphabet_before_after.png`.

### Hand-style redraw from chosen nodes (2026-10-12)

Every letter blown up, messy spots circled (https://claude.ai/artifact/EDKFUZRpgxAxirum4qgAr3, `scratch/messy_spots.png`): lumps, notches and wobbles that are in the shapes themselves (not the outline drawing), so smoothing does not remove them (smoothing 20 / 40 tried on 8 4 6 G M k d O: lumps stay, M grows spikes; `scratch/smooth_try.png`). `scripts/redraw.py` cleans a contour the way a type designer does by hand: only the nodes I pick are kept (extremes with horizontal or vertical tangents, corners, line ends), and each stretch between two nodes becomes one curve fitted robustly to our own outline (a lump inside the stretch does not pull it), one straight line, or a clean rounding (elliptical quarter between two tangents: brackets, rounded ends). Node specs per glyph in `scripts/nodes/*.json`. Digits redrawn: 8 (shoulder lump at lower left and notch in the lower counter gone), 4 (straight diagonals, flat crossbar of one thickness, straight stem, wavy blob foot replaced by a symmetric flared foot with small rounded corners, rounded bar end), 6 (smooth arm, one sharp joint where the arm meets the bowl, clean round terminal), 5 (straight stem, clean ball terminal), 0 (dent at the top left gone). `scratch/cmp_digits.png`.
Letters redrawn (`scripts/nodes/letters.json`, applied after the digits): M (stems straight, kept serifs; right diagonal's bump into the top serif smoothed), G (beak, jaw, crossbar serif, chin), O (two clean ovals; lower-left bulge gone), k (straight arm and leg, one rounded crotch, flag serif on the arm). James on the first d: "the top of the inside circle has a strange shape and there is a notch in the foot"; "the p does the attachment correct. the q and b are weird". p is the model: the counter's stem side straight with rounded corners about 125 wide and 130-150 tall, and the bowl meeting the stem low and shallow (about 33 units from the bowl's extreme). b, d and q redrawn that way: d's and b's counters get p's corners; d's bowl runs straight into its foot (no notch); b's stem rounds into its bowl at the bottom (no spike); q's bowl meets the stem low like p's, q's top spur redrawn clean. New span kinds: "k" keeps our original outline between two nodes, "s" a plain smooth curve.
a and u: their bowls run straight into the foot like d's (the notch between bowl and foot gone); a's bowl meets the stem in one clean corner. y: the knee where the thick arm turns into the tail is one straight edge and one rounding. N: the blob at the bottom right is a flat end with small rounded corners. Working font `~/maxocr-work/keep/clean_v7.ttf` (`out/golden/clean_v7.ttf`); before / after page https://claude.ai/artifact/E1VFDs7ko5PumECbvycpek (`scratch/redraw_before_after.png`).
James on the filled bottoms: "you changed the footer of a, b, d, and u. I don't hate the design, but I don't love it either. If it helps with accuracy, it can be a keeper." Third option, a small clean notch like p's (`scripts/nodes/feet_notch.json`: the bowl meets the stem about 30 units up, shallow, with a small rounding into the foot; `out/golden/v7_smallnotch.ttf`). Quick test (`cap_candidates.py`, 400 random lines, d a b u q p h n o c 6 oversampled; `feet_eval3.csv`), error / a / b / d / u read right: old messy 7.77 / 96.5 / 97.9 / 99.3 / 97.5; small notch 7.81 / 96.5 / 98.3 / 99.3 / 96.9; filled 7.90 / 95.0 / 98.6 / 99.3 / 96.6. All within a few errors of each other; the filled bottoms do not help accuracy. Page https://claude.ai/artifact/75m9Ewr6gZZEofbEE9Wqps (`scratch/feet_options.png`).
James: "i prefer the old notch". a, b, d, u get their old notch back, drawn cleanly (the deep V between bowl and foot, crotch 64-72 units up; b's pointed spur and shallow notch at the bottom left), counters stay as redrawn. Quick test (`feet_eval4.csv`), error / a / b / d / u: old messy 7.77 / 96.5 / 97.9 / 99.3 / 97.5; old notch cleaned 7.88 / 96.1 / 99.0 / 99.3 / 96.9 (within a few misreads). Working font `~/maxocr-work/keep/clean_v7b.ttf` (`out/golden/clean_v7b.ttf`).

### Full checks of the cleaned outlines (2026-10-12)

James: "are all chars cleaned up? should we run a comparison now for blurry? for grocery story...?" Punctuation looked at large: clean. Full checks of `clean_v7b.ttf` vs v0.9 (`scratch/v7b_checks.sh`; `text_eval_story_v7b.csv`, `confusions_pc_v7b*`, `vlm_clean_v7b*`), character error %: story s=0.5 4.78 -> 4.73, clean 2.00 -> 2.14 (EasyOCR 2.39 -> 2.79; the curve version alone was 2.65, so this is the curves, not the redraws); codes 8.89 -> 8.84; VLM prose 0.305 -> 0.248, codes 0.379 -> 0.568 (9 vs 6 errors), prose+codes 0.31 -> 0.28; VLM shuffled words 1.60 -> 1.99 (mostly 8 pt: 96 vs 62 errors; substitutions 0.13 -> 0.27%, spread thinly over t i e h o l n). Sheet with numbers https://claude.ai/artifact/A7PhUMS84ChJTWVy4LrASS (`scratch/v7b_checks.png`).

### v0.91 adopted (2026-10-12)

James: "Clean it is." Exported as version 0.91 (`scratch/export_v091.sh`; v0.9 in `out/fonts/intermediate/*-v09.ttf`): v0.9 with every outline cleaned (`~/maxocr-work/keep/clean_v7b.ttf`). Numbered 0.91, not 0.10: font versions are decimals (head.fontRevision), so 0.10 would read as older than 0.9. Specimen page updated (https://claude.ai/artifact/TrVjxydoADdpD2kbuTHU9N, `out/golden/v091_charset.png`, `scratch/specimen_v091.py`).
James: "Did we ever test vv/w?" Yes (capitals 2026-10-11, lowercase 2026-10-12, fixed by v w y sidebearings >= 40). Re-checked on v0.91 (`scratch/merge_v091.sh`; `merge_lower_v091.csv`, `merge_caps_v091.csv`; four engines, s=0.5), pair read as the single letter, v0.9 -> v0.91: vv/w 0.0 -> 0.0, VV/W 0.5 -> 0.5, rn/m 0.8 -> 1.0, cl/d 0.2 -> 0.0, ri/n 0.0 -> 0.0, in/m 0.0 -> 0.0; never split. w's right sidebearing moved 40 -> 38 in the cleanup (no effect). Page https://claude.ai/artifact/9my7eDTVwpvzuous8Xurge (`scratch/merge_v091.png`).

### Punctuation spacing (cleanup item 1; James: "Let's tighten the punctuation spacing and see what it does to the grocery story", 2026-10-12)

Marks borrowed from monospaced faces kept wide cells: sidebearings up to ~290 units (. ! ' about 285 each side, | 310) vs 20-50 for letters. `scripts/punct_spacing.py` caps each punctuation mark's left and right sidebearing (smaller ones untouched; letters, digits, space untouched). Grocery story (`text_eval_story_punct_tight.csv`, four engines, mean), blurry s=0.5 / clean: now 4.73 / 2.14; cap 120 4.59 / 2.29; cap 70 5.45 / 2.27 (EasyOCR 9.7 -> 11.6 and PARSeq 5.7 -> 6.4 blurry: marks too close to their neighbours blur into them). Page with numbers https://claude.ai/artifact/XdMCig1VFfKNyAChwrvKF9 (`scratch/punct_tight_numbers.png`).
James: yes (cap 120). Exported as version 0.92 (`scratch/export_v092.sh`; v0.91 in `out/fonts/intermediate/*-v091.ttf`): v0.91 + punctuation sidebearings capped at 120 units (`~/maxocr-work/keep/MaxOCR-Text-v092.ttf`). Specimen updated (`out/golden/v092_charset.png`, `scratch/specimen_v092.py`; VLM number still from v0.91).

### 6, 8 joints; g, t, O, Z fit (James, 2026-10-12)

James: b/d bowls "fine" (cleanup item 2 dropped). "6 and 8 look a little broken"; "g and t don't fit font family. There might not be much we can do about this if we want to maintain accuracy"; "O and Z just look off".
6 and 8 (`scripts/nodes/digits.json`): the 6's bowl top now runs into the arm almost level (joint at y 372 instead of 341, so the arm no longer hangs below the bowl as a point); the 8's lower counter top moved right and down with a clean quarter at its top left, so the lower loop's left stroke no longer thins to a hairline at the waist. Quick test (`eval_68.csv`, 6 8 G b B S 5 9 0 3 oversampled), error / 6 / 8 read right: now 9.77 / 94.0 / 88.4; fixed 9.59 / 94.0 / 93.0.
O and Z narrower (`scripts/gtOZ_parts.py`; O scaled in width, Z likewise), quick tests: O (`eval_O.csv`), error / O / 0: now 11.99 / 81.2 / 56.3; O at 80% width 11.59 / 82.6 / 58.7; O 70% 12.14 / 73.4 / 57.7. Z (`eval_Z.csv`), error / Z / 2 / z: now (1.4x a normal Z) 10.79 / 77.2 / 94.0 / 81.7; 1.2x 10.75 / 74.6 / 94.2 / 81.7; 1.1x 10.88 / 73.5 / 94.2 / 81.3.
g and t from our own parts (`scripts/gt_from_parts.py`): g = our q without its straight descender (bowl, stem, top spur) + our j's hooked descender widened to the q's stem width; t = stem as wide as our f's with a slanted top, our f's flat crossbar on the x-height, and a drawn round serif foot. A first try (j's hook unscaled, f's arch flipped as the t's foot) looked clumsy (flat bowl bottom, steps, heavy ball foot) and was dropped. Quick tests running.
g and t quick tests: g (`eval_g.csv`), error / g / q / 9: now 9.46 / 94.4 / 88.5 / 92.4; g from q + j 10.83 / 77.9 / 87.0 / 91.5 (g read as 9 45 times). t (`eval_t.csv`), error / t / f: now 11.53 / 95.0 / 95.4; drawn t 11.94 / 89.3 / 94.8. The family-style g and t fit the look but cost accuracy, as James expected. Page with every option and its numbers https://claude.ai/artifact/WzkLzShZb6iFmVQHKJR1va (`scratch/fit_options.png`).
James: "6/8 better. Both still have room for improvement"; "O and Z both better". Working font `~/maxocr-work/keep/MaxOCR-Text-v093w.ttf` = v0.92 + 6/8 joints + O at 80% width + Z at 1.2x. Next 6/8 candidates (`scripts/digits_68.py`): 6 = our 9 turned half a turn (same box); 8 = two stacked clean rings on one axis, the size of our 8 (sides ~95, tops ~55 like our 0 and 3). Quick test running (`eval_68b.csv`).
