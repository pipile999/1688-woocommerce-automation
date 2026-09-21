@echo off
setlocal
chcp 65001 >nul
"C:\Users\ayala\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -X utf8 "D:\codex\fastener-site\sites\fastenhardware\runner.py" %*
if errorlevel 1 pause
