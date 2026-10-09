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

## Open questions for James

1. **Per-cluster targets (Section 7 step 4).** The rule "if the R40b estimate is above 0.1%, target = 2x the estimate" gives Source Code Pro at s=0.5 a {0,O,D} target of 0.22% (estimate 0.111%) and leaves the other clusters with no stated target (estimates at or below 0.1%). The PaddleOCR baseline is 4.5%, so a ~0.2% target means closing ~95% of the gap with font changes alone. That is probably unreachable and would make the success criterion meaningless. Proposal: express targets as a fraction of headroom closed (R41), e.g. "close at least 50% of the gap between the best baseline and the probe estimate, per objective cluster". That matches the 50% figure the PRD already uses for the transfer test. Needs your call.
2. **Context check (proposed addition, measured only).** Evaluate fonts with context available (Tesseract dictionaries on, PaddleOCR with no alphabet restriction, real words and format-constrained codes such as VIN-style strings) to confirm gains don't reverse when an engine can use context. Not an optimization target. Extends the PRD's existing R13b word control. Note: VINs already exclude I/O/Q and UPCs are digits-only, and most measured confusions are digit-vs-letter, so the expected gain is largest for unconstrained alphanumeric codes (serials, licence keys, part numbers).

3. **Best baseline is a near tie.** At the operating point Source Code Pro (8.45%) leads IBM Plex Mono (8.67%) by 0.21 points, and an earlier, mis-ordered version of the procedure ranked Iosevka first. Proposal: any font within noise of the best counts as co-best and MaxOCR must beat all of them; Source Code Pro is the R40/R40b reference.
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
