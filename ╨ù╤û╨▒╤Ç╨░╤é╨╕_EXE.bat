@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe py -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 goto error
.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean --windowed --name MyCraftLauncher --icon assets\icon.ico --add-data "assets;assets" --collect-all customtkinter --collect-all minecraft_launcher_lib main.py
if errorlevel 1 goto error
echo.
echo EXE готовий: dist\MyCraftLauncher\MyCraftLauncher.exe
set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if exist "%ISCC%" (
  "%ISCC%" installer.iss
  echo Інсталятор: installer_output\MyCraftLauncher_Setup.exe
) else (
  echo Щоб зробити інсталятор, встанови Inno Setup 6 ^(https://jrsoftware.org/isdl.php^) і запусти цей файл ще раз.
)
pause
exit /b 0
:error
echo Помилка встановлення або збирання. Перевір інтернет та версію Python.
pause
exit /b 1
