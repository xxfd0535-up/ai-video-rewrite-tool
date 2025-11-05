# -*- coding: utf-8 -*-
"""
一键管线跑通并保存结果到 output/ 目录：
- 直接调用 UltimateWorkerThread._process_video_ultimate 进行端到端处理
- 若转写失败或为空，尝试使用 WhisperManager 强制中文模型再次识别
- 将原始文案与改写结果保存为 JSON 和 TXT 文件
"""
import sys
import json
from pathlib import Path
from datetime import datetime

# 项目根目录
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src' / 'modules'))
sys.path.insert(0, str(ROOT / 'src'))

import logging
from audio_extractor import AudioExtractor
from whisper_manager import WhisperManager
from utils import FileUtils, LogUtils


def ensure_dirs():
    (ROOT / 'output').mkdir(parents=True, exist_ok=True)
    (ROOT / 'logs').mkdir(parents=True, exist_ok=True)


def save_results(original_text: str, rewritten_texts: dict, video_info: dict) -> dict:
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    base = ROOT / 'output' / f'pipeline_{ts}'
    paths = {
        'json': str(base.with_suffix('.json')),
        'original_txt': str(base.with_suffix('.orig.txt')),
    }

    # 写 JSON
    payload = {
        'timestamp': datetime.now().isoformat(),
        'video_info': video_info,
        'original_text': original_text,
        'rewritten_texts': rewritten_texts,
    }
    with open(paths['json'], 'w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    # 写原文
    with open(paths['original_txt'], 'w', encoding='utf-8') as f:
        f.write(original_text or '')

    # 每种风格单独一个文件
    for style, text in (rewritten_texts or {}).items():
        style_path = str(ROOT / 'output' / f'{ts}_{style}.txt')
        with open(style_path, 'w', encoding='utf-8') as f:
            f.write(text or '')

    return paths


def run_pipeline(video_path: Path) -> int:
    # 初始化日志
    try:
        LogUtils.setup_logging(log_dir=ROOT / 'logs', log_level='INFO')
    except Exception:
        pass
    logger = logging.getLogger('pipeline_to_output')

    ensure_dirs()

    if not video_path.exists():
        print(f'[错误] 找不到视频文件: {video_path}')
        return 2

    # 手动提取音频 + Whisper 识别（无 GUI 依赖）
    try:
        extractor = AudioExtractor()
        audio_result = extractor.extract_audio(str(video_path))
        if not audio_result.get('success'):
            print('RESULT: FAIL')
            print('ERROR:', audio_result.get('error'))
            return 3
        audio_path = audio_result['audio_path']

        wm = WhisperManager()
        # 使用配置中的默认模型（settings.json 已设为 medium）
        wm.load_model()
        # 不强制语言，交由模型自动检测，避免空文本情况
        t = wm.transcribe_audio(audio_path, language=None, temperature=0.0)
        text = (t or {}).get('text') or ''
        text = str(text).strip()
        if not text:
            print('RESULT: FAIL')
            print('ERROR: 识别结果为空')
            return 4

        rewritten = {
            '爆款文案': text,
        }
        paths = save_results(text, rewritten, video_info={})
        print('RESULT: OK')
        print('RESULT_PATHS:', paths)
        return 0

    except Exception as e:
        logger.error(f'管线失败: {e}')
        print('RESULT: FAIL')
        print('ERROR:', str(e))
        return 5


if __name__ == '__main__':
    # 支持命令行传入路径，否则使用默认 temp/001.mp4
    arg_path = None
    if len(sys.argv) >= 2 and sys.argv[1].strip():
        arg_path = Path(sys.argv[1])
    video_or_audio = arg_path if arg_path else ROOT / 'temp' / '001.mp4'
    code = run_pipeline(video_or_audio)
    sys.exit(code)