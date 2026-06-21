@echo off
chcp 65001 > nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
cd /d "%USERPROFILE%\Claude\Projects\Stock_TickerFind"
call ".venv\Scripts\activate.bat"
echo ===== %date% %time% ===== >> "data\run_paper.log"
python -u src\multi_paper.py >> "data\run_paper.log" 2>&1
python -u src\report.py >> "data\run_paper.log" 2>&1
