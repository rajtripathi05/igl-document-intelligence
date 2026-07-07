@echo off
REM Commit all work and push to origin/main. Refuses to run if .env is staged.
cd /d "%~dp0"
set "LOG=outputs\git_push_log.txt"
if not exist outputs mkdir outputs
echo === IGL git push  %DATE% %TIME% === > "%LOG%"

REM Never track secrets or temporary artifacts.
git rm --cached .env >nul 2>&1
git rm -r --cached _preview >nul 2>&1
git rm --cached outputs\health.txt >nul 2>&1

git add -A >> "%LOG%" 2>&1

REM Safety gate: abort if .env somehow got staged.
git diff --cached --name-only | findstr /i /x ".env" >nul 2>&1
if %errorlevel%==0 (
    echo ABORTED: .env is staged - refusing to push secrets. >> "%LOG%"
    git reset .env >> "%LOG%" 2>&1
    goto done
)

echo --- staged file count: >> "%LOG%"
git diff --cached --name-only | find /c /v "" >> "%LOG%"

git -c user.name="rajtripathi05" -c user.email="ai@indiaglycols.com" commit -m "Add Log Book (Plant Operations) processor; rework IGP output to 38-col Data format with multi-entry consolidation + field normalization; add benchmarks, launchers, deployment config" >> "%LOG%" 2>&1

echo --- pushing to origin main --- >> "%LOG%"
git push origin main >> "%LOG%" 2>&1

:done
echo --- latest commit --- >> "%LOG%"
git log --oneline -1 >> "%LOG%" 2>&1
echo --- working tree status --- >> "%LOG%"
git status --short >> "%LOG%" 2>&1
echo === FINISHED === >> "%LOG%"
