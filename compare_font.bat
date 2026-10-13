@echo off
rem Run the full README comparison on one font: compare_font.bat "Times New Roman"   or   compare_font.bat C:\path\font.ttf
rem Report: out\report\compare_<name>.md and .json  (takes about 2 minutes)
if "%~1"=="" (
  echo Usage: compare_font.bat "Font Name"   or   compare_font.bat C:\path\to\font.ttf
  exit /b 1
)
set "ARG=%~1"
if exist "%ARG%" (
  for /f "delims=" %%P in ('wsl -d Ubuntu -- wslpath -a "%ARG:\=/%"') do set "ARG=%%P"
)
wsl -d Ubuntu -- bash -c "cd /mnt/c/Users/james.JAMESWORK2025/Repos/MaxOCR && MAXOCR_CROP=ink timeout -s KILL 1200 $HOME/.pixi/bin/pixi run python -u scripts/compare_font.py \"%ARG%\" 2>&1 | grep -v -i -E 'warn|cache|timm'; bash scripts/kill_workers.sh > /dev/null"
