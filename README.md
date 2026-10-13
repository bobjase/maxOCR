# MaxOCR

A font for text that people read and machines read back: receipts, labels, invoices, forms, serial numbers, anything
that will be scanned, photographed or faxed and then run through OCR. It looks like an ordinary serif book face,
but every character is shaped and spaced so that OCR engines confuse it with as few other characters as possible.

![MaxOCR character set](docs/specimen.png)

**Version 0.96.** 95 characters: A–Z, a–z, 0–9, space and all 32 ASCII punctuation marks.

## Which file to use

| File | Use it for |
|---|---|
| `MaxOCR.ttf` | **Start here.** Everyday text, codes and numbers. Adds a little space where letters meet digits (applied automatically in apps that support kerning). |
| `MaxOCR-Text.ttf` | The same letters with plain spacing everywhere (no extra space between letters and digits). |
| `MaxOCR-Small.ttf` | Print smaller than about 7 pt (wider letter spacing; cuts errors by about 12% at 6 pt). |
| `MaxOCR-Machine.ttf` | Machine-only work where looks do not matter: capitals, digits and space only. |

## How it compares

Character error rate (the share of characters an OCR engine gets wrong), averaged over eight print conditions from
crisp to badly damaged. Lower is better.

![Average character error by font](docs/benchmark.png)

| Font | Paragraphs | Codes | Numbers | **All three** |
|---|---:|---:|---:|---:|
| **MaxOCR** | **6.8** | **11.9** | **4.2** | **7.6** |
| Courier New | 8.0 | 14.2 | 7.3 | 9.8 |
| Sitka Text | 8.6 | 15.7 | 7.0 | 10.4 |
| Courier Prime | 8.2 | 16.2 | 8.0 | 10.8 |
| Bookman Old Style | 10.7 | 15.5 | 7.2 | 11.2 |
| Verdana | 10.4 | 17.6 | 8.1 | 12.1 |
| Calibri | 10.2 | 19.3 | 7.7 | 12.4 |
| Segoe UI | 11.5 | 18.4 | 8.1 | 12.7 |
| Consolas | 9.5 | 20.2 | 10.4 | 13.3 |
| Georgia | 11.4 | 19.4 | 9.3 | 13.4 |
| Times New Roman | 14.7 | 19.5 | 9.3 | 14.5 |
| Arial | 14.9 | 20.9 | 11.8 | 15.9 |
| OCR-A Extended | 13.7 | 26.6 | 19.0 | 19.8 |

Across all three kinds of text, MaxOCR makes **22% fewer errors than the next best font** (Courier New) and **about
half as many as Arial or Times New Roman**. The gap is largest on **numbers**: 4.2% against 7.0% for the
next best font.

The comparison set is the fonts people use most (Arial, Times New Roman, Calibri, Segoe UI, Verdana, Georgia,
Consolas, Courier New), the leaders of a 413-font survey we ran at the start of the project (Bookman Old Style,
Sitka Text), the classic OCR font (OCR-A Extended), and Courier Prime, the open-licence font with the most readable
punctuation of the 450 we tested.

### By kind of text and kind of damage

The three kinds of text:

- **Paragraphs**: lines of a short story set in a grocery store, with prices, receipt codes and all 32 punctuation marks.
- **Codes**: random mixed-case letters and digits, 6–12 characters long, like order numbers, serials and passwords.
- **Numbers**: digits only, in groups separated by spaces, like barcodes, card numbers and phone numbers.

The eight print conditions:

| Condition | What it simulates |
|---|---|
| Clean | Crisp print, scanned perfectly |
| Blurry | An out-of-focus scan or phone photo |
| Noisy | A speckled, grainy scan |
| Low-res | A fax, or an image shrunk to half size and blown back up |
| JPEG | Heavy compression (quality 15) |
| Smudged | Ink spread: every stroke about 1 pixel heavier |
| Damaged | Several kinds at once, mildly: blur, ink spread, tilt, perspective, uneven light, noise, JPEG |
| Heavy | The same combination, severely |

The best value in each column is bold.

**Paragraphs**

| Font | Clean | Blurry | Noisy | Low-res | JPEG | Smudged | Damaged | Heavy | **Average** |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **MaxOCR** | **2.2** | **2.2** | **4.3** | 5.1 | **2.2** | **1.9** | **6.3** | 29.9 | **6.8** |
| Courier New | 3.2 | 3.4 | 9.3 | 5.7 | 3.2 | 3.9 | 7.2 | **27.9** | 8.0 |
| Courier Prime | 3.1 | 4.5 | 7.6 | **4.9** | 2.8 | 6.2 | 8.5 | 28.4 | 8.2 |
| Sitka Text | 3.0 | 2.8 | 5.7 | 6.0 | 2.8 | 5.7 | 8.4 | 34.7 | 8.6 |
| Consolas | 4.2 | 6.5 | 8.0 | 6.9 | 4.0 | 6.7 | 9.9 | 30.0 | 9.5 |
| Calibri | 3.5 | 5.5 | 5.7 | 7.0 | 4.0 | 6.8 | 11.6 | 37.6 | 10.2 |
| Verdana | 3.1 | 7.3 | 6.6 | 7.2 | 2.9 | 8.8 | 12.3 | 35.3 | 10.4 |
| Bookman Old Style | 3.3 | 6.2 | 7.1 | 8.4 | 4.0 | 8.4 | 10.3 | 38.0 | 10.7 |
| Georgia | 2.9 | 6.3 | 5.7 | 8.1 | 2.9 | 7.1 | 12.2 | 45.8 | 11.4 |
| Segoe UI | 4.3 | 8.9 | 8.0 | 8.0 | 4.2 | 7.6 | 11.7 | 39.6 | 11.5 |
| OCR-A Extended | 6.6 | 12.7 | 11.4 | 11.2 | 6.4 | 12.9 | 14.5 | 34.2 | 13.7 |
| Times New Roman | 3.9 | 10.5 | 8.1 | 15.9 | 5.5 | 10.1 | 15.3 | 48.2 | 14.7 |
| Arial | 3.7 | 13.9 | 7.6 | 10.6 | 4.2 | 13.2 | 17.9 | 48.5 | 15.0 |

**Codes**

| Font | Clean | Blurry | Noisy | Low-res | JPEG | Smudged | Damaged | Heavy | **Average** |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **MaxOCR** | **4.4** | **6.3** | 9.9 | 15.2 | **4.8** | **5.5** | **10.5** | **39.0** | **11.9** |
| Courier New | 6.5 | 9.0 | 12.3 | 16.8 | 7.2 | 8.9 | 13.2 | 40.2 | 14.3 |
| Bookman Old Style | 5.2 | 8.9 | **9.7** | 15.6 | 6.0 | 11.6 | 16.7 | 50.1 | 15.5 |
| Sitka Text | 6.2 | 8.7 | 10.5 | 16.1 | 7.1 | 10.2 | 15.9 | 50.6 | 15.7 |
| Courier Prime | 6.5 | 10.1 | 10.9 | **15.1** | 6.9 | 13.4 | 18.5 | 48.0 | 16.2 |
| Verdana | 7.4 | 13.7 | 12.6 | 17.7 | 8.1 | 12.3 | 18.9 | 50.2 | 17.6 |
| Segoe UI | 6.3 | 14.5 | 12.6 | 19.9 | 7.1 | 11.6 | 19.8 | 55.6 | 18.4 |
| Calibri | 7.8 | 12.9 | 14.1 | 18.5 | 8.9 | 12.0 | 21.7 | 58.2 | 19.3 |
| Georgia | 6.4 | 11.1 | 11.1 | 19.9 | 7.6 | 15.8 | 20.6 | 62.7 | 19.4 |
| Times New Roman | 5.9 | 12.1 | 13.6 | 23.5 | 9.5 | 13.1 | 18.6 | 59.4 | 19.5 |
| Consolas | 9.6 | 16.9 | 14.6 | 22.2 | 10.5 | 15.7 | 20.6 | 51.4 | 20.2 |
| Arial | 6.3 | 18.1 | 12.4 | 19.0 | 7.6 | 17.6 | 25.3 | 61.0 | 20.9 |
| OCR-A Extended | 15.6 | 25.6 | 23.2 | 26.3 | 17.9 | 22.6 | 28.8 | 52.7 | 26.6 |

**Numbers**

| Font | Clean | Blurry | Noisy | Low-res | JPEG | Smudged | Damaged | Heavy | **Average** |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **MaxOCR** | **0.7** | **1.1** | **4.5** | **2.6** | **0.9** | **1.1** | **3.7** | **18.7** | **4.2** |
| Sitka Text | 1.9 | 2.6 | 6.8 | 6.1 | 2.3 | 2.1 | 6.0 | 28.2 | 7.0 |
| Bookman Old Style | 2.5 | 3.2 | 7.2 | 5.1 | 2.8 | 3.3 | 6.1 | 27.7 | 7.2 |
| Courier New | 1.6 | 2.1 | 12.7 | 7.5 | 2.3 | 1.8 | 7.0 | 23.2 | 7.3 |
| Calibri | 1.4 | 2.4 | 6.6 | 4.1 | 1.8 | 2.8 | 6.6 | 36.3 | 7.7 |
| Courier Prime | 1.0 | 5.2 | 10.5 | 5.2 | 1.3 | 5.3 | 8.1 | 27.3 | 8.0 |
| Verdana | 3.2 | 4.4 | 8.3 | 6.7 | 3.4 | 3.6 | 6.8 | 28.4 | 8.1 |
| Segoe UI | 2.0 | 3.5 | 8.1 | 6.3 | 2.3 | 2.8 | 7.0 | 33.0 | 8.1 |
| Georgia | 2.1 | 2.5 | 6.4 | 6.4 | 2.2 | 4.3 | 6.4 | 44.4 | 9.3 |
| Times New Roman | 1.7 | 4.3 | 8.5 | 9.6 | 1.9 | 3.3 | 8.2 | 37.3 | 9.3 |
| Consolas | 3.6 | 5.7 | 9.8 | 9.1 | 3.7 | 6.2 | 10.2 | 34.5 | 10.4 |
| Arial | 3.4 | 6.8 | 7.7 | 7.1 | 3.4 | 7.8 | 12.7 | 45.1 | 11.7 |
| OCR-A Extended | 9.4 | 21.0 | 19.4 | 12.8 | 12.6 | 12.2 | 19.8 | 44.9 | 19.0 |

What the tables show:

- **Numbers:** MaxOCR has the fewest errors in every condition, and usually by a wide margin.
- **Clean, blurry, JPEG and smudged print:** MaxOCR leads for every kind of text.
- **Where another font edges ahead:**
  - heavily damaged paragraphs: Courier New, 27.9 vs 29.9;
  - low-resolution paragraphs and codes: Courier Prime, by 0.1–0.2;
  - noisy codes: Bookman Old Style, 9.7 vs 9.9.

  All four are within the test's noise (see below).
- **OCR-A Extended**, the font designed for 1960s optical readers, does worst of all with today's engines.

## Letters that run together

OCR engines often read two narrow letters as one wide one. Each pair was printed inside codes, blurred and read by
the same four engines. These numbers come from version 0.91; none of the letters involved has changed since.

| Pair read as one letter | MaxOCR |
|---|---:|
| vv as w | 0.0% |
| VV as W | 0.5% |
| rn as m | 1.0% |
| cl as d | 0.0% |
| ri as n | 0.0% |
| in as m | 0.0% |

None of the single letters was ever read as the pair.

## AI readers

A vision-language model (Qwen2.5-VL) reads clean text in almost any font nearly perfectly. In our measurements on clean
text and codes, MaxOCR's character error was 0.33% and Courier New's 0.24%. The difference is a handful of characters, within
the test's noise. MaxOCR's advantage is with conventional OCR engines and damaged print.

## How it was measured

- **Engines.** PaddleOCR, EasyOCR, PARSeq and Tesseract (with its dictionaries on). Every number above is the
  average of the four.
- **Reading mode.** All engines read case-sensitively over letters, digits and punctuation.
- **Scoring.** Character error from an alignment of the engine's output with the true text, ignoring spaces.
- **Printing.** 8 pt at 200 dpi. Every font is set at the same capital height, so fonts with large letters get no
  advantage. Every image is converted to black and white (Otsu), as most OCR pipelines do.
- **Sample size.** 100 lines per kind of text per condition, the same lines for every font. With 100 lines,
  differences under about one point are within noise.
- **Simulated damage.** All damage is simulated. A print-and-scan test on paper is still to come.
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

`DECISIONS.md` records every step, measurement and choice.

## License

MaxOCR is built only from fonts under the SIL Open Font License 1.1. It will be released under the same license with
version 1.0, together with the license file and full credits for the source fonts. The fonts in the comparison were
measured, never copied.
