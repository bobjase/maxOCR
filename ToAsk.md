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
4. **Near misses.** The s from Carlito improved the overall average by 0.016 (threshold 0.02), so it was not kept.
   Worth a second look if you think the threshold is too strict.
5. **Two-storey g.** The best g's in the screen (Unna, Newsreader) are two-storey (the "eyeglass" g), while ours is
   one-storey. I'm testing Unna's g anyway; if it wins it changes the font's look more than other swaps. Kept only if
   the gain is clear, and flagged here either way.
6. **Broken donors.** Libre Bodoni's k fell apart when fitted to our weight (its hairlines vanish), so it was skipped.
7. **Rare letters.** x, q, z (and likely j, X, Q, Z) are too rare in the test text for any swap to show a
   difference. I left them unchanged. A test text rich in those letters would be needed to judge them.
8. **Size by H.** The benchmark gives every font the same capital height, measured on its H. A taller or shorter H
   changes the size of the whole font in the test, so H swaps must keep the exact height (now enforced). Worth knowing
   if we ever redraw the H by hand.
9. **W and C were hand-fixed by you.** You spent care on the W (straight edges, round bottoms like the V) and the C
   top. Donor W's and C's are being tested; if one wins it would replace your fixes. I'll only keep one if the gain is
   clear, and list it here so you can veto it.
