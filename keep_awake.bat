@echo off
REM ── Keep this machine awake during the long autonomous build/test loop ───────
REM Disables sleep/monitor timeouts on AC and battery, then launches a hidden
REM PowerShell that pins SetThreadExecutionState (system + display required) and
REM re-affirms every ~3.5 minutes. Close the hidden PowerShell (Task Manager) or
REM reboot to stop it.
powercfg /change standby-timeout-ac 0
powercfg /change monitor-timeout-ac 0
powercfg /change hibernate-timeout-ac 0
powercfg /change standby-timeout-dc 0
powercfg /change monitor-timeout-dc 0

REM Pin system+display awake AND send a harmless {F15} key every 60s so Windows'
REM idle timer never triggers the LOCK screen. (F15 does nothing in apps.)
start "keepawake" /min powershell -NoProfile -WindowStyle Hidden -Command "Add-Type -Name P -Namespace W -MemberDefinition '[DllImport(\"kernel32.dll\")] public static extern uint SetThreadExecutionState(uint e);'; $sh = New-Object -ComObject WScript.Shell; while($true){ [W.P]::SetThreadExecutionState(2147483651) ^| Out-Null; try { $sh.SendKeys('{F15}') } catch {}; Start-Sleep -Seconds 60 }"

echo Keep-awake started (sleep + idle-lock prevention).
