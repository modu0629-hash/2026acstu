@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo  수복이 합본 갱신 — *.meta.json 모두 자동 갱신
echo ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo.
python merge.py
echo.
echo ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo  완료. 아무 키나 누르면 종료.
pause >nul
