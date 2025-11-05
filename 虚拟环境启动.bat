@echo off
rem ====== 自动激活 conda 环境并启动主程序 ======

set ENV_NAME=aiwriter312cf
set PY_SCRIPT=src/main.py

echo [INFO] 检查并激活 conda 环境: %ENV_NAME%
call conda activate %ENV_NAME%
if errorlevel 1 (
    echo [ERROR] conda 环境激活失败，请检查环境是否存在。
    pause
    exit /b 1
)

echo [INFO] 启动主程序: %PY_SCRIPT%
python %PY_SCRIPT%
if errorlevel 1 (
    echo [ERROR] 主程序运行失败，请检查依赖是否完整、模型参数设置及必要包是否安装。
    pause
    exit /b 2
)
echo.
echo ✅ 程序已正常启动，关闭窗口或按任意键退出。
pause
exit /b 0
