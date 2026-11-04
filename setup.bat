@echo off
title Touch Grass Inc Tracker setup
cd /d "%~dp0"
echo ============================================
echo   Touch Grass Inc Tracker - one-time setup
echo ============================================
echo.
where pythonw >nul 2>nul
if errorlevel 1 (
  echo Python was not found. Install Python 3 from the Microsoft Store, then run this again.
  pause
  exit /b 1
)
for /f "delims=" %%P in ('where pythonw') do (
  set "PYW=%%P"
  goto :found
)
:found
echo Python found: %PYW%
python --version
echo.
findstr /c:"PASTE_CLAN_TAG" /c:"PASTE_CLASH_API_KEY_HERE" /c:"PASTE_GITHUB_USERNAME" /c:"PASTE_REPO_NAME" config.json >nul 2>nul
if not errorlevel 1 (
  echo config.json still has PASTE_ placeholders.
  echo Open config.json in Notepad, fill in your clan tag, API key, GitHub username and repo name, save, and run this again.
  pause
  exit /b 1
)
findstr /c:"PASTE_TOKEN_HERE" github_token.txt >nul 2>nul
if not errorlevel 1 (
  echo Your GitHub token isn't in github_token.txt yet.
  echo Open github_token.txt, replace PASTE_TOKEN_HERE with your token, save, and run this again.
  pause
  exit /b 1
)
echo Running the first update (about 30 seconds)...
python build_site.py
if errorlevel 1 (
  echo.
  echo The first update hit a problem. Open run_log.txt in this folder to see why.
  pause
  exit /b 1
)
echo.
echo Creating the Windows task (every 10 minutes)...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$a=New-ScheduledTaskAction -Execute '%PYW%' -Argument '\"%~dp0build_site.py\"' -WorkingDirectory '%~dp0'; $n=Get-Date; $start=$n.Date.AddHours($n.Hour).AddMinutes(5); while($start -le $n){$start=$start.AddMinutes(10)}; $t=New-ScheduledTaskTrigger -Once -At $start -RepetitionInterval (New-TimeSpan -Minutes 10); $s=New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Minutes 10); Register-ScheduledTask -TaskName 'Touch Grass Inc Tracker' -Action $a -Trigger $t -Settings $s -Description 'Every-10-min Clash data pull, page build, GitHub upload' -Force | Out-Null; if($?){'Task created (every 10 min). First run: ' + $start.ToString('h:mm tt')}"
echo.
for /f "delims=" %%U in ('python -c "import json;c=json.load(open('config.json',encoding='utf-8'));print('https://'+c['githubUser'].lower()+'.github.io/'+c['githubRepo']+'/')"') do set "SITE=%%U"
echo All set. Your site: %SITE%
echo (GitHub can take a few minutes to publish it the first time.)
echo.
pause
