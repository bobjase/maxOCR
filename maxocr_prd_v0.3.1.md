# MaxOCR Font: Product Requirements Document

Version: 0.3.1
Date: 2026-09-14
Owner: James
Status: FROZEN. No edits until M1a exit, when v0.4 freezes Sections 6.5 and 7 from measured data.
Supersedes: v0.3

Changes from v0.3: legacy tessdata vendored separately for oem 0; CTC per-character posterior rule defined; Tesseract lstm_choice_mode and rank-margin lower-bound stated; acceptance gate runs on both suites; build invariants asserted programmatically; hard minimum ink-area fraction; parent glyph frozen per rung; ink-box tolerance set from rung 0 distribution; Pareto frontier logged; PatEL parameter blast-radius map required before rung 2; objective clusters from PaddleOCR, gate clusters from Tesseract; ceiling reframed as pixel-distance covariate plus probe-classifier Bayes-error estimate; candidate own-pair distance plotted; PARSeq dictionary-word control and length-1 transfer emphasis; M1 split into M1a and M1b; rung 0 search procedure specified; worker allocation measured; released TTF carries full character set. Requirement numbering preserved; new requirements carry letter suffixes.

## 1. Problem statement

Off-the-shelf OCR engines confuse visually similar characters (0/O, 1/l/I, 5/S, 8/B, rn/m) when the input is degraded by blur, low resolution, ink bleed, compression, or poor thresholding. Existing machine-readable typefaces (OCR-A, OCR-B, MICR E-13B) were validated against 1960s template-matching hardware. No published work benchmarks them, or any typeface, against modern neural OCR engines under a systematic degradation sweep. No published work closes the loop and optimizes glyph geometry against a real OCR engine's confusion matrix.

## 2. Hypothesis

Under a stated synthetic degradation model, a Latin alphanumeric typeface whose glyph geometry is optimized against the degraded-input confusion matrix of off-the-shelf OCR engines will achieve materially lower within-cluster substitution rates than OCR-B and than leading programming fonts, at matched degradation levels, on an engine of a different architectural family that it was never optimized against, while remaining legible to human readers and no worse than baseline on clean input.

The claim is explicitly conditional on the degradation model. No claim is made about physical scans.

## 3. Goals

1. Produce a baseline table and full severity-by-size curves: within-cluster substitution rates for the named baseline fonts across the degradation matrix on all engines with language modeling disabled.
2. Measure headroom: the estimated Bayes error per cluster per severity, the pixel-distance covariate, and how far each baseline font sits from the estimate.
3. Produce a font (TTF) that beats the best baseline at the pre-registered operating point.
4. Demonstrate that the gain transfers to a held-out engine of a different architectural family.
5. Demonstrate human legibility is not degraded relative to the baseline font.
6. Publish the harness, degradation banks, confusion matrices, build plans, and font builds so every claim is reproducible from one command.

## 4. Non-goals

- Training, fine-tuning, or providing custom traineddata for any OCR engine. Any result that requires engine training is a failure. The probe classifier in R40b is a measurement instrument, not an OCR engine, and is never used to read text or to score candidates.
- Vision-language model OCR (PaddleOCR-VL, GPT-class models). Their language priors cannot be disabled and would measure the prior, not the glyph.
- Non-Latin scripts.
- Aesthetic quality as a primary objective. Legibility is a constraint, beauty is not.
- Handwriting or scene text.
- Text detection and layout. The harness feeds pre-cropped single lines. Detection and segmentation are out of scope and are not measured.
- Optimizing punctuation. Punctuation is measured (6.4) but not optimized in this version.
- Physical capture of any kind. No printer, scanner, or camera is in the loop or in the evaluation.

## 5. Prior art and positioning

| Work | What it did | Gap relative to this project |
|---|---|---|
| OCR-A, OCR-B (ISO 1073), ISO 1831 | Machine-readable fonts with measured read rates and print-quality tolerances | Validated against 1960s hardware, not neural engines |
| MICR E-13B | Most empirically validated typeface in existence via bank reject rates | Magnetic plus optical, 14 glyphs, not general text |
| AnyOCR (Anyline, 2016) | Commercial machine-readable font designed from mobile OCR use cases | Designer-driven, no systematic optimization or published measurement |
| Font-vs-OCR benchmarks (Khmer, Devanagari, Tamil, historical Latin) | Compare existing fonts by Tesseract accuracy | Selection among existing fonts, not design; mostly non-Latin |
| Differentiable Variable Fonts (Parikh et al., 2025) | Gradient optimization in variable font axis space; legibility preserved by staying on the design manifold | Objectives were geometric and aesthetic, not recognition |
| Aalto thesis (parameterized vector font plus diffvg) | Optimized a parametric font against a perceptual ML model of human legibility under impaired viewing | Target was human perception, not a machine engine |
| GlyphGAN, VecGlypher | Use a recognizer's accuracy as a legibility metric for generated fonts | Recognizer as evaluation metric, not as optimization objective |
| Song and Shmatikov (2018), "Fooling OCR Systems" | Tiny L2 perturbations flip Tesseract LSTM output while invisible to humans; do not transfer to legacy Tesseract | Demonstrates that machine and human recognition diverge; motivates R15b and R40c |
| ZXX (2013), Ghost Font (2026) | Fonts designed to be human-readable and machine-unreadable | Inverse of this project; ZXX is now trivially read by modern models |

Positioning: this is the first closed-loop optimization of glyph geometry against real OCR engines under a degradation model, with a transfer test to a held-out engine of a different architectural family.

Caveats to be stated in the writeup:
1. Disabling dictionaries removes the engine's lexical prior, not its font prior. Engine training sets contain synthetic renders in many fonts. What we optimize against is residual prior mismatch, not a font-naive recognizer.
2. All degradation is synthetic. Operator ranges are bracketed against published scanned-document statistics (RVL-CDIP) as a sanity range only.
3. PARSeq is a scene-text model; 8 pt document-like crops are out of its training distribution. The transfer test asks whether the geometry survives a different inductive bias, not whether PARSeq is a deployment target. Its permutation language model cannot be disabled; random strings starve it but do not prove it inactive. See R13b.
4. Tesseract rank margins are lower bounds on rank (R12b) and therefore optimistic about safety.

## 6. Requirements

### 6.0 Operating environment

- R0. All harness code, engines, and font builds run in WSL2 Ubuntu 24.04 on the reference machine (Intel Core Ultra 9 285K, 24 cores, 96 GB RAM, RTX 4060 Ti 16 GB) with CUDA through the WSL driver. Nothing runs on the Windows side. Python 3.12, pinned via lockfile.

### 6.1 Rendering and the frozen raster contract

- R1. Render arbitrary strings from a font file at configurable point size and DPI to grayscale raster via FreeType (with HarfBuzz for shaping).
- R2. Fixed advance widths, fixed sidebearings, and a fixed maximum ink bounding box per glyph across all candidates. For Iosevka-derived candidates, sidebearings are pinned via metricOverride.sb.
- R2a. Ink-box tolerance is set from the measured distribution of ink boxes across the full rung 0 variant set: the 95th percentile per glyph. Exceeding it is hard rejection before evaluation.
- R2b. Hard minimum ink-area fraction: each candidate glyph must retain at least 85% of the parent glyph's ink area at the em scale. Hard rejection. Counter area and stroke contrast remain soft penalties under R31; ink area does not.
- R2c. Post-build invariant check, programmatic, before any rendering: hmtx advances equal to parent for every glyph; ink boxes within R2a tolerance; ink area within R2b; outline is non-self-intersecting. Any failure discards the candidate and logs the reason. No prose rule substitutes for this check.
- R3. Frozen raster contract, identical for every candidate, bank, and engine: FT_LOAD_NO_HINTING; stem darkening off; no LCD filtering; no subpixel positioning; integer pen origin except where jitter is applied by the degradation bank; pinned FreeType commit hash; pinned libjpeg-turbo commit hash.
- R4. Deterministic output given (font, string, size, DPI, bank instance).

### 6.2 Degradation pipeline

- R5. Operators, each parameterized: Gaussian blur; downscale then upscale (bilinear and nearest); JPEG compression; additive Gaussian noise; salt-and-pepper noise; morphological dilate and erode; rotation within plus or minus 3 degrees; mild perspective warp; uneven illumination gradient; global threshold at varying cutoffs; adaptive threshold; fractional-pixel origin jitter; point-size jitter of plus or minus 0.5 pt; edge crop of 0 to 20% of cap height at top, bottom, left, or right.
- R6. A degradation instance is a fully specified operator chain with fixed random seed.
- R7. Three banks: optimization bank (500 instances, resampled every 10 generations; may rise to 1,000 if R27 variance is high and R38 permits); validation bank (5,000 instances, frozen); test bank (50,000 instances, frozen, sealed until final evaluation). Sizes confirmed or revised after R37.
- R7a. Clean-condition set: a separate frozen set of at least 300 renders per character of the primary alphabet, integer pen origin, no jitter, no degradation. Used for R29 only.
- R8. Common random numbers: every candidate in a generation is evaluated against the identical bank instances.
- R9. Removed in v0.3. No physical samples.
- R10. Two input suites, both reported: (a) pre-binarized rasters; (b) grayscale rasters. Optimization signal runs on suite (a). The acceptance gate (R28) runs on both.
- R10b. Cropped instances are reported as a separate stratum and appear as a separate series on the R40 plots.

### 6.3 OCR engines

- R11. PaddleOCR PP-OCRv6 recognition model, medium tier, fed pre-cropped single-line images, bypassing detection. Primary optimization signal. Tiny and small tiers run once on the sealed test bank as a robustness row.
- R11a. CTC per-character posterior rule: greedy decode; segment the timestep sequence into non-blank runs separated by blanks; align runs to ground-truth characters via R17; the per-character posterior is the softmax distribution at the maximum-confidence frame within the aligned run. Posteriors are never summed across frames. A collapsed double (ground truth `00` decoded as one run) is a deletion, attributed by R17, and counted as an error for the deleted position; it is not assigned a margin.
- R12. Tesseract 5, LSTM mode (oem 1), tessdata_best from tesseract-ocr/tessdata_best, load_system_dawg=0, load_freq_dawg=0, tessedit_char_whitelist set to the corpus alphabet, psm 7, lstm_choice_mode=2. Acceptance gate per generation. tessdata_fast runs once on the sealed test bank as a robustness row.
- R12b. Tesseract rank margin: position of the correct class in the ChoiceIterator alternative list at the aligned position. If the correct class is absent from the list, rank is recorded as K+1 where K is the list length. Because ChoiceIterator enumerates alternatives along the chosen path only, this is a lower bound on true rank and an optimistic estimate of safety. Stated in the writeup. M1a includes a test confirming lstm_choice_mode=2 returns alternatives on degraded input before any gate depends on it.
- R13. PARSeq, base model, non-autoregressive decode mode, pinned commit and weights. Published held-out engine.
- R13b. PARSeq language-model control: once, on the sealed test bank, the same degradation instances are applied to dictionary-word strings of matched length, and PARSeq CER is reported alongside the random-string CER so the LM residual is visible. Transfer is reported for length-1 and length-8+ strata separately; length 1 is the cleanest architectural transfer test because the internal LM has no context to use.
- R14. Apple Vision, usesLanguageCorrection = false, supplementary snapshot holdout, macOS build recorded, omitted with a stated omission if no Mac is available.
- R15. EasyOCR recognition model, internal check only.
- R15b. Tesseract legacy engine (oem 0), internal inspection flag only, never a gate. Requires the legacy-compatible eng.traineddata from tesseract-ocr/tessdata (not tessdata_best or tessdata_fast, neither of which contains legacy engine data). The harness vendors both traineddata files under distinct paths and asserts at startup that oem 0 loads without error.
- R16. All open-source engines pinned by commit hash and weight-file hash, recorded in every results file.
- R17. Alignment: positional using known mono advance, edit-distance fallback for insertions and deletions, method recorded per string. Substitutions attributed only after alignment.

### 6.4 Test corpus

- R18. Primary alphabet: digits 0-9 and uppercase A-Z. Random strings.
- R18b. Secondary alphabet: digits plus mixed case. Measured, not optimized.
- R19. Stratified so every cluster and, in the secondary corpus, every digraph pair appears with controlled frequency and in varied neighbors. Doubles (`00`, `11`, `88`) appear at controlled frequency in the primary corpus.
- R20. Lengths 1 to 12. Reported separately for length 1 and length 8 or more.
- R21. Sealed punctuation set (. , : ; - _ / \ |) measured at baseline and final evaluation, not optimized.

### 6.5 Confusion clusters (frozen at M1a exit)

- R22. Cluster derivation, per engine, on the frozen validation bank at the operating point severity, primary alphabet, suite (a): directed substitution graph, edges above threshold (R22b), connected components.
- R22a. Roles: objective clusters are PaddleOCR's components. Gate clusters are Tesseract's components. The published table is the union, with edges marked as shared, PaddleOCR-only, or Tesseract-only. Rung 2 spends parameter budget on objective clusters only.
- R22b. Threshold rule: if a visible gap separates a small set of high-rate pairs from the mass near zero, the threshold sits in the gap. Otherwise, a pair is included when its rate is significantly above the uniform-error null for the source character (one-sided binomial test, Bonferroni-corrected, alpha 0.01). Stability under a 2x threshold change either way is reported.
- R23. Case pairs are a secondary-corpus matter and do not enter primary clusters.
- R24. Single-glyph and digraph clusters are separate objects. Digraph clusters arise only in the secondary corpus and are measured, not optimized.
- R25. Denominator is cluster-member occurrences; all-characters rate reported alongside.

### 6.6 Objective

- R26. Primary metric: expected within-cluster substitution rate over the bank.
- R27. Optimization signal: PaddleOCR per-character log-odds margin (R11a) between the correct class and the strongest in-objective-cluster competitor, hinged per R27b, aggregated over the optimization bank.
- R27b. Hinge rule: reliability curve of realized error versus margin on the validation bank baseline; hinge at the margin where realized error falls below the per-cluster target, times 1.5. Flat or non-monotonic curve means rank margin is used instead.
- R28. Acceptance gate, run on both suites (a) and (b): a candidate enters the elite only if its Tesseract rank margin on gate clusters and its R29 clean floor are no worse than the current elite's. Rejection on either suite is rejection. Cross-engine aggregation is worst-case on rank margin. Log-odds are never summed across engines.
- R29. Clean-condition floor, per character, strict, evaluated on R7a: the candidate must be no worse than the rung parent on every primary-alphabet character on PaddleOCR and Tesseract.
- R29a. Pareto logging: for every evaluated candidate, record (worst clean-character error delta, best objective-cluster margin gain). The frontier is reported at M3 so it is known whether R29 was binding. R29 remains the release rule regardless.
- R30. Shape-distance ceiling: Chamfer distance and IoU between candidate glyph and the rung parent glyph, hard ceiling, reported separately.
- R30a. The parent glyph for R30, R29, and R2b is frozen at the start of each rung. It is never the current elite. A sliding parent is prohibited.
- R31. Constraint handling: penalty with repair for soft constraints (counter area, stroke contrast band); hard rejection for R2a, R2b, R2c violations and self-intersection. Rejection rate logged; above 20% in a generation triggers parameterization review.

### 6.7 Search

- R32. Rung 0: exhaustive enumeration of Iosevka variants within each objective cluster (clusters are near-independent at this rung, so the space is per-cluster, typically a few hundred combinations), greedy coordinate ascent across clusters, one joint verification build of the assembled best set. Weight and width axes swept at the joint step only, subject to R2c. Every variant built once and cached.
- R32a. Blast-radius map, required before rung 2 begins: sweep each candidate PatEL parameter across its intended range with all others at default, build, and diff every glyph's outline against the default build with fontTools. The result is a matrix of parameter versus affected glyph. If any parameter affects glyphs in more than one objective cluster, those clusters are merged into one optimization block, and the block schedule in R33 is rewritten from the map. The map is a deliverable of M2.
- R33. Rung 2: CMA-ES over forked Iosevka PatEL stroke parameters for objective-cluster glyphs, 3 to 8 parameters per glyph, block-wise by cluster as determined by R32a, round-robin, with a final joint pass.
- R33b. Candidate build configuration: subset.include primary alphabet, one weight, one width, upright, noLigation, noCvSs, ttf-unhinted. Measured 18 s per rebuild on a slow single core; subset confirmed to skip glyph construction (59 s full-charset under the same plan).
- R33c. Parallel builds: one Iosevka working copy per worker, each with its own .build cache. Worker count set by R37b, not assumed to be 24.
- R34. Rung 3: measurement only, never released.
- R35. Rung 0 to rung 2 advancement: no validation improvement for 5 consecutive full sweeps or space exhausted.
- R36. Rung 2 saturation: no validation improvement for 20 consecutive generations at population 32. Confirmed or revised after R37.

### 6.8 Compute budget

- R37. M1a measures on the reference machine: Iosevka one-time compile; per-candidate build single-threaded and parallel; render time; per-operator degradation time; per-image inference for each engine with a persistent process. Projected wall-clock per candidate and per generation reported.
- R37b. Worker allocation is measured, not assumed: sweep build-worker count against Tesseract-worker count on a fixed generation and record wall-clock. The 24-core machine will not run 24 build workers and Tesseract concurrently without contention. Expect a split on the order of 16 build plus 8 inference; the measured optimum is recorded and used. If parallel node builds contend on disk or npm, cap build workers at 8 and accept the wall-clock.
- R38. Target: one generation, population 32, 500-image optimization bank, including builds, under 10 minutes. Preliminary estimate under 2 minutes. Population and bank size are negotiable; the 10-minute cap is not.
- R39. Validation on elite only per generation; test bank once at the end.

### 6.9 Headroom and discriminability analysis

- R40. Pixel-distance covariate: for each cluster and severity, the worst confusable pair from the best baseline font is rendered, degraded, and compared by L2 and normalized cross-correlation at the frozen pen origin and baseline of R3. No re-centering of bounding boxes. Plotted against realized substitution rate. This is reported as a covariate, not as a bound.
- R40b. Bayes-error estimate: for each severity level, a small probe classifier (a CNN of a few layers) is trained on degraded renders of the primary alphabet from the best baseline font, with the degradation model as the data generator, and its held-out per-cluster error rate is reported as the estimated achievable floor for that severity. The probe is trained per severity on the baseline font only, is never shown a candidate during optimization, and is never used to score candidates. It exists to answer whether the engines are near what any classifier could do. Its estimate is optimistic (it sees the exact degradation distribution) and is labeled as such.
- R40c. Candidate own-pair distance: for every elite at M3, the same L2 and NCC as R40 are computed on the candidate's own worst pair. Plotted against the candidate's substitution rate. A candidate that lowers substitution rate at constant or decreasing pixel distance is exploiting the engine rather than separating the glyphs, and is flagged together with the R15b legacy check.
- R41. Achieved rates reported as fraction of headroom closed, where headroom is baseline rate minus the R40b estimate.

### 6.10 Human legibility

- R42. Specimen sheet at every milestone.
- R43. Human study as in v0.3: five-reader pilot, power analysis, paired design, primary alphabet, severity set so baseline human CER is 5% to 20%, CER primary, response time secondary, 2 pp non-inferiority unless pilot variance forces a recorded change.
- R44. Constraint check, not a legibility claim.

### 6.11 Reproducibility and release

- R45. All configs, seeds, engine and weight hashes, FreeType, libjpeg-turbo, and Iosevka commit hashes, build plans, and font builds committed. One command reproduces the M1a artifacts.
- R46. Results stored as per-character confusion matrices per engine, per suite, per severity, per length stratum, per crop stratum.
- R47. Release form: both the Iosevka build plan and a built family named MaxOCR under OFL 1.1.
- R47a. The released TTF is a full-charset build: primary alphabet, secondary alphabet, and punctuation, with the optimized glyph parameters applied to the objective-cluster glyphs and Iosevka defaults elsewhere. The search-time subset build is never the release artifact. The release is unhinted; any hinted rasterization is outside the claim and stated as such.

## 7. Pre-registered operating point (frozen at M1a exit)

Procedure:
1. Build the baseline table on the primary alphabet, suite (a), PaddleOCR and Tesseract, at one size and a severity sweep (M1a scope).
2. Lock the severity at which the median baseline font sits at 2% aggregate within-cluster substitution. At that locked severity, the best baseline font is the one with the lowest aggregate rate averaged across the two engines. Severity is locked first; the font is chosen second; the two steps are not interleaved.
3. Find the severity at which the best baseline font shows between 1% and 5% on both engines. This is the operating point severity.
4. Run R40 and R40b at that severity. If the R40b estimate for any objective cluster is above 0.1%, that cluster's target is 2x the estimate, recorded.
5. Freeze size, DPI, operator chain, and per-cluster targets. Write them into this section in v0.4.

Placeholder until step 5: 8 pt at 200 DPI; Gaussian sigma 1.2; JPEG quality 40; dilate 1 px; jitter per R5.

Fixed regardless of outcome:
- Single operating point for search; full severity-by-size curve for reporting (M1b).
- Transfer: the candidate must close at least 50% of remaining headroom (R41) on PARSeq that it closes on PaddleOCR, reported for length-1 and length-8+ separately.
- Human: non-inferior within the R43 margin.

## 8. Success and stopping criteria

Done when all hold:

1. Per-cluster targets met on validation, confirmed on the sealed test bank, suite (a), primary alphabet.
2. Suite (b): no regression versus parent.
3. R29 clean floor holds on the R7a set at final evaluation.
4. Transfer criterion met on PARSeq at both length strata.
5. Off-diagonal mass no longer concentrated in objective clusters.
6. Headroom closed (R41) reported per cluster.
7. Human non-inferiority met.
8. Length-1 and length-8+ both show the gain.
9. Secondary alphabet and punctuation: no regression versus parent.
10. R40c shows the candidate's own pair distance increased relative to the parent for every objective cluster where substitution rate improved.

Abort and redirect:

- M1a: best baseline is within noise of the R40b estimate at the operating point: benchmark paper, stop after M1b.
- Rung 0 meets targets: publish variant table and font, do not proceed to rung 2.
- Transfer closes under 50% of headroom: back down a rung and simplify.
- R15b legacy regresses while LSTM improves on two consecutive elites, or R40c shows gain at constant pixel distance: inspect for engine-specific artifacts before continuing.
- R30 binding on every improving step: parameterization exhausted, stop.
- R31 rejection above 20% after parameterization review: design space wrong, redesign.
- R32a blast-radius map shows coupling across all clusters: block-wise CMA-ES is invalid; switch to joint optimization or stop at rung 0.

## 9. Risks

| Risk | Likelihood | Mitigation |
|---|---|---|
| No headroom at operating point | High | M1a gate; R40b estimate; abort criterion 1 |
| Gain only in the tail | High | Operating point targets the tail; full curve reported |
| Synthetic model resembles no real capture path | High, accepted | Claim scoped; stated |
| Optimizer exploits engine-specific features | Medium | PARSeq holdout, R15b flag, R40c own-pair distance, R30 with frozen parent, R29, rung 3 never ships |
| Optimizer thins strokes or opens counters to widen gaps | Medium | R2b hard ink-area floor; R2a hard ink box; R2c programmatic assert |
| PatEL parameters couple across clusters | Medium | R32a blast-radius map before rung 2 |
| Tesseract rank margin misses off-path confusions | Medium | lstm_choice_mode=2; K+1 rule; stated as lower bound; M1a functional test |
| Engine-internal binarization confounds | Medium | Two suites; gate on both |
| PARSeq LM residual masks transfer | Medium | R13b word control; length-1 stratum |
| Rung 0 captures nearly all gain | Medium | Acceptable; abort criterion 2 |
| M1 too heavy to reach a go/no-go quickly | Medium | M1a/M1b split |
| Worker contention breaks the generation budget | Low | R37b measured allocation |
| oem 0 fails to load against best/fast tessdata | Would be certain if unaddressed | R15b vendors legacy tessdata; startup assert |
| Engine version drift | Low | Hash pinning |

## 10. Deliverables

1. M1a: environment; harness (render, degrade, align, evaluate, build orchestration, R2c invariants); PaddleOCR and Tesseract wired including lstm_choice_mode test and oem 0 load test; baseline table at one size across a severity sweep; R40 and R40b at candidate operating point; cluster graphs per engine; reliability curve; timing sheet and R37b allocation; v0.4 with frozen 6.5 and 7.
2. M1b: full severity-by-size curves; PARSeq, EasyOCR, legacy Tesseract, Apple Vision if available; secondary alphabet and punctuation baselines; sealed test bank generated and hashed.
3. M2: rung 0 result font, build plan, comparison; R32a blast-radius map.
4. M3: rung 2 result font, build plan, comparison, transfer test with R13b control, R40c plot, R29a frontier; rung 3 measurement if reached.
5. M4: pilot, pre-registration, human study results, writeup, reproducibility package, R47a release build.

## 11. Baseline fonts

OCR-A; OCR-B; Iosevka default build (same subset and configuration as candidates); JetBrains Mono; IBM Plex Mono; Source Code Pro; Inter at matched x-height.

## 12. Milestones

| M | Content | Exit criterion |
|---|---|---|
| M1a | Go/no-go | One command reproduces the baseline table, per-engine cluster graphs, R40 and R40b at the candidate operating point, reliability curve, and timing sheet; lstm_choice_mode and oem 0 tests pass; v0.4 written with frozen 6.5 and 7; abort criterion 1 evaluated |
| M1b | Full baseline | Severity-by-size curves on all engines and both alphabets; sealed test bank hashed |
| M2 | Rung 0 | Best variant set; validation gain per sweep; R32a map; abort criterion 2 evaluated |
| M3 | Rung 2 | Targets met or saturated; transfer with control; R40c; R29a; rung 3 measurement if applicable |
| M4 | Human study and writeup | Pilot; pre-registration; non-inferiority result; specimen; release build; package |

The M1a decision artifacts: baseline substitution versus severity (plot 1); pixel distance and R40b estimate versus realized rate (plot 2). Flat plot 1 across fonts: stop. R40b estimate above target: change the target, not the glyphs.

## 13. Open questions

1. Human study N. After the M4 pilot.

## 14. Decision log

(All v0.1 through v0.3 entries carried forward unchanged; see v0.3. New entries:)

| Date | Decision | Rationale |
|---|---|---|
| 2026-09-14 | Legacy tessdata vendored separately for oem 0 | best and fast traineddata contain no legacy engine data; oem 0 fails fatally against them |
| 2026-09-14 | CTC posterior is the max-confidence frame in the aligned non-blank run; never summed; collapsed doubles are deletions | Emissions smear under degradation; summing inflates evidence |
| 2026-09-14 | lstm_choice_mode=2; absent class is rank K+1; rank margin stated as lower bound | ChoiceIterator enumerates the chosen path only |
| 2026-09-14 | Acceptance gate runs on both suites | Leptonica Otsu otherwise unmeasured |
| 2026-09-14 | Build invariants asserted programmatically (R2c) | Prose rules do not stop a width-axis advance change |
| 2026-09-14 | Hard 85% ink-area floor; ink-box tolerance from rung 0 95th percentile | Soft penalty on the thing the optimizer most wants to cheat produces skeletons |
| 2026-09-14 | Parent glyph frozen per rung | Sliding parent lets the shape leave the letterform in small legal steps |
| 2026-09-14 | Pareto frontier logged, R29 unchanged as release rule | Know whether the constraint binds without relaxing it |
| 2026-09-14 | Blast-radius map required before rung 2 | Iosevka parameters are a shared geometry graph; block-diagonal assumption must be verified |
| 2026-09-14 | Objective clusters from PaddleOCR, gate clusters from Tesseract, union published | Prevents spending rung 2 budget on engine-private edges |
| 2026-09-14 | R40 reframed as covariate; R40b probe classifier estimates Bayes error; R40c candidate own-pair distance | Pixel L2 is not a bound on neural discriminability; own-pair distance separates geometric gain from engine exploitation |
| 2026-09-14 | Probe classifier permitted under the no-training rule | It is a measurement instrument, never an OCR engine, never scores candidates |
| 2026-09-14 | PARSeq word-string control; length-1 as cleanest transfer stratum | Internal LM cannot be disabled; length 1 gives it nothing to use |
| 2026-09-14 | M1 split into M1a (go/no-go) and M1b (full baseline) | Abort after M1a costs a week, not six |
| 2026-09-14 | Rung 0 is per-cluster exhaustive plus greedy across clusters | Clusters near-independent at rung 0; 10^6 figure overstated |
| 2026-09-14 | Worker allocation measured (R37b) | 24 build workers starve Tesseract |
| 2026-09-14 | Released TTF is full-charset, unhinted | Subset build is a specimen, not a font |
| 2026-09-14 | Rejected: legacy Tesseract as a gate | Would optimize toward 1960s features |
| 2026-09-14 | Rejected: summed CTC posteriors | Inflates evidence under smeared emissions |
| 2026-09-14 | Document frozen until M1a exit | Further edits without measured data are churn |
