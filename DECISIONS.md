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
