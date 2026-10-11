@echo off
setlocal

powershell -NoProfile -Command "try { Invoke-WebRequest -Uri 'http://127.0.0.1:5090/api/v1/scan?full=true' -Method POST -UseBasicParsing | Out-Null; Write-Host 'SCAN=FULL_STARTED' } catch { Write-Host ('SCAN=FAILED ' + $_) }"

pause
endlocal
