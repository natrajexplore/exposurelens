@echo off
rem Opens ExposureLens at https://nemocve.com on this PC only.
rem No hosts-file edit, no administrator rights, nothing installed in Windows' certificate store:
rem a dedicated Chrome profile maps nemocve.com to 127.0.0.1 and accepts only the local server key
rem pinned in certs\nemocve.spki. Needs the app serving HTTPS on 127.0.0.1:443 (see README).
setlocal
set "ROOT=%~dp0.."
set "PIN_FILE=%ROOT%\certs\nemocve.spki"
set "CHROME=%ProgramFiles%\Google\Chrome\Application\chrome.exe"
if not exist "%CHROME%" set "CHROME=%LocalAppData%\Google\Chrome\Application\chrome.exe"

curl -s -o nul --ssl-no-revoke -k https://127.0.0.1/api/health
if errorlevel 1 (
  echo ExposureLens is not answering on https://127.0.0.1 - start the HTTPS server first.
  pause
  exit /b 1
)
if not exist "%PIN_FILE%" (
  echo Missing %PIN_FILE% - create the local certificate first, see README.
  pause
  exit /b 1
)
set /p PIN=<"%PIN_FILE%"

start "" "%CHROME%" --user-data-dir="%TEMP%\nemocve-chrome-https" --host-resolver-rules="MAP nemocve.com 127.0.0.1, MAP www.nemocve.com 127.0.0.1" --ignore-certificate-errors-spki-list=%PIN% https://nemocve.com
endlocal
