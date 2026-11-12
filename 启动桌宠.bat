@echo off
chcp 936 >nul 2>nul
setlocal
cd /d "%~dp0"

rem 优先用系统 Python（依赖齐全时秒开），否则用独立虚拟环境
where python >nul 2>nul
if errorlevel 1 goto need_python

python -c "import PyQt6, imageio_ffmpeg" >nul 2>nul
if errorlevel 1 goto try_venv

start "" pythonw "%~dp0main.py"
exit /b 0

:try_venv
if exist "%~dp0.venv\Scripts\pythonw.exe" goto run_venv

echo 首次启动：正在准备运行环境，请稍候...
python -m venv "%~dp0.venv"
if errorlevel 1 goto failed
"%~dp0.venv\Scripts\python.exe" -m pip install --upgrade pip
"%~dp0.venv\Scripts\python.exe" -m pip install -r "%~dp0requirements.txt"
if errorlevel 1 goto failed

:run_venv
start "" "%~dp0.venv\Scripts\pythonw.exe" "%~dp0main.py"
exit /b 0

:need_python
echo 未检测到 Python。
echo 请先安装 Python 3.10 或更高版本：https://www.python.org/downloads/
echo 安装时务必勾选 "Add Python to PATH"。
pause
exit /b 1

:failed
echo.
echo 运行环境安装失败，请检查网络后重新双击本文件。
pause
exit /b 1
