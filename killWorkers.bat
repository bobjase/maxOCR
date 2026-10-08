@echo off
rem Stop all MaxOCR harness processes running inside WSL (frees CPU held by VmmemWSL).
for /f "delims=" %%p in ('wsl -d Ubuntu wslpath -a "%~dp0scripts\kill_workers.sh"') do set SCRIPT=%%p
wsl -d Ubuntu -- bash "%SCRIPT%"
pause
