@echo off
py -3 "%~dp0panel\panel.py"
if errorlevel 1 pause
