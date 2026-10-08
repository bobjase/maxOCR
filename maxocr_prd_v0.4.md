# MaxOCR Font: Product Requirements Document

Version: 0.4 (DRAFT)
Date: 2026-10-08
Owner: James
Status: DRAFT. Freezes Sections 6.5 and 7 from measured M1a data. Three items wait on the owner and are marked **[OPEN]**: per-cluster targets (7.4), co-best baseline handling (7.3), and the proposed context check (R13c). The document is frozen once those are decided.
Supersedes: v0.3.1

Changes from v0.3.1: environment via pixi on Ubuntu 26.04; PaddleOCR run as the official ONNX export with the output restricted to the corpus alphabet; CTC run definition corrected (R11a); Tesseract rank from confidence-sorted alternatives (R12b); Apple Vision omitted; R29 "no worse" made statistical; cluster rule gains share and rate floors (R22b); objective and gate clusters frozen (6.5); R27b reliability curve defined per glyph; Section 7 replaced by a relative operating-point rule after the 2% absolute target proved unreachable, and frozen at s = 0.5; severity defined as one dial over all R5 operators; R33c working copies share only node_modules; R37b allocation measured; R40b probe results; Inter dropped from baselines; font builds compared by content, not file hash; new risk that the engines' 0/O behaviour is a learned habit. Requirement numbering preserved; new requirements carry letter suffixes. Rationale and raw measurements: `DECISIONS.md`.

## 1. Problem statement

Unchanged from v0.3.1.

Off-the-shelf OCR engines confuse visually similar characters (0/O, 1/l/I, 5/S, 8/B, rn/m) when the input is degraded by blur, low resolution, ink bleed, compression, or poor thresholding. Existing machine-readable typefaces (OCR-A, OCR-B, MICR E-13B) were validated against 1960s template-matching hardware. No published work benchmarks them, or any typeface, against modern neural OCR engines under a systematic degradation sweep. No published work closes the loop and optimizes glyph geometry against a real OCR engine's confusion matrix.

**M1a finding that sharpens the problem:** both engines confuse 0 and O at close to chance on every baseline font, including fonts with a dotted or slashed zero, and do so on undegraded input. A small probe classifier separates the same glyphs almost perfectly. The confusion is how the engines read these glyphs, not ambiguity in the pixels.

## 2. Hypothesis

Unchanged from v0.3.1.

Under a stated synthetic degradation model, a Latin alphanumeric typeface whose glyph geometry is optimized against the degraded-input confusion matrix of off-the-shelf OCR engines will achieve materially lower within-cluster substitution rates than OCR-B and than leading programming fonts, at matched degradation levels, on an engine of a different architectural family that it was never optimized against, while remaining legible to human readers and no worse than baseline on clean input.

The claim is explicitly conditional on the degradation model. No claim is made about physical scans.

## 3. Goals

Unchanged from v0.3.1, except Goal 3 reads "beats every co-best baseline" (see 7.3).

1. Produce a baseline table and full severity-by-size curves: within-cluster substitution rates for the named baseline fonts across the degradation matrix on all engines with language modeling disabled.
2. Measure headroom: the estimated Bayes error per cluster per severity, the pixel-distance covariate, and how far each baseline font sits from the estimate.
3. Produce a font (TTF) that beats every co-best baseline at the pre-registered operating point.
4. Demonstrate that the gain transfers to a held-out engine of a different architectural family.
5. Demonstrate human legibility is not degraded relative to the baseline font.
6. Publish the harness, degradation banks, confusion matrices, build plans, and font builds so every claim is reproducible from one command.

## 4. Non-goals

Unchanged from v0.3.1.

## 5. Prior art and positioning

Unchanged from v0.3.1, with one caveat added to the writeup list:

5. M1a observed that the engines' within-cluster error on clean input is far above the probe-classifier estimate for every baseline, OCR-A and OCR-B included. Fonts designed for 1960s readers are not easier for these engines; OCR-A is the worst baseline on both.

## 6. Requirements

### 6.0 Operating environment

- R0. All harness code, engines, and font builds run in WSL2 Ubuntu (26.04 on the reference machine; the release is immaterial) on the reference machine (Intel Core Ultra 9 285K, RTX 4060 Ti 16 GB) with CUDA through the WSL driver. WSL is configured for 20 cores and 64 GB. Nothing runs on the Windows side. Python 3.12, Tesseract, Leptonica, Node, ONNX Runtime and PyTorch are pinned through a pixi lockfile (conda-forge), installed without root.

### 6.1 Rendering and the frozen raster contract

R1 to R4 unchanged. Clarifications:
- R1. Fonts may be addressed as `file.ttc#index` for collections.
- R3. Stem darkening is disabled for every FreeType driver through `FREETYPE_PROPERTIES`. Fractional pen-origin jitter is applied through FreeType's transform delta, so outlines are rasterized at the sub-pixel offset; pen origins are otherwise integer.
- R4a. Font builds are compared by content (all tables, all glyph outlines and advances), not by file hash: Iosevka embeds a build timestamp in `head`.

### 6.2 Degradation pipeline

- R5. Operators unchanged. Severity s is a single dial applied to per-instance uniform draws, so one instance at different severities shares its noise (common random numbers across fonts and severities). At severity s, per instance: ink spread s x U(0.5, 1.5) px (erosion instead in 25% of instances); rotation up to +/-3s degrees (clipped to +/-3); perspective corner offsets up to 2s% of the line; Gaussian blur sigma 1.2s x U(0.8, 1.2); downscale/upscale in 50% of instances, factor 1/(1 + 0.6s x U), nearest or bilinear; illumination gradient up to 60s grey levels; Gaussian noise sigma up to 10s; salt-and-pepper in 30% of instances, p up to 0.004s; JPEG quality 100 - 60s x U(0.8, 1.2), clipped to [5, 95]; suite (a) threshold: global Otsu offset up to +/-25s, or adaptive Gaussian in 30% of instances. Always: fractional origin jitter U[0, 1) px on both axes, point-size jitter +/-0.5 pt. Edge crop (R10b stratum): 20% of instances, 0-20% of cap height from one side.
- R6. Unchanged.
- R7. Banks: sweep bank (2,000 lines, seed 101, used for the M1a severity sweep); validation bank (5,000 lines, seed 202, sha256 `7644d190a6067344892df8551acf757a6434d6c40207fa6d91d8c6a6c9398fcb`); optimization bank (500 instances, resampled every 10 generations); test bank (50,000 instances, sealed; generated and hashed at M1b).
- R7a. Clean condition: integer pen origin, no jitter, no degradation; suite (a) is plain Otsu.
- R8 to R10b unchanged.

### 6.3 OCR engines

- R11. PaddleOCR PP-OCRv6 medium recognition model, the official ONNX export (Hugging Face `PaddlePaddle/PP-OCRv6_medium_rec_onnx`, revision `50c7eac`), run with ONNX Runtime on CUDA, pre-cropped single lines, detection bypassed. The engine's own input preprocessing is part of the engine. Output is restricted to blank plus the corpus alphabet and renormalized, mirroring Tesseract's whitelist. Tiny and small tiers run once on the sealed test bank as a robustness row.
- R11a. CTC per-character posterior: greedy decode; a run is a maximal span of frames with the same non-blank argmax (standard greedy collapse); runs align to ground truth via R17; the per-character posterior is the softmax at the maximum-confidence frame of the run. Never summed. Collapsed doubles are deletions.
- R11b. Inference runs in the parent process, one image at a time (batching pads images and changes outputs, breaking R4). ONNX Runtime CPU threads are limited to one with spinning disabled.
- R12. Unchanged.
- R12b. Rank is the 1-based position of the correct class among the ChoiceIterator alternatives sorted by confidence (measured: raw order is non-monotonic in ~2% of symbols), K+1 if absent; empty alternatives are dropped. Lower bound, stated. The `lstm_choice_mode=2` functional test passes.
- R12c. Tesseract workers run single-threaded. Thread limits are set in the environment before a worker starts (OpenMP reads them once at load); Intel OpenMP warnings are suppressed.
- R13, R13b unchanged.
- R13c. **[OPEN] Context check, measured only.** Once, on the sealed test bank: Tesseract with dictionaries on and PaddleOCR without the alphabet restriction, on real words and on format-constrained codes (VIN-style), to confirm gains do not reverse when the engine can use context. Not an optimization target.
- R14. Apple Vision omitted: no Mac available.
- R15. Unchanged.
- R15b. Unchanged; the oem 0 load test passes against the vendored legacy traineddata.
- R16. Open-source engines and weights pinned by package version, lockfile and file hash (sha256 recorded by `scripts/fetch_vendor.sh`).
- R17. Unchanged.

### 6.4 Test corpus

R18 to R21 unchanged. The primary corpus uses 20% length-1 strings and forces a double in 15% of longer strings. Surveys may oversample characters with explicit weights; the frozen banks are unweighted.

### 6.5 Confusion clusters (frozen)

- R22. Derivation per engine on the validation bank at the operating point, primary alphabet, suite (a), uncropped.
- R22a. Objective clusters are PaddleOCR's, gate clusters Tesseract's, union published (`out/report/cluster_union.csv`).
- R22b. An edge c->d is included when (1) it is significant against the uniform-error null for c (one-sided binomial, Bonferroni over all directed pairs, alpha 0.01), (2) it carries at least 25% of c's errors, and (3) it occurs in at least 1% of c's occurrences. Floors (2) and (3) were added because, at these sample sizes, weak but consistent edges pass the test alone and chain most of the alphabet into one component (Tesseract at s = 0; both engines at s = 0.5). Stability is reported with both floors halved and doubled.
- R22c. **Frozen objective clusters (PaddleOCR):** {0, 8, B, D, E, O, Q}, {6, G, L}, {H, M, N}, {1, I}, {2, Z}, {5, S}, {9, A}, {U, W}. At doubled floors the first splits into {0, D, O} and {8, B}; the link is real (PaddleOCR reads 0 as 8 in 10.2% of cases).
- R22d. **Frozen gate clusters (Tesseract):** {1, 3, 9, I, J}, {0, D, O}, {2, Z}, {4, A}, {5, S}, {6, G}, {7, T}, {8, B}, {M, N}, {V, Y}.
- R23 to R25 unchanged.

### 6.6 Objective

- R26 to R28 unchanged.
- R27b. Reliability curve, per glyph: for each (font, character) in an objective cluster, the median R11a margin over the validation bank against that glyph's realized within-cluster error, with a weighted isotonic fit. (The per-instance curve is degenerate: the margin is read at the decoded run, so margin < 0 exactly when the instance is an error.) Measured: all six baselines fall on one curve; fitted error is below 1% from a median margin of ~9.4 and ~0 above ~11.3. Hinge = 1.5 x the smallest median margin whose fitted error is below the per-cluster target: 14.2 for targets of 0.5-1%, 13.8 for 2% (final value follows 7.4).
- R29. Clean floor, per character, evaluated on R7a: a candidate fails when it is statistically significantly worse than the rung parent on any primary-alphabet character on PaddleOCR or Tesseract (one-sided test). A strict point-estimate comparison is not used: with ~300 samples per character it rejects on noise.
- R29a to R31 unchanged.

### 6.7 Search

- R32, R32a, R33, R33b unchanged.
- R33c. One Iosevka working copy per build worker, each with its own build cache. Only `node_modules` is shared (hard links); the rest is copied, because a build compiles glyph code into `packages/*/lib` and shared files are overwritten by parallel builds. Worker count per R37b.
- R34 to R36 unchanged.

### 6.8 Compute budget (measured)

- R37. Measured on the reference machine: Iosevka subset rebuild after a glyph change 5.2-5.4 s alone (8-14 s under load); full-charset build 22 s; first build including compile 16.7 s alone, 197 s when 16 copies compile at once (one-time); render + degrade ~0.7-1.6 ms per line; Tesseract ~8 ms per line alone, ~13 ms with 16 workers; PaddleOCR ~3.2 ms per line on the GPU; end-to-end evaluation ~300 lines/s.
- R37b. Allocation: **8 build workers, 12 Tesseract workers.** A 32-candidate generation takes 63-70 s for every split from 4x16 to 16x4; PaddleOCR in the parent (~52 s per generation) is the bound.
- R38. Met: one generation (population 32, 500-image bank, builds included, worst-case gate) takes ~63 s against the 10-minute cap. A second PaddleOCR process is the next lever if the budget tightens.
- R39 unchanged.

### 6.9 Headroom and discriminability analysis

- R40. Measured (`out/report/r40_pixel_distance.*`): Spearman correlation between pair pixel distance (RMS, same degradation instance, grayscale) and pair substitution rate is -0.23 (s = 0), -0.44 (0.5), -0.60 (1.0) on PaddleOCR. A covariate only, as stated. OCR-A pairs are often confused despite large pixel distance.
- R40b. Probe classifier: 3-layer CNN, 54k training / 10.8k test glyph cells (middle character of 3-character strings), cropped stratum excluded, three seeds with the seed of lowest training error kept (never selected on test data); a seed is flagged as diverged when its training error exceeds the best seed's by more than 1 point. Within-cluster error at s = 0.5 with the frozen clusters: Source Code Pro 0.058%, IBM Plex Mono 0.044%, Iosevka 0.234%; every baseline was at or below 0.22% under the provisional clusters, OCR-A and OCR-B at 0.000%. At s = 1.0 (Source Code Pro): 3.3%.
- R40c, R41 unchanged.

### 6.10 Human legibility

Unchanged.

### 6.11 Reproducibility and release

- R45. `scripts/reproduce_m1a.sh` reproduces the M1a artifacts in one command (estimated 45-60 min; every step has run individually, the script has not yet been run end to end); `scripts/timing.py` reproduces the timing sheet separately. Every heavy step is time-capped and followed by worker cleanup.
- R46 to R47a unchanged.

## 7. Operating point (frozen)

### 7.1 Why the v0.3.1 procedure was replaced

Step 2 of v0.3.1 locks the severity at which the median baseline sits at 2% within-cluster substitution. Measured within-cluster rates at s = 0 are already 2.8-12.7% (PaddleOCR) and 8.4-19% (Tesseract), and never fall below that, so step 2 has no solution. The owner chose a relative rule. The PRD's order is kept: severity locked first, font chosen second, never interleaved.

### 7.2 Procedure (`scripts/operating_point.py`, `scripts/m1a_validation.py`)

1. Provisional clusters: PaddleOCR, sweep bank, s = 0, suite (a), uncropped, R22b rule.
2. Anchor font: lowest within-cluster rate at s = 0, averaged over the two engines. Result: **Iosevka**.
3. Lock severity: the first swept s at which the anchor's PaddleOCR within-cluster rate reaches 1.5x its s = 0 rate. Result: **s = 0.5**.
4. Final clusters on the validation bank at that severity (6.5).
5. Best baseline: lowest within-cluster rate at the locked severity, averaged over PaddleOCR (objective clusters) and Tesseract (gate clusters), validation bank, suite (a), uncropped.

A median-font anchor, as in v0.3.1, does not work with a relative rule: Tesseract's within-cluster rate barely grows below s = 0.5 and then falls as errors leave the clusters, and a PaddleOCR-only median only reaches 1.5x near s = 1.0, where the metric no longer measures confusability.

### 7.3 Frozen values

- Size 8 pt, 200 DPI. Severity **s = 0.5** with the R5 operator definitions above.
- Baseline table at the operating point, validation bank, uncropped; within-cluster % with all-character error % in brackets (PaddleOCR on objective clusters, Tesseract on gate clusters):

| Font | PaddleOCR (a) | PaddleOCR (b) | Tesseract (a) | Tesseract (b) |
|---|---|---|---|---|
| Source Code Pro | 3.59 (2.6) | 2.45 (1.6) | 13.32 (17.7) | 9.44 (10.0) |
| IBM Plex Mono | 4.06 (2.9) | 3.13 (2.0) | 13.28 (18.0) | 9.99 (9.7) |
| OCR-B | 6.30 (4.2) | 4.57 (2.9) | 12.45 (18.2) | 8.86 (8.9) |
| JetBrains Mono | 5.89 (4.1) | 3.85 (2.5) | 13.02 (19.3) | 9.71 (10.9) |
| Iosevka | 7.13 (6.0) | 3.46 (2.3) | 14.96 (29.6) | 9.61 (15.2) |
| OCR-A | 12.73 (9.6) | 7.80 (6.5) | 12.32 (27.4) | 9.82 (18.4) |

- Best baseline: **Source Code Pro** (two-engine aggregate 8.45%), with IBM Plex Mono 0.21 points behind.
- **[OPEN] Co-best rule.** Proposal: every font not significantly worse than the best counts as co-best, and MaxOCR must beat all of them; Source Code Pro is the reference for R40/R40b.
- Iosevka, the rung-0 parent, ranks 5th of 6 (aggregate 11.04%); on PaddleOCR its suite (a) rate is twice its suite (b) rate, so binarization hurts it most.

### 7.4 Per-cluster targets [OPEN]

The v0.3.1 rule (target = 2x the R40b estimate where that estimate exceeds 0.1%) gives the {0, 8, B, D, E, O, Q} cluster a target near 0.2% against a 3.6% baseline, i.e. closing ~95% of the gap by font changes alone, and leaves clusters with smaller estimates undefined. Proposal: targets as headroom closed (R41), **at least 50% of the gap between the best baseline and the R40b estimate, per objective cluster**, matching the 50% already used for transfer. Frozen once the owner decides.

### 7.5 Fixed regardless of outcome

Unchanged from v0.3.1: single operating point for search, full severity-by-size curve for reporting (M1b); transfer must close at least 50% of the remaining headroom on PARSeq that it closes on PaddleOCR, for length 1 and length 8+ separately; human non-inferiority within R43.

## 8. Success and stopping criteria

Unchanged from v0.3.1, with criterion 1 reading "per-cluster targets (7.4) met".

**M1a abort criterion 1 evaluated: not triggered.** At s = 0.5 the best baseline's within-cluster rate is ~60x the R40b estimate on PaddleOCR (3.59% vs 0.058%). Decision: **go**.

## 9. Risks

v0.3.1 table carried forward, with changes:

| Risk | Likelihood | Mitigation |
|---|---|---|
| No headroom at operating point | ~~High~~ **Retired**: headroom measured at 30-90x | — |
| Engines' 0/O behaviour is a learned habit that glyph geometry cannot move far | **High (new)** | Early evidence it can move: a dotted or slashed zero raises PaddleOCR's 0->0 accuracy from ~36% (OCR-B) to ~93% (Iosevka); a plain O is still read as 0 roughly 20-60% of the time depending on the font. Rung 0 tests this first; the Windows font survey looks for fonts that already succeed |
| The rung-0 parent (Iosevka) starts behind | **High (new)** | 5th of 6 at the operating point; rung 0 must close ~2.6 points to match the best baseline before beating it |
| Best baseline identity is fragile | Medium (new) | Near tie at the operating point; co-best rule (7.3) |
| Harness concurrency faults (thread oversubscription, orphaned workers, shared build files) | Medium (new) | R12c; `killWorkers.bat` / `scripts/kill_workers.sh`; R33c; every heavy run time-capped |

## 10. Deliverables

M1a delivered: environment; harness (render, degrade, align, evaluate, build orchestration); PaddleOCR and Tesseract wired, lstm_choice_mode and oem 0 tests passing; baseline sweep at 8 severities plus clean; validation bank; frozen clusters; reliability curve; R40 and R40b; timing sheet and R37b allocation; one-command reproduce script; this v0.4. Outstanding before freeze: the [OPEN] items. R2c invariants are implemented with candidate generation in M2.

M1b to M4 unchanged.

## 11. Baseline fonts

OCR-A (Debian `fonts-ocr-a` 1.0-12, public domain); OCR-B (Matthew Skala, CTAN `ocr-b-outline`, `ocrb10.otf`); Iosevka default subset build (same plan as candidates, v34.9.0); JetBrains Mono 2.304; IBM Plex Mono 2.5.0; Source Code Pro 2.042. All Regular. Inter dropped: proportional, complicates alignment, little go/no-go value.

Proposed addition (measurement only): a survey of the fonts installed with Windows on the reference machine (414 faces, 25 monospaced), rendered at matched capital height on PaddleOCR and Tesseract only (PARSeq stays held out), to find fonts the engines already read correctly and the glyph features that predict it. Fonts are read in place, never redistributed or copied into MaxOCR.

## 12. Milestones

Unchanged from v0.3.1. M1a exit criteria met except the v0.4 freeze, which waits on the [OPEN] items.

## 13. Open questions

1. Human study N. After the M4 pilot.
2. Per-cluster targets (7.4). Owner.
3. Co-best baseline rule (7.3). Owner.
4. Context check R13c: adopt or not. Owner.

## 14. Decision log

All v0.1 through v0.3.1 entries carried forward unchanged. New entries (details and measurements in `DECISIONS.md`):

| Date | Decision | Rationale |
|---|---|---|
| 2026-10-08 | Ubuntu 26.04 accepted; environment via pixi lockfile | Release immaterial; no root needed; lockfile pins everything |
| 2026-10-08 | PaddleOCR as ONNX export, output restricted to corpus alphabet | Clean access to per-frame softmax; same class set as Tesseract's whitelist |
| 2026-10-08 | CTC run = same-argmax span | Adjacent distinct characters often have no blank between them |
| 2026-10-08 | Tesseract rank from confidence-sorted alternatives | Raw order non-monotonic in ~2% of symbols |
| 2026-10-08 | Apple Vision omitted | No Mac |
| 2026-10-08 | R29 "no worse" is statistical | Strict comparison rejects on noise |
| 2026-10-08 | Severity is one dial over all R5 operators | Section 7 needs one axis |
| 2026-10-08 | Operating point by relative rule; s = 0.5 | 2% absolute target unreachable on clean input |
| 2026-10-08 | Cluster rule gains 25% share and 1% rate floors | Significance alone chains most of the alphabet at these sample sizes |
| 2026-10-08 | R27b defined per glyph | Per-instance curve is degenerate for CTC margins |
| 2026-10-08 | 8 build / 12 Tesseract workers | Measured; split barely matters, PaddleOCR bounds the generation |
| 2026-10-08 | Worker copies share only node_modules | Shared compiled files were corrupted by parallel builds |
| 2026-10-08 | Font builds compared by content | Build timestamp changes the file hash |
| 2026-10-08 | Inter dropped | Proportional; little value for go/no-go |
| 2026-10-08 | Abort criterion 1 not triggered: go | Headroom 30-90x the probe estimate |
