# -*- coding: utf-8 -*-
"""
自动化测试：调用终极完整优化版处理流程（ultimate_app）
- 直接执行 UltimateWorkerThread._process_video_ultimate 进行端到端验证
- 需要依赖：pydub（调用 ffmpeg）、whisper
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'src' / 'modules'))

import logging
from modules.utils import LogUtils
from modules.ultimate_app import UltimateWorkerThread


def run_test(video_path: Path, whisper_model: str = 'base'):
    # 初始化日志
    try:
        LogUtils.setup_logging(log_dir=ROOT / 'logs', log_level='INFO')
    except Exception:
        pass
    logger = logging.getLogger('ultimate_full_test')

    if not video_path.exists():
        print(f"测试失败：找不到视频文件 {video_path}")
        return 1

    logger.info(f"开始完整管线测试，视频: {video_path}")

    worker = UltimateWorkerThread(
        'process_video_ultimate',
        video_path=str(video_path),
        config_manager=None,
        whisper_model=whisper_model,
    )

    try:
        result = worker._process_video_ultimate()
    except Exception as e:
        logger.error(f"处理异常: {e}")
        print("RESULT: FAIL")
        return 2

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
    default_video = ROOT / 'temp' / '001.mp4'
    sys.exit(run_test(default_video))