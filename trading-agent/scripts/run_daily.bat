@echo off
rem SMZ Trader 日次実行ラッパー(Windows / bash不要)。
rem Task Scheduler からこの .bat を1日1回叩くだけで、一時的なネットワーク障害を
rem 数回リトライしてから諦める(諦めても翌日のスケジュール実行には影響しない)。
setlocal enabledelayedexpansion

cd /d "%~dp0.."
set "REPO_ROOT=%cd%"
set "PYTHONPATH=%REPO_ROOT%\src"
if not exist "%REPO_ROOT%\state" mkdir "%REPO_ROOT%\state"
set "LOG_FILE=%REPO_ROOT%\state\cron.log"

rem secrets.env があれば読み込む(簡易パーサ: KEY=VALUE 形式・コメント行#は無視)
if exist "%REPO_ROOT%\config\secrets.env" (
  for /f "usebackq eol=# tokens=1,* delims==" %%A in ("%REPO_ROOT%\config\secrets.env") do (
    if not "%%A"=="" set "%%A=%%B"
  )
)

if not defined SMZ_DAILY_MAX_RETRIES set "SMZ_DAILY_MAX_RETRIES=3"
if not defined SMZ_DAILY_RETRY_DELAY set "SMZ_DAILY_RETRY_DELAY=90"

set /a attempt=1
:retry
echo [%date% %time%] run-daily 開始 (試行 %attempt%/%SMZ_DAILY_MAX_RETRIES%) >> "%LOG_FILE%"
python -m smz_trader --config "%REPO_ROOT%\config\config.toml" run-daily %* >> "%LOG_FILE%" 2>&1
if %errorlevel%==0 (
  echo [%date% %time%] run-daily 成功 >> "%LOG_FILE%"
  exit /b 0
)
echo [%date% %time%] run-daily 失敗(終了コード %errorlevel%、試行 %attempt%/%SMZ_DAILY_MAX_RETRIES%) >> "%LOG_FILE%"
if %attempt% GEQ %SMZ_DAILY_MAX_RETRIES% (
  echo [%date% %time%] %SMZ_DAILY_MAX_RETRIES%回とも失敗。今日は諦めます(明日また自動実行されます) >> "%LOG_FILE%"
  exit /b 1
)
echo [%date% %time%] %SMZ_DAILY_RETRY_DELAY%秒後にリトライします >> "%LOG_FILE%"
timeout /t %SMZ_DAILY_RETRY_DELAY% /nobreak >nul
set /a attempt+=1
goto retry
