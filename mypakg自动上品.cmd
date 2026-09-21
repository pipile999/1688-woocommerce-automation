@echo off
setlocal
chcp 65001 >nul
"C:\Users\ayala\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -X utf8 "D:\codex\新建文件夹\1688-woocommerce-automation-main\sites\mypakg\runner.py" %*
if errorlevel 1 pause
