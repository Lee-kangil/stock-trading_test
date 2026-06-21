@echo off
chcp 65001 > nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
cd /d "%USERPROFILE%\Claude\Projects\Stock_TickerFind"
call ".venv\Scripts\activate.bat"
echo ===== %date% %time% ===== >> "data\run_kis.log"
python -u src\run_live.py >> "data\run_kis.log" 2>&1
