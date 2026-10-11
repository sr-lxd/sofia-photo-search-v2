@echo off
setlocal

powershell -NoProfile -Command "try { Invoke-WebRequest -Uri 'http://127.0.0.1:5090/api/v1/status' -UseBasicParsing -Proxy $null -TimeoutSec 3 -ErrorAction Stop | Out-Null; exit 0 } catch { exit 1 }"
if errorlevel 1 goto :start_service
goto :run_scan

:start_service
echo [INFO] Service is not running on 5090. Starting service...
call "%~dp0启动照片搜索(仅启动).bat" --no-pause
if errorlevel 1 (
  echo [ERROR] Failed to start service.
  pause
  exit /b 1
)

powershell -NoProfile -Command "try { Start-Sleep -Seconds 2; Invoke-WebRequest -Uri 'http://127.0.0.1:5090/api/v1/status' -UseBasicParsing -Proxy $null -TimeoutSec 5 -ErrorAction Stop | Out-Null; exit 0 } catch { exit 1 }"
if errorlevel 1 (
  echo [ERROR] Service failed to become ready on 5090.
  pause
  exit /b 1
)

:run_scan
powershell -NoProfile -Command "try { Invoke-WebRequest -Uri 'http://127.0.0.1:5090/api/v1/scan' -Method POST -UseBasicParsing -Proxy $null -TimeoutSec 10 -ErrorAction Stop | Out-Null; Write-Host 'SCAN=INCREMENTAL_STARTED'; exit 0 } catch { Write-Host ('SCAN=FAILED ' + $_.Exception.Message); exit 1 }"
if errorlevel 1 (
  pause
  exit /b 1
)

pause
endlocal
