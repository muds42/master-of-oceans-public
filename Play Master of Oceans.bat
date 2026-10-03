@echo off
rem Double-click to play Master of Oceans on Windows.
rem
rem The first time, this sets the game up: it makes a private Python environment
rem in the .venv folder, installs pygame into it and puts a shortcut on the
rem desktop. After that it just starts the game, without a console window.
rem Anything after the file name is passed on, e.g. --scenario battle_line.

setlocal
set "HERE=%~dp0"
set "ME=%~f0"
set "VENV=%~dp0.venv"
set "VPY=%~dp0.venv\Scripts\python.exe"
cd /d "%HERE%"
title Master of Oceans

if exist "%VPY%" goto check_venv

echo Setting up Master of Oceans. This only happens once.
echo.
call :find_python
if not defined PYTHON goto no_python
echo Making the game's Python environment in the .venv folder...
%PYTHON% -m venv "%VENV%"
if errorlevel 1 goto venv_failed

:check_venv
"%VPY%" -c "import sys" >nul 2>&1
if errorlevel 1 goto broken_venv

rem Install pygame the first time, and again whenever requirements.txt changes
rem (e.g. after pulling a new version of the game).
"%VPY%" -c "import filecmp, sys; sys.exit(not filecmp.cmp(sys.argv[1], sys.argv[2], shallow=False))" "%HERE%requirements.txt" "%VENV%\requirements.installed" >nul 2>&1
if not errorlevel 1 goto shortcut
echo Installing pygame. This needs an internet connection and takes a minute...
rem --only-binary: a ready-made pygame or nothing. Without it, pip would try to
rem build pygame from source for a Python too new to have one, and fail slowly.
"%VPY%" -m pip install --disable-pip-version-check --only-binary pygame-ce -r "%HERE%requirements.txt"
if errorlevel 1 goto pip_failed
copy /y "%HERE%requirements.txt" "%VENV%\requirements.installed" >nul

:shortcut
rem Make the desktop shortcut once. Deleting it later is fine: it won't come back.
if exist "%VENV%\shortcut.done" goto play
set "ICON=%HERE%seabattle\assets\icon.ico"
powershell -NoProfile -Command "$s = (New-Object -ComObject WScript.Shell).CreateShortcut([IO.Path]::Combine([Environment]::GetFolderPath('Desktop'), 'Master of Oceans.lnk')); $s.TargetPath = $env:ME; $s.WorkingDirectory = $env:HERE; $s.IconLocation = $env:ICON; $s.Description = 'Play Master of Oceans'; $s.Save()" >nul 2>&1
if errorlevel 1 (
    echo Could not put a shortcut on the desktop. To make one yourself, right-click
    echo "Play Master of Oceans.bat" and choose Send to, then Desktop ^(create shortcut^).
    echo On Windows 11, Send to is under "Show more options".
    pause
) else (
    echo Put a "Master of Oceans" shortcut on your desktop.
)
echo done> "%VENV%\shortcut.done"

:play
rem pythonw runs the game without a console window. If the game crashes it
rem says so in a message box and writes the details to crash.log next to the
rem saves (in %APPDATA%\Master of Oceans\saves).
start "" "%VENV%\Scripts\pythonw.exe" -m seabattle %*
exit /b 0


:find_python
rem A Python 3.10 or newer. First the newest one pygame is known to have
rem ready-made builds for, through the py launcher, so a brand-new Python that
rem pygame hasn't caught up with yet isn't picked over an older one that works.
rem Then whatever the py launcher picks, then python, then python3.
rem (The Microsoft Store's stand-in "python" fails this check, as it should.)
for %%V in (3.15 3.14 3.13 3.12 3.11 3.10) do (
    py -%%V -c "import sys" >nul 2>&1
    if not errorlevel 1 (
        set "PYTHON=py -%%V"
        exit /b 0
    )
)
set "PYTHON=py -3"
%PYTHON% -c "import sys; sys.exit(sys.version_info < (3, 10))" >nul 2>&1
if not errorlevel 1 exit /b 0
set "PYTHON=python"
%PYTHON% -c "import sys; sys.exit(sys.version_info < (3, 10))" >nul 2>&1
if not errorlevel 1 exit /b 0
set "PYTHON=python3"
%PYTHON% -c "import sys; sys.exit(sys.version_info < (3, 10))" >nul 2>&1
if not errorlevel 1 exit /b 0
set "PYTHON="
exit /b 1

:no_python
echo Master of Oceans needs Python 3.10 or newer, and this computer doesn't have it.
echo Install it from https://www.python.org/downloads/ and then run this again.
echo.
choice /c YN /m "Open the Python download page now"
if not errorlevel 2 start "" https://www.python.org/downloads/
exit /b 1

:venv_failed
echo.
echo Could not make the Python environment (see the message above).
pause
exit /b 1

:broken_venv
echo The game's Python environment in the .venv folder doesn't work any more.
echo This happens when Python has been upgraded or reinstalled.
echo Delete the .venv folder and run this again to set it up afresh.
echo Your saved campaigns are in %APPDATA%\Master of Oceans\saves and are not affected.
pause
exit /b 1

:pip_failed
echo.
echo Could not install pygame (see the message above). Check the internet
echo connection and run this again.
echo.
echo If it says no matching distribution was found, pygame isn't ready yet for
echo the version of Python this computer has. Install Python 3.13 from
echo https://www.python.org/downloads/ then delete the .venv folder and run
echo this again.
pause
exit /b 1
