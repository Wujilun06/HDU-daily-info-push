@echo off
REM 每日信息整合推送 —— 一键运行（供 Windows 任务计划程序调用）
cd /d %~dp0
if exist "venv\Scripts\activate.bat" call "venv\Scripts\activate.bat"
python main.py --once
