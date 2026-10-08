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
| 2026-10-08 | Sec. 7 | Severity is one dial s in [0, 1+] scaling all operators together; s = 1 is the Section 7 placeholder chain | Section 7 needs a single severity axis to sweep |
| 2026-10-08 | R29 | "No worse" means not statistically significantly worse (one-sided test), not a strict point-estimate comparison | With ~300 samples per character, a strict rule rejects good candidates on noise |
| 2026-10-08 | R11 (sizing) | Each engine's own input preprocessing is treated as part of the engine | Simplest faithful use of off-the-shelf engines |
| 2026-10-08 | Sec. 11 | OCR-B source: Matthew Skala's free OCR-B. Inter dropped from M1a | Free licence; Inter is proportional and complicates alignment for little go/no-go value |
| 2026-10-08 | R33 | Iosevka fork base: v34.9.0 | Latest stable release |
| 2026-10-08 | Sec. 7 | Operating point by relative rule (user decision). Best baseline = lowest within-cluster rate averaged over both engines and s in [0, 0.5] (suite a, uncropped, PaddleOCR clusters). Operating point = first swept s where its PaddleOCR within-cluster rate >= 1.5x its s=0 rate. Result: Source Code Pro, s = 0.5 (PaddleOCR 4.51% vs 2.81% clean; Tesseract 13.64%) | The 2% absolute target is unreachable: every font exceeds it at s=0 |

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

Small CNN (3 conv layers), 54k train / 10.8k test, middle glyph of 3-character strings, cropped stratum excluded, 3 seeds with the lowest-training-error seed kept (selection never uses test data). Clusters are the PaddleOCR objective clusters.

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

## Open questions for James

1. **Per-cluster targets (Section 7 step 4).** The rule "if the R40b estimate is above 0.1%, target = 2x the estimate" gives Source Code Pro at s=0.5 a {0,O,D} target of 0.22% (estimate 0.111%) and leaves the other clusters with no stated target (estimates at or below 0.1%). The PaddleOCR baseline is 4.5%, so a ~0.2% target means closing ~95% of the gap with font changes alone. That is probably unreachable and would make the success criterion meaningless. Proposal: express targets as a fraction of headroom closed (R41), e.g. "close at least 50% of the gap between the best baseline and the probe estimate, per objective cluster". That matches the 50% figure the PRD already uses for the transfer test. Needs your call.
2. **Context check (proposed addition, measured only).** Evaluate fonts with context available (Tesseract dictionaries on, PaddleOCR with no alphabet restriction, real words and format-constrained codes such as VIN-style strings) to confirm gains don't reverse when an engine can use context. Not an optimization target. Extends the PRD's existing R13b word control. Note: VINs already exclude I/O/Q and UPCs are digits-only, and most measured confusions are digit-vs-letter, so the expected gain is largest for unconstrained alphanumeric codes (serials, licence keys, part numbers).

## Early timings (reference machine, single build, Iosevka v34.9.0 @ 2487637)

| Step | Measured | PRD assumption |
|---|---|---|
| First subset build incl. one-time compile | 16.7 s | — |
| Subset rebuild after a glyph change (candidate cost) | 5.2–5.4 s | 18 s (R33b) |
| Full-charset build | 22.1 s | 59 s (R33b) |
| PP-OCRv6 medium rec, one 8-char line, GPU, unbatched | ~3 ms | — |

Verified that a variant change alters only the target glyph's outline and leaves advances at 500. The subset build's cmap holds 56 code points (36 requested plus Iosevka's required extras). The ~5 s candidate cost is mostly fixed tool startup, so parallel workers (R33c) should scale well. R38's 10-minute generation budget looks comfortable.
