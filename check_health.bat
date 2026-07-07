@echo off
cd /d "%~dp0"
powershell -NoProfile -Command "try { $r = Invoke-WebRequest 'http://localhost:8501/_stcore/health' -UseBasicParsing -TimeoutSec 12; Write-Output ('LOCALHOST 8501 -> STATUS ' + $r.StatusCode + ' BODY ' + $r.Content) } catch { Write-Output ('LOCALHOST 8501 -> ERROR ' + $_.Exception.Message) }" > outputs\health.txt 2>&1
