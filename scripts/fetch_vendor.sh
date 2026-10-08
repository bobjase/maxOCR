#!/usr/bin/env bash
# Download pinned third-party data into vendor/ and verify hashes.
set -euo pipefail
cd "$(dirname "$0")/.."

fetch() {  # url dest sha256 (empty sha = print it)
  local url=$1 dest=$2 sha=$3
  mkdir -p "$(dirname "$dest")"
  [ -f "$dest" ] || curl -fsSL "$url" -o "$dest"
  local got; got=$(sha256sum "$dest" | cut -d' ' -f1)
  if [ -z "$sha" ]; then echo "UNPINNED $dest $got"; return; fi
  [ "$got" = "$sha" ] || { echo "HASH MISMATCH $dest: $got"; exit 1; }
  echo "ok $dest"
}

# R12: LSTM model (oem 1).
fetch https://raw.githubusercontent.com/tesseract-ocr/tessdata_best/e12c65a915945e4c28e237a9b52bc4a8f39a0cec/eng.traineddata \
  vendor/tessdata_best/eng.traineddata 8280aed0782fe27257a68ea10fe7ef324ca0f8d85bd2fd145d1c2b560bcb66ba
# R15b: legacy-capable model (oem 0); best/fast contain no legacy data.
fetch https://raw.githubusercontent.com/tesseract-ocr/tessdata/ced78752cc61322fb554c280d13360b35b8684e4/eng.traineddata \
  vendor/tessdata_legacy/eng.traineddata daa0c97d651c19fba3b25e81317cd697e9908c8208090c94c3905381c23fc047
# R11: PP-OCRv6 medium recognition, ONNX export (HF revision pinned).
PP=https://huggingface.co/PaddlePaddle/PP-OCRv6_medium_rec_onnx/resolve/50c7eacafc52fa7bcf4194e8cd08e46f8558504b
fetch $PP/inference.onnx vendor/ppocrv6_medium_rec/inference.onnx 9c09abf0957f7968c7586464b7397b84ad2387a0497a351af40e9acc71b673ba
fetch $PP/inference.yml vendor/ppocrv6_medium_rec/inference.yml 991b700facf5b50a7de193468207d5f4255b538dde0d312ae3b7c7a9b6873129

# Section 11 baseline fonts. Archives are verified, then one Regular face is extracted.
DL=vendor/_dl
FONTS=vendor/fonts
mkdir -p $FONTS
unzip_one() { [ -f "$3" ] || python3 -c "import zipfile,sys; open(sys.argv[3],'wb').write(zipfile.ZipFile(sys.argv[1]).read(sys.argv[2]))" "$1" "$2" "$3"; }

fetch https://deb.debian.org/debian/pool/main/f/fonts-ocr-a/fonts-ocr-a_1.0-12_all.deb \
  $DL/fonts-ocr-a_1.0-12_all.deb 34382ea995436d9a74a92ac535130715419c2a7b2a06aa23f592f957a03f12c2
[ -f $FONTS/OCRA.ttf ] || dpkg-deb --fsys-tarfile $DL/fonts-ocr-a_1.0-12_all.deb \
  | tar -xO ./usr/share/fonts/truetype/ocr-a/OCRA.ttf > $FONTS/OCRA.ttf
fetch https://mirrors.ctan.org/fonts/ocr-b-outline/opentype/ocrb10.otf \
  $FONTS/ocrb10.otf 6270b592af1cb319fe4122777d14fdbfc4a2edd111c6f87af3f4ac04c82ba48a
fetch https://github.com/JetBrains/JetBrainsMono/releases/download/v2.304/JetBrainsMono-2.304.zip \
  $DL/JetBrainsMono-2.304.zip 6f6376c6ed2960ea8a963cd7387ec9d76e3f629125bc33d1fdcd7eb7012f7bbf
unzip_one $DL/JetBrainsMono-2.304.zip fonts/ttf/JetBrainsMono-Regular.ttf $FONTS/JetBrainsMono-Regular.ttf
fetch "https://github.com/IBM/plex/releases/download/%40ibm%2Fplex-mono%402.5.0/ibm-plex-mono.zip" \
  $DL/ibm-plex-mono.zip 6d23f01257663d8cc49a0d64c22ced630b79e0e2a0ac08a0da86e9a38bbc481c
unzip_one $DL/ibm-plex-mono.zip ibm-plex-mono/fonts/complete/ttf/IBMPlexMono-Regular.ttf $FONTS/IBMPlexMono-Regular.ttf
fetch https://github.com/adobe-fonts/source-code-pro/releases/download/2.042R-u%2F1.062R-i%2F1.026R-vf/TTF-source-code-pro-2.042R-u_1.062R-i.zip \
  $DL/TTF-source-code-pro-2.042R-u_1.062R-i.zip 0c85bac90d15c040b82939aa92bc8404420fccc02e37bbcb9c93a7f21abb52c6
unzip_one $DL/TTF-source-code-pro-2.042R-u_1.062R-i.zip TTF/SourceCodePro-Regular.ttf $FONTS/SourceCodePro-Regular.ttf
