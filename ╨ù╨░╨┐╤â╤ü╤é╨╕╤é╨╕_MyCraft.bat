@echo off
chcp 65001 >nul
cd /d "%~dp0"
title MyCraft Launcher
where py >nul 2>nul
if %errorlevel%==0 (set "PY=py") else (set "PY=python")
if not exist .venv\Scripts\python.exe (
  echo [1/3] Створення середовища Python...
  %PY% -m venv .venv
  if errorlevel 1 goto no_python
)
echo [2/3] Перевірка та встановлення бібліотек...
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 goto install_error
echo [3/3] Запуск MyCraft Launcher...
.venv\Scripts\python.exe main.py
if errorlevel 1 pause
exit /b 0
:no_python
echo Python не знайдено. Встанови Python 3.11 або 3.12 з https://www.python.org/downloads/windows/
echo Під час встановлення увімкни пункт Add Python to PATH.
pause
exit /b 1
:install_error
echo Не вдалося встановити залежності. Перевір інтернет і повтори запуск.
pause
exit /b 1
