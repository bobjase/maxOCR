# To ask James

Judgement calls made while James was away (glyph sweep, started 2026-10-16). Newest at the bottom.

## Ground rules I set

1. **Licences.** Only OFL fonts (vendor/ofl, 80 families) are used as donors. Installed commercial fonts (Arial,
   Calibri, Georgia, Segoe, Helvetica …) are compared against, never copied.
2. **Keep rule.** A donor glyph is kept only if the full 27-test benchmark average improves, MaxOCR stays #1 or #2 in
   every test, and the glyph does not look out of place next to our other letters.
3. **Screen.** Each character is first screened against all 80 donors on 100 lines (clean + damaged; lowercase on
   paragraphs, capitals on codes + paragraphs, digits on numbers + codes, punctuation on paragraphs), four engines.
   The best (up to 3) that look right get the full 27-test run.
4. Each donor glyph is fitted into our glyph's box and matched to our ink weight (same as the 3 and the e).

## Questions

1. **Noise threshold.** One swapped letter moves the 27-test average by only a few hundredths, which is close to
   luck. I keep a swap only if the overall average improves by at least 0.02 points. Too strict or too loose?
2. **Fitting to the test.** Swapping many letters, each chosen because it scored a little better on the same test
   text, risks tuning the font to this benchmark. Accepted swaps are combined and re-tested together; a print-and-scan
   check on paper would be the real proof.
3. **Screen order.** Characters are screened against the font as it was when the sweep started (v0.99.4); accepted
   swaps are combined and re-tested in batches, not one at a time.
