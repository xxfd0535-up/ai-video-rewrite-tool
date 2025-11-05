@echo off
REM 日志清理批处理脚本，支持传入参数，例如 --days 7 --max-size-mb 50 --dry-run
REM 将工作目录切换到项目根目录（本脚本位于 scripts/ 下）
cd /d "%~dp0.."

echo [INFO] Using project root: %CD%
echo [INFO] Running: conda run -n video_rewrite_env_py312 python -u scripts\clear_logs.py %*
conda run -n video_rewrite_env_py312 python -u scripts\clear_logs.py %*

echo.
echo [DONE] 日志清理完成。保留此窗口以查看输出结果。
pause