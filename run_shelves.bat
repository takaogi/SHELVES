@echo off
cd /d %~dp0
echo 現在のディレクトリ: %CD%

if not exist .venv\Scripts\activate (
    echo 仮想環境が見つかりません。
    pause
    exit /b
)

call .venv\Scripts\activate

if not exist main.py (
    echo main.py が見つかりません。
    pause
    exit /b
)

python main.py


