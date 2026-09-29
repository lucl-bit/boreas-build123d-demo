@echo off
cd /d "%~dp0"
set PY=python
if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" set PY="%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
%PY% app.py
pause
