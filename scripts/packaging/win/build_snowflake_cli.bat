@echo off
set PATH=C:\Program Files\Python310\;c:\Program Files (x86)\Windows Kits\8.1\bin\x86\;%PATH%

python.exe -m pip install --upgrade pip uv hatch

@echo off
FOR /F "delims=" %%I IN ('hatch run packaging:win-build-version') DO SET CLI_VERSION=%%I
echo %CLI_VERSION%

set ENTRYPOINT=src\\snowflake\\cli\\_app\\__main__.py

@echo on
python.exe -m hatch -e packaging run ^
  pyinstaller ^
  --name snow ^
  --onedir ^
  --clean ^
  --noconfirm ^
  --console ^
  --icon=scripts\packaging\win\snowflake_msi.ico ^
  %ENTRYPOINT%

tar -a -c -f snowflake-cli-%CLI_VERSION%.zip dist\snow
