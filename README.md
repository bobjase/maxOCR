# MaxOCR

A font for text that people read and machines read back: receipts, labels, invoices, forms, serial numbers, anything
that will be scanned, photographed or faxed and then run through OCR. It looks like an ordinary serif book face,
but every character is shaped and spaced so that OCR engines confuse it with as few other characters as possible.

![MaxOCR character set](docs/specimen.png)

**Version 0.99.20.** 95 characters: A–Z, a–z, 0–9, space and all 32 ASCII punctuation marks, plus the Hebrew
alphabet (27 letters) and the Russian Cyrillic alphabet (66 letters).

## Which file to use

The fonts are in the [fonts](fonts) folder.

| File | Use it for |
|---|---|
| [`MaxOCR.ttf`](fonts/MaxOCR.ttf) | **Start here.** Everyday text, codes and numbers. Adapts to what it is printing: a little extra space where letters meet digits and between the digits of numbers, and slightly smaller lowercase letters inside codes like `KRZgx2w`, so capitals and small letters are easier to tell apart. Applied automatically by apps that support OpenType features (browsers, design and most layout apps; in Word, turn on contextual alternates). |
| [`MaxOCR-Text.ttf`](fonts/MaxOCR-Text.ttf) | The same letters with plain spacing everywhere (no extra space between letters and digits). |
| [`MaxOCR-Small.ttf`](fonts/MaxOCR-Small.ttf) | Print smaller than about 7 pt (wider letter spacing; cuts errors by about 12% at 6 pt). |
| [`MaxOCR-Machine.ttf`](fonts/MaxOCR-Machine.ttf) | Machine-only work where looks do not matter: capitals, digits and space only. |

## How it compares

Character error rate (the share of characters an OCR engine gets wrong), averaged over nine print conditions from
crisp to badly damaged. Lower is better.

![Average character error by font](docs/benchmark.svg)

![Average character error by font and kind of text](docs/table_summary.svg)

Across all three kinds of text, MaxOCR makes **29% fewer errors than the next best font** (Courier New) and **about
half as many as Arial, Times New Roman or Helvetica**. The gap is largest on **numbers**: 2.9% against 4.4% for the
next best font.

The comparison set:

- **Windows:** Arial, Times New Roman, Calibri, Segoe UI, Verdana, Georgia, Consolas, Courier New. Arial, Times New
  Roman, Georgia, Verdana and Courier New also come with every Mac.
- **Apple:** Helvetica and Helvetica Neue. Apple's San Francisco and New York are not included: their licence allows
  them only for designing apps for Apple devices.
- **Phones, Linux and the web:** Roboto, Open Sans, Noto Sans, DejaVu Sans, Inter, Ubuntu Mono, Source Code Pro.
- **The best we found:** the leaders of a 413-font survey we ran at the start of the project (Bookman Old Style,
  Sitka Text), the classic OCR font (OCR-A Extended), and Courier Prime, the open-licence font with the most readable
  punctuation of the 450 we tested.

### By kind of text and kind of damage

The three kinds of text:

- **Paragraphs**: lines of a short story set in a grocery store, with prices, receipt codes and all 32 punctuation marks.
- **Codes**: random mixed-case letters and digits, 6–12 characters long, like order numbers, serials and passwords.
- **Numbers**: digits only, in groups separated by spaces, like barcodes, card numbers and phone numbers.

<details>
<summary>The grocery story (the paragraphs test text)</summary>

Written for the test: everyday prose mixed with prices, codes, receipt lines and every ASCII punctuation mark. The
test splits it into lines of up to 22 characters (198 lines), then again into lines of up to 26 for the rest of
its 300 lines.

```text
The Saturday List

Odile Brennan reached Greenleaf Market #0217 at 8:05 AM, just as the automatic doors slid open and the smell of warm sourdough drifted out from Barnes & Daughters, the bakery by the entrance. Her list was written on the back of an old envelope: 2% milk, 1 dozen eggs, olive oil, Zesty Lime seltzer (12-pack, if the <<< 2 for $9 >>> deal was still on), clams for Sunday's chowder, and "something for Bo's birthday." She folded it twice, tucked it into her coat pocket, and pulled a cart from the corral; it wobbled to the left, as they always do.

In aisle 5 the shelf tag for the olive oil read "SKU 0O1-IL5-8B2Z, Verde Hills Extra Virgin, 500 mL, $8.49." The bottle beside it had a sticker that said $6.99, and the UPC under the barcode was 0 41196 01523 8. Odile photographed both with her phone, because last month the register had charged her the shelf price instead of the sale price, and the manager, a tall man named Clement, had refunded the $1.50 with a small, embarrassed bow.

The dairy case was half empty. She found the milk (UPC 0 70852 99310 4, best by 10/19/26) behind a row of oat-milk cartons, and the eggs (Grade A Large, SKU EGG-12L-0716) on the bottom shelf, where a handwritten card warned: "Limit 2 per customer - thank you!" A boy in a red cap was arranging yogurt cups into a tower: vanilla, lemon, mixed berry, then vanilla again. "Modern art," he told her solemnly. She agreed that it was.

At the seafood counter the clerk weighed the clams on a scale that printed a label: "Littleneck Clams, 1.25 lb @ $11.98/lb, NET $14.98, PLU 4011-C7, packed 10/10/26 07:42." She had asked for about a pound; the scale said otherwise (~1.25 lb, close enough). Odile asked whether the clams were local. "Rhode Island," the clerk said, "came in on the 6 o'clock truck." He wrapped them in brown paper, wrote "B. ODILE" on the side in grease pencil, and added a lemon at no charge.

The birthday present took longer. Bo was turning 11 and liked three things: puzzles, burnt-sugar candy, and anything with a lighthouse on it. In aisle 12 she found a 500-piece puzzle called "Lighthouse at Cape Vvhite" (the box really did spell it with two v's), SKU PZ-500-LH81, $14.99. Next to it was a tin of burnt-sugar toffee, item #8806-31B, marked down from $7.25 to $5.00. She took both, and a card with a cartoon gull that said "Have a Whale of a Day!"

The self-checkout lanes were closed for maintenance, so she joined Lane 3, where the cashier, Ilona, scanned everything with a steady beep, beep, beep. While she waited she joined the store Wi-Fi (network GLM\Guest, password Fresh`Picks_26, taped to the register). The olive oil rang up at $8.49. Odile showed the photo; Ilona called for a price check ("Price check on 3, Verde Hills, five hundred mil"), and two minutes later the screen showed "PRICE OVERRIDE -1.50 / AUTH CL2017." The seltzer, the milk, the eggs, the clams, the puzzle, the toffee, and the card came to $63.62 before tax. Her phone buzzed: {Greenleaf Rewards} +65 pts = 1,305 pts [Gold tier].

The receipt was long enough to curl. At the bottom it read: "SUBTOTAL 63.62 | TAX (2.00%) 1.27 | TOTAL $64.89 | VISA ****1157 | AUTH 8BZ2Q5 | REF 000418-227590-36 | TRANS #5513 | STORE 0217 | TERM 03 | OP 1I0L | 10/10/2026 08:51:17 | ITEMS 8 | [MEMBER] YOU SAVED $3.75 TODAY | e-receipt: odile_b@example.com." Below that, a coupon promised "$2 OFF your next purchase of $25 or more - code GLM-2Z5S-08OB - valid until 11/30/26 ^ see back for details." Someone had scribbled "5 * 3 = 15?" on the back.

Outside, the wind had picked up. Odile loaded the bags into the trunk: milk and eggs on the left, clams in the cooler, the puzzle wedged upright so its corners would not crush. She checked the list one more time, crossed off every line with a short, satisfied stroke, and found a note she had forgotten writing at the very bottom of the envelope: "Call Mom (555) 013-2287 - ask about the 1/2 cup vs 1/3 cup thing." She laughed, started the car, and drove home with the radio on.
```

</details>

The nine print conditions:

| Condition | What it simulates |
|---|---|
| Clean | Crisp print, scanned perfectly |
| Blurry | An out-of-focus scan or phone photo |
| Noisy | A speckled, grainy scan |
| Low-res | A fax, or an image shrunk to half size and blown back up |
| JPEG | Heavy compression (quality 15) |
| Ink bleed | Ink spreading into the paper: every stroke about 1 pixel heavier |
| Smudged | A finger dragged through wet ink: the whole line smeared sideways, more in some places than others |
| Damaged | Blur, ink spread, tilt, perspective, uneven light, noise and JPEG together, mild |
| Heavy | Blur, ink spread, tilt, perspective, uneven light, noise and JPEG together, severe |

Here is each condition applied to its own name. The left column is actual size, the 8 pt text as scanned at 300 dpi,
exactly what the engines receive. The right column is the same damage enlarged 3× so you can see it. Both are
shown in grey; the engines get them after a final black-and-white step, as in most OCR pipelines.

![Each print condition applied to its own name](docs/damage.png)

In the tables below, the best value in each column has a green background and the second best a light blue one.
Values that are equal as shown (to one decimal) count as ties: a difference under 0.1 points is noise. The same numbers are in
[docs/benchmark_results.csv](docs/benchmark_results.csv).

**Paragraphs**

![Paragraphs: character error by font and print condition](docs/table_paragraphs.svg)

**Codes**

![Codes: character error by font and print condition](docs/table_codes.svg)

**Numbers**

![Numbers: character error by font and print condition](docs/table_numbers.svg)

What the tables show: how many fewer errors MaxOCR makes than **the best other font** in each condition. A negative
number means that font made fewer errors than MaxOCR.

| Text | Clean | Blurry | Noisy | Low-res | JPEG | Ink bleed | Smudged | Damaged | Heavy |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Paragraphs | 40% | 15% | 23% | 16% | 48% | 12% | 9% | 14% | −2% |
| Codes | 20% | 31% | 9% | 15% | 19% | 30% | 21% | 11% | 4% |
| Numbers | tie | tie | 16% | −9% | tie | tie | tie | 17% | 30% |

Tie: equal to one decimal. Clean, blurry, JPEG, ink-bleed and smudged numbers are read almost perfectly by
every good font (under 0.1% errors for the best ones).

- **Clean print.** MaxOCR makes 40% fewer errors than the best other font on paragraphs (Georgia) and 20% fewer on
  codes (Bookman Old Style); numbers in clean print are read perfectly in most fonts. Against the everyday fonts it's
  42–58% fewer than the average of Arial, Times New Roman and Calibri.
- **Codes.** MaxOCR leads in all nine conditions.
- **Where another font is ahead.**
  - Paragraphs under heavy damage: Courier Prime makes 2% fewer errors (28.4% against 29.0%). Monospaced fonts give
    narrow letters such as l, t and the comma a full-width slot, so they stay apart when heavy damage blurs the line.
  - Numbers at low resolution: Calibri (3.5% against 3.8%).
- **Ties.** The near-perfect numbers cells.
- **Engine agreement.** In 14 of the 27 cells, all four engines agree that MaxOCR does at least as well as the best
  other font (ties included).
- **Helvetica and Helvetica Neue**, the classic Apple fonts, make slightly more errors than Arial.
- **OCR-A Extended**, the font designed for 1960s optical readers, does worst overall with today's engines.

## Commercial readers and real-world capture

Two more tests, added after an outside review asked about cloud OCR and harsher real-world printing:

**Three more print conditions**, read by the same four engines (300 lines each, all three kinds of text averaged):
a thermal receipt printer (203-dpi head, faded and uneven heat, dead heating elements), a 9-pin dot-matrix printer
(letters rebuilt from round dots, worn ribbon) and a phone photo of a curled receipt (strong perspective, page curl,
shadow, blur, camera noise). Character error %, lower is better:

| Condition | MaxOCR | Best other font | MaxOCR's rank |
|---|---:|---|---:|
| Thermal | 5.3 | Courier Prime 5.4 | 1 of 22 |
| Dot-matrix | 26.8 | Verdana 19.2 | 10 of 22 |
| Phone photo | 24.3 | Courier Prime 25.7 | 1 of 22 |

Dot-matrix print is MaxOCR's weak spot: when letters are rebuilt from dots, its finer details break up and plainer
fonts such as Verdana hold together better.

**Two commercial engines**, Google Cloud Vision (document text detection) and Windows' built-in OCR, on all twelve
conditions (the nine above plus these three; 100 lines per kind of text and condition, read as whole pages):

| Engine | Paragraphs | Codes | Numbers | All | Best other font | MaxOCR fewer errors |
|---|---:|---:|---:|---:|---|---:|
| Google Cloud Vision | 3.2 | 9.0 | 1.2 | **4.5** | Noto Sans 6.1 | 27% |
| Windows OCR | 20.1 | 24.1 | 9.8 | **18.0** | Courier Prime 21.1 | 15% |

MaxOCR is first with both. With Google, Consolas and Courier Prime are slightly ahead on paragraphs alone (2.5% and
2.6% against 3.2%). Full results: [docs/benchmark_extra.csv](docs/benchmark_extra.csv),
[docs/benchmark_google.csv](docs/benchmark_google.csv), [docs/benchmark_windows.csv](docs/benchmark_windows.csv).

## Hebrew

MaxOCR has the Hebrew alphabet: the 22 letters and the 5 final forms. The letters come from open-licence fonts (most
from Arimo; ר ז ל ם from Cousine; ב י ד from Varela Round; ת from Secular One; ה from IBM Plex Sans Hebrew; צ from
Frank Ruhl Libre), scaled to MaxOCR's size and stroke weight, each letter chosen by testing. Hebrew lines in the same
nine print conditions, read by Tesseract's Hebrew model (the only one of the four engines here that reads Hebrew);
character error %, lower is better, best in bold; the eight best of 37 fonts with Hebrew (Windows, Google Fonts,
the Linux Culmus set and DejaVu Sans):

| Font | Clean | Blurry | Noisy | Low-res | JPEG | Ink bleed | Smudged | Damaged | Heavy | Average |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **MaxOCR** | 0.1 | **0.1** | **1.3** | **3.9** | 0.1 | 0.2 | 0.9 | 6.4 | 29.1 | **4.7** |
| Courier New | 0.1 | **0.1** | 4.0 | 5.8 | 0.1 | 0.1 | **0.4** | 11.8 | **27.6** | 5.6 |
| Cousine | 1.3 | 1.1 | 5.0 | 5.9 | 1.8 | 1.1 | 2.3 | 6.7 | 27.9 | 5.9 |
| DejaVu Sans | **0.0** | **0.1** | 2.3 | 7.3 | **0.0** | 0.6 | 1.8 | 6.9 | 35.6 | 6.1 |
| David CLM | 0.7 | 0.9 | 2.6 | 6.0 | 0.5 | 1.3 | 3.1 | 6.9 | 34.7 | 6.3 |
| Miriam Mono CLM | 0.3 | 0.5 | 4.1 | 8.3 | 0.4 | **0.0** | **0.4** | 12.2 | 30.5 | 6.3 |
| Arimo | 0.5 | 1.0 | 1.6 | 8.8 | 0.3 | 3.6 | 2.0 | **5.9** | 34.8 | 6.5 |
| IBM Plex Sans Hebrew | 0.8 | 1.1 | 2.4 | 10.4 | 0.6 | 3.4 | 2.5 | 7.9 | 35.2 | 7.1 |

MaxOCR makes 16% fewer errors than the next font (Courier New) on average; Courier New is still ahead under heavy
damage. One engine only, so treat this as a first result.

## Cyrillic

MaxOCR has the Russian alphabet (А–я, Ё ё). Letters that look the same as Latin ones (А В Е К М Н О Р С Т Х,
а е о р с у х) are MaxOCR's own Latin letters; the rest come from open-licence fonts (most from Cousine; б and ь from
Noto Sans, й from IBM Plex Serif), scaled to MaxOCR's size and weight and chosen by testing. Russian lines in the
nine print conditions, read by Tesseract's Russian model; character error %, lower is better, best in bold; the
eight best of 14 fonts with Cyrillic:

| Font | Clean | Blurry | Noisy | Low-res | JPEG | Ink bleed | Smudged | Damaged | Heavy | Average |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **MaxOCR** | 0.1 | 0.1 | **1.2** | **2.2** | 0.1 | 0.2 | 0.2 | 6.6 | **25.1** | **4.0** |
| Verdana | **0.0** | 0.1 | 1.3 | 2.6 | **0.0** | 0.4 | 0.3 | **3.6** | 30.8 | 4.3 |
| Source Code Pro | **0.0** | 0.2 | 4.3 | **2.2** | **0.0** | 0.5 | **0.1** | 4.4 | 28.6 | 4.5 |
| Noto Sans | **0.0** | 0.1 | 1.3 | 2.6 | 0.1 | 0.6 | 0.2 | 4.4 | 32.4 | 4.6 |
| Consolas | **0.0** | 0.1 | 4.1 | 2.6 | **0.0** | 1.7 | 0.6 | 3.9 | 30.5 | 4.8 |
| Segoe UI | **0.0** | **0.0** | 1.3 | 3.2 | **0.0** | **0.1** | **0.1** | 5.2 | 34.3 | 4.9 |
| Courier New | **0.0** | **0.0** | 2.0 | 2.6 | **0.0** | 0.2 | 0.3 | 10.8 | 30.9 | 5.2 |
| Calibri | **0.0** | **0.0** | 1.3 | 4.2 | **0.0** | 4.0 | 0.5 | 4.1 | 33.0 | 5.2 |

MaxOCR makes 8% fewer errors than the next font (Verdana) on average. One engine only, so treat this as a
first result.

## Real print-and-scan test

The same text printed on an office laser printer and scanned at 600 dpi (one printer, one scanner, five fonts, about
1,700 characters per font), then read by the same four engines at 300 dpi.

| Font | Paragraphs | Codes | Numbers | All |
|---|---:|---:|---:|---:|
| **MaxOCR** | **0.33** | **2.1** | **0.0** | **0.8** |
| Times New Roman | 0.43 | 3.5 | 0.0 | 1.3 |
| Courier Prime | 0.43 | 4.6 | 0.0 | 1.7 |
| Arial | 0.47 | 5.2 | 0.0 | 1.9 |
| Courier New | 2.3 | 4.4 | 0.0 | 2.2 |

Character error %, lower is better (version 0.98). On real paper MaxOCR made the fewest errors overall and on codes,
about 40% fewer than the next font. The sample is small, so treat small differences as ties.

## Letters that run together

OCR engines often read two narrow letters as one wide one. Each pair was printed inside codes, blurred and read by
the same four engines (version 0.99).

| Pair read as one letter | MaxOCR |
|---|---:|
| vv as w | 0.0% |
| VV as W | 0.1% |
| rn as m | 0.2% |
| cl as d | 0.0% |
| ri as n | 0.0% |
| in as m | 0.0% |

None of the single letters was ever read as the pair.

## AI readers

A vision-language model (Qwen2.5-VL) reads clean text in almost any font nearly perfectly. In our measurements on clean
text and codes (version 0.95), MaxOCR's character error was 0.33% and Courier New's 0.24%. The difference is a handful of characters, within
the test's noise. MaxOCR's advantage is with conventional OCR engines and damaged print.

## How it was measured

- **Engines.** PaddleOCR, EasyOCR, PARSeq and Tesseract (with its dictionaries on). Every number above is the
  average of the four. Each is used the way it is meant to be used: PARSeq reads one word at a time (it reads at
  most 25 characters; a real OCR pipeline finds the words first), and EasyOCR may output spaces. Earlier versions
  of this README gave PARSeq whole lines and kept EasyOCR from writing spaces (it invented dots instead), which
  made every font look worse and some much worse than others.
- **Reading mode.** All engines read case-sensitively over letters, digits and punctuation.
- **Scoring.** Character error from an alignment of the engine's output with the true text, ignoring spaces.
- **Printing.** 8 pt at 300 dpi (the standard scanning resolution; at 200 dpi Tesseract's letters were too small
  for it and it started inventing letters). Fonts are rendered with their OpenType features on, as browsers and
  design apps do. Every font is set at the same capital height, so fonts with large letters get no
  advantage. Every image is converted to black and white (Otsu), as most OCR pipelines do.
- **Sample size.** 300 lines per kind of text per condition, the same lines for every font, read by each of the four
  engines. A lead that all four engines agree on is unlikely to be chance; where they split, treat the result as
  close to a tie.
- **Simulated damage.** The damage in the tables is simulated; see the print-and-scan test above for real paper.
- **Reproducing.** Install the project environment with `pixi install` (under WSL on Windows; the comparison fonts
  are read from `C:\Windows\Fonts`). Then run `pixi run python scripts/readme_bench.py`; results go to
  `out/report/readme_bench.csv`.

## How it was made

1. **Survey.** We measured 413 installed fonts to learn which characters OCR engines confuse and which shapes
   keep them apart. For example, the engines ignore slashes and dots inside zeros; what helps most is a wide O next
   to a narrow, tall 0.
2. **Building the letters.** Each character was built from open-licence fonts, then tuned against the four
   engines one confusion at a time: 0/O, 1/l/I, 5/S, 2/Z, 8/B, rn/m and vv/w.
3. **Cleanup.** Every outline was redrawn by hand to remove the lumps and notches the blending left behind.
4. **Final letters.** C, O, g, t and J were chosen from 58 open-licence serif faces for the most normal look that
   still scored well.
5. **Capitals for low-resolution scans.** At low resolution the hairlines of C, K, O, U, V, W, X, Y and Z
   disappeared, and engines read those capitals as lowercase. Their thin strokes were thickened by hand (straight
   edges moved parallel, curves and serifs kept), and the W was redrawn from straight strokes.
6. **Codes and numbers.** Inside codes the lowercase letters are slightly smaller (74% of the capital height
   instead of 78%), so engines can tell W from w and O from o without context; numbers get a little extra space
   between digits; and the digits have more even strokes, so they survive thinned or broken print.
7. **The 3 and the e for ink bleed.** When ink spreads, our old 3 clumped and Tesseract returned nothing for whole
   lines of numbers, and the eye of our old e closed up so it was read as o or a. The 3s and e's of 80 open-licence
   fonts were each fitted into MaxOCR's shapes and tested. The 3 from Noto Sans (Google) cut errors on ink-bleed
   numbers from 0.39% to 0.10%; the e from Spectral (Production Type) cut errors on ink-bleed paragraphs from 1.31%
   to 1.07%. Both fonts are under the SIL Open Font License. The o then got 40 units more space (half on each side),
   which keeps it apart from its neighbours under heavy damage.
8. **Letter-by-letter sweep.** Every character is tried in the shapes of 80 open-licence fonts, fitted to MaxOCR's
   size and weight; a swap is kept only if the full benchmark improves and the letter still fits in. Kept: the n from
   Quattrocento, the h from Enriqueta, the d from Arvo, the s from Carlito, the S from Literata (at 92%, to match the
   other capitals), the D from Manuale, the G from Enriqueta (strokes thickened to match), the Y from Cardo, the P from Mate, the Q from Radley and
   the 1 from Aleo (all SIL Open Font License). Most helped only a little on their own and were kept in groups. The I
   (Source Code Pro) and T (Faustina) were then chosen for looks among the near-equal candidates, and h, b and d
   were given the k's top serif and the h the n's feet, so the letters match. The s and d were redrawn with real curves (the s keeps Carlito's
   tips, the d gets the a's tail and a slightly heavier top to its bowl).

`DECISIONS.md` records every step, measurement and choice.

## License

MaxOCR is licensed under the [SIL Open Font License 1.1](LICENSE): free to use, embed, modify and share, including
commercially; it may not be sold on its own. Its letters were built from other fonts under the same license; their
names and copyright notices are in [CREDITS.md](CREDITS.md). The other fonts in the comparison were measured, never
copied.
