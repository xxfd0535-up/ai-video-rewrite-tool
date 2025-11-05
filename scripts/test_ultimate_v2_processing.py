# -*- coding: utf-8 -*-
"""
自动化测试：调用终极修复版处理流程（ultimate_app_fixed_v2）
- 直接执行 UltimateWorkerThread._process_video_ultimate 进行端到端验证
- 避免 GUI 交互，确保处理管线稳定
"""
import sys
from pathlib import Path

# 确保可以导入 src 下的模块
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src' / 'modules'))
sys.path.insert(0, str(ROOT / 'src'))

from modules import enhanced_logging  # type: ignore
from ultimate_app_fixed_v2 import UltimateWorkerThread, get_logger


def run_test(video_path: Path):
    # 初始化日志
    try:
        enhanced_logging.setup_logging(ROOT / 'logs', 'INFO')
    except Exception:
        pass
    logger = get_logger('ultimate_v2_test')

    if not video_path.exists():
        print(f"测试失败：找不到视频文件 {video_path}")
        return 1

    logger.info(f"开始端到端测试，视频: {video_path}")

    # 构造工作线程实例（不启动线程，直接调用处理方法）
    worker = UltimateWorkerThread(
        'process_video_ultimate',
        video_path=str(video_path),
        config_manager=None,
    )

    try:
        result = worker._process_video_ultimate()  # 直接调用以避免 Qt 事件循环依赖
    except Exception as e:
        logger.error(f"处理异常: {e}")
        print("RESULT: FAIL")
        return 2

    # 输出结果摘要
    success = bool(result.get('success'))
    original_text = result.get('original_text', '')
    rewritten = result.get('rewritten_texts', {})
    video_info = result.get('video_info', {})

    print("RESULT:", "OK" if success else "FAIL")
    print("VIDEO_INFO:", video_info)
    print("ORIGINAL_TEXT_LEN:", len(original_text))
    print("REWRITTEN_STYLES:", list(rewritten.keys()))

    return 0 if success else 3


if __name__ == '__main__':
    # 默认使用仓库根目录下的 temp/001.mp4
    default_video = ROOT / 'temp' / '001.mp4'
    exit_code = run_test(default_video)
    sys.exit(exit_code)