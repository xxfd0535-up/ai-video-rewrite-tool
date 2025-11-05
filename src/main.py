"""
🎬 视频文案AI爆款改写工具 - 程序入口
主程序入口点
"""

import sys
import os
import logging
from pathlib import Path

# 尽早设置以避免 OpenMP 运行时冲突（libiomp5md.dll 重复加载）
os.environ['KMP_DUPLICATE_LIB_OK'] = 'TRUE'

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from modules.config import CONFIG, get_config
from modules.utils import LogUtils, SystemUtils

def setup_environment():
    """设置运行环境"""
    try:
        # 设置环境变量
        os.environ['PYTHONIOENCODING'] = 'utf-8'
        os.environ['PYTHONUTF8'] = '1'
        # 解决 OpenMP 运行时冲突（libiomp5md.dll 重复）
        # 注意：此为临时规避方案，可在后续优化依赖版本时移除
        os.environ['KMP_DUPLICATE_LIB_OK'] = 'TRUE'

        # 设置日志
        LogUtils.setup_logging(
            log_level=CONFIG.get('system.log_level', 'INFO'),
            log_dir=CONFIG.get('system.log_dir', 'logs'),
            max_files=CONFIG.get('system.max_log_files', 10)
        )

        logger = logging.getLogger(__name__)
        logger.info("=" * 60)
        logger.info("🎬 视频文案AI爆款改写工具启动中...")
        logger.info("=" * 60)

        # 显示系统信息
        sys_info = SystemUtils.get_system_info()
        logger.info(f"系统信息: {sys_info.get('system', 'Unknown')} {sys_info.get('release', '')}")
        logger.info(f"Python版本: {sys_info.get('python_version', 'Unknown')}")
        logger.info(f"平台架构: {sys_info.get('machine', 'Unknown')}")

        # 检查配置
        config = get_config()
        logger.info(f"应用名称: {config.get('app.name')}")
        logger.info(f"应用版本: {config.get('app.version')}")

        # 检查必要目录
        config.create_directories()

        # 检查GPU支持并优化Whisper配置
        try:
            import torch
            if torch.cuda.is_available():
                gpu_name = torch.cuda.get_device_name(0)
                gpu_memory = torch.cuda.get_device_properties(0).total_memory / 1024**3
                logger.info(f"GPU检测: {gpu_name} ({gpu_memory:.1f}GB)")

                # 强制设置Whisper使用GPU
                if config.get('whisper.device') != 'cuda':
                    config.set('whisper.device', 'cuda')
                    logger.info("已自动配置Whisper使用GPU加速")

                # 根据GPU内存大小优化Whisper模型选择
                if gpu_memory >= 8:
                    if config.get('whisper.model') == 'small':
                        logger.info("检测到充足GPU内存，建议使用medium或large模型以提升识别准确率")
                elif gpu_memory >= 4:
                    if config.get('whisper.model') == 'large':
                        logger.info("GPU内存有限，建议使用medium模型以避免内存不足")
            else:
                logger.info("GPU检测: 未检测到CUDA支持，将使用CPU模式")
                # 确保CPU模式配置正确
                if config.get('whisper.device') == 'cuda':
                    config.set('whisper.device', 'cpu')
                    logger.info("已自动调整Whisper为CPU模式")
        except ImportError:
            logger.info("GPU检测: PyTorch未安装，使用CPU模式")
            # 确保在没有PyTorch时使用CPU
            if config.get('whisper.device') == 'cuda':
                config.set('whisper.device', 'cpu')
                logger.info("已自动调整Whisper为CPU模式")

        return True

    except Exception as e:
        logging.error(f"环境设置失败: {e}")
        return False

def check_dependencies():
    """检查依赖组件"""
    logger = logging.getLogger(__name__)
    logger.info("检查依赖组件...")

    missing_deps = []
    optional_deps = []

    # 必需依赖
    try:
        import PyQt5
        logger.info("✅ PyQt5 已安装")
    except ImportError:
        missing_deps.append("PyQt5")

    try:
        import whisper
        logger.info("✅ Whisper 已安装")
    except ImportError:
        missing_deps.append("Whisper")

    try:
        import requests
        logger.info("✅ Requests 已安装")
    except ImportError:
        missing_deps.append("Requests")

    # 可选依赖
    try:
        import torch
        if hasattr(torch, 'cuda') and torch.cuda.is_available():
            logger.info("✅ PyTorch + CUDA 已安装")
        else:
            logger.info("⚠️ PyTorch 已安装但CUDA不可用")
    except ImportError:
        optional_deps.append("PyTorch (CPU模式可用)")

    try:
        import soundfile
        logger.info("✅ SoundFile 已安装")
    except ImportError:
        optional_deps.append("SoundFile (音频文件处理)")

    try:
        import cv2
        logger.info("✅ OpenCV 已安装")
    except ImportError:
        optional_deps.append("OpenCV (视频信息获取)")

    try:
        import psutil
        logger.info("✅ psutil 已安装")
    except ImportError:
        optional_deps.append("psutil (系统监控)")

    # 检查FFmpeg
    if SystemUtils.check_command_exists('ffmpeg'):
        logger.info("✅ FFmpeg 已安装")
    else:
        missing_deps.append("FFmpeg")

    # 检查Ollama
    if SystemUtils.check_command_exists('ollama'):
        try:
            import requests
            response = requests.get('http://localhost:11434', timeout=2)
            if response.status_code == 200:
                logger.info("✅ Ollama 服务正在运行")
            else:
                logger.warning("⚠️ Ollama 已安装但服务未运行")
        except:
            logger.warning("⚠️ Ollama 已安装但服务未运行")
    else:
        optional_deps.append("Ollama (AI文案改写)")

    # 报告结果
    if missing_deps:
        logger.error("❌ 缺少必需依赖:")
        for dep in missing_deps:
            logger.error(f"   - {dep}")
        logger.error("请安装缺失的依赖后重试")
        return False

    if optional_deps:
        logger.warning("⚠️ 建议安装的可选依赖:")
        for dep in optional_deps:
            logger.warning(f"   - {dep}")

    return True

def cleanup_old_files():
    """清理旧文件"""
    logger = logging.getLogger(__name__)
    try:
        # 清理临时文件
        temp_dir = Path(CONFIG.get('system.temp_dir', 'temp'))
        if temp_dir.exists():
            import time
            current_time = time.time()
            cleanup_days = CONFIG.get('system.cleanup_days', 7)

            for file_path in temp_dir.rglob('*'):
                if file_path.is_file():
                    file_age = current_time - file_path.stat().st_mtime
                    if file_age > cleanup_days * 24 * 60 * 60:  # 超过N天
                        try:
                            file_path.unlink()
                            logger.debug(f"清理旧文件: {file_path}")
                        except:
                            pass

        # 清理旧日志
        if CONFIG.get('system.auto_cleanup', True):
            LogUtils.clear_old_logs(
                log_dir=CONFIG.get('system.log_dir', 'logs'),
                days=CONFIG.get('system.cleanup_days', 7)
            )

        logger.info("旧文件清理完成")

    except Exception as e:
        logger.warning(f"清理旧文件失败: {e}")

def main():
    """主函数"""
    logger = None
    try:
        # 初始化基础logger
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        logger = logging.getLogger(__name__)

        print("视频文案AI爆款改写工具 v1.0")
        print("=" * 50)

        # 环境设置
        if not setup_environment():
            print("环境设置失败，程序退出")
            return 1

        # 依赖检查
        if not check_dependencies():
            print("依赖检查失败，程序退出")
            return 1

        # 清理旧文件
        cleanup_old_files()

        logger.info("环境检查完成，启动图形界面...")

        # 延迟导入，避免 PyQt5 未安装时在模块导入阶段报错
        from modules.app import main as gui_main
        # 启动图形界面
        return gui_main()

    except KeyboardInterrupt:
        if logger:
            logger.info("用户中断，程序退出")
        print("用户中断，程序退出")
        return 0
    except Exception as e:
        if logger:
            logger.critical(f"程序启动失败: {e}")
        print(f"程序启动失败: {e}")
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)