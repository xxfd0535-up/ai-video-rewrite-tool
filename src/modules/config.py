"""
🎬 配置管理模块
统一管理和访问应用程序配置
"""

import json
import os
import logging
from typing import Dict, Any, Optional, Union
from pathlib import Path

logger = logging.getLogger(__name__)

class ConfigManager:
    """配置管理器"""

    def __init__(self, config_file: str = "config/settings.json"):
        self.config_file = Path(config_file)
        self.config_data: Dict[str, Any] = {}
        self._load_config()
        logger.info("🔧 配置管理器初始化完成")

    def _load_config(self) -> None:
        """加载配置文件"""
        try:
            if not self.config_file.exists():
                logger.warning(f"配置文件不存在: {self.config_file}")
                self._create_default_config()
                return

            with open(self.config_file, 'r', encoding='utf-8') as f:
                self.config_data = json.load(f)

            logger.info(f"配置文件加载成功: {self.config_file}")
            self._validate_config()

        except json.JSONDecodeError as e:
            logger.error(f"配置文件格式错误: {e}")
            self._create_default_config()
        except Exception as e:
            logger.error(f"配置文件加载失败: {e}")
            self._create_default_config()

    def _create_default_config(self) -> None:
        """创建默认配置"""
        default_config = {
            "app": {
                "name": "AI视频文案改写工具",
                "version": "1.0.0",
                "window_title": "🎬 AI视频文案改写工具 v1.0",
                "window_size": {"width": 1200, "height": 800}
            },
            "whisper": {
                "model": "small",
                "language": "zh",
                "device": "auto",
                "temperature": 0.0
            },
            "ollama": {
                "url": "http://localhost:11434/api/generate",
                "model": "deepseek-r1:8b",
                "timeout": 600,
                "max_retries": 3,
                "retry_delay": 2,
                "stream": false,
                "system_prompt": "你是一位创作过1000多个爆款短视频专家，请你从以下几个角度拆解。\n1.脚本结构：从开篇、中间发展、结尾的逻辑层次进行详细剖；\n2.表述风格：通过具体语言风格的分析，提炼出让文案更贴近目标受众的写作技巧；\n3.爆款逻辑：解析文案如何通过痛点刺激、数据支撑等逻辑驱动用户行动；\n4.开头三秒：聚焦文案开头,分析如何迅速抓住读者的注意力；\n5.钩子设计:识别出文章中多处钩子设计,不断吸引用户继续阅读；\n6.爆款表达方法论：总结出文案成功的关键要素，并提炼出可操作的写作建议。\n在拆解完文案以后,请你结合下面的要求,帮我对该文案进行仿写：\n1.文案的开头必须与原文一致，不得更改；\n2.避免使用过于常见的广告语或套路化的表达,确保内容的新颖性和独特性；\n3.文案必须保证50%的原创度,但整体内容的意思禁止改变。\n严格要求：只输出仿写后的文案，不要输出任何解释、分析或多余内容。"
            },
            "audio": {
                "sample_rate": 16000,
                "channels": 1,
                "format": "wav",
                "temp_dir": "temp"
            },
            "video": {
                "supported_formats": [".mp4", ".mov", ".mkv", ".avi", ".flv", ".wmv", ".webm"],
                "max_file_size_mb": 500
            },
            "ui": {
                "font_family": "Microsoft YaHei",
                "font_size": 10,
                "theme": "light"
            }
        }

        self.config_data = default_config
        self.save_config()
        logger.info("默认配置文件已创建")

    def _validate_config(self) -> None:
        """验证配置文件"""
        required_sections = ['app', 'whisper', 'ollama', 'audio', 'video', 'ui']

        for section in required_sections:
            if section not in self.config_data:
                logger.warning(f"配置缺少必要部分: {section}")
                self.config_data[section] = {}

    def get(self, key: str, default: Any = None) -> Any:
        """
        获取配置值，支持嵌套键访问

        Args:
            key: 配置键，支持点分隔的嵌套键，如 'whisper.model'
            default: 默认值

        Returns:
            配置值
        """
        try:
            keys = key.split('.')
            value = self.config_data

            for k in keys:
                value = value[k]

            return value
        except (KeyError, TypeError):
            logger.debug(f"配置键不存在: {key}，使用默认值: {default}")
            return default

    def set(self, key: str, value: Any) -> None:
        """
        设置配置值，支持嵌套键设置

        Args:
            key: 配置键，支持点分隔的嵌套键
            value: 配置值
        """
        keys = key.split('.')
        config = self.config_data

        # 导航到最后一层
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]

        # 设置值
        config[keys[-1]] = value
        logger.debug(f"配置已更新: {key} = {value}")

    def get_section(self, section: str) -> Dict[str, Any]:
        """
        获取整个配置段

        Args:
            section: 配置段名

        Returns:
            配置段字典
        """
        return self.config_data.get(section, {})

    def save_config(self) -> bool:
        """
        保存配置到文件

        Returns:
            保存是否成功
        """
        try:
            # 确保目录存在
            self.config_file.parent.mkdir(parents=True, exist_ok=True)

            # 保存配置
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config_data, f, indent=2, ensure_ascii=False)

            logger.info(f"配置文件保存成功: {self.config_file}")
            return True

        except Exception as e:
            logger.error(f"配置文件保存失败: {e}")
            return False

    def reset_to_default(self) -> None:
        """重置为默认配置"""
        self._create_default_config()
        logger.info("配置已重置为默认值")

    def get_whisper_config(self) -> Dict[str, Any]:
        """获取Whisper配置"""
        return self.get_section('whisper')

    def get_ollama_config(self) -> Dict[str, Any]:
        """获取Ollama配置"""
        return self.get_section('ollama')

    def get_audio_config(self) -> Dict[str, Any]:
        """获取音频处理配置"""
        return self.get_section('audio')

    def get_video_config(self) -> Dict[str, Any]:
        """获取视频处理配置"""
        return self.get_section('video')

    def get_ui_config(self) -> Dict[str, Any]:
        """获取用户界面配置"""
        return self.get_section('ui')

    def get_system_config(self) -> Dict[str, Any]:
        """获取系统配置"""
        return self.get_section('system', {
            'log_level': 'INFO',
            'log_dir': 'logs',
            'temp_dir': 'temp'
        })

    def is_gpu_enabled(self) -> bool:
        """检查是否启用GPU"""
        device = self.get('whisper.device', 'auto')
        return device == 'cuda' or device == 'auto'

    def get_supported_video_formats(self) -> list:
        """获取支持的视频格式"""
        return self.get('video.supported_formats', ['.mp4', '.mov', '.mkv'])

    def get_max_file_size(self) -> int:
        """获取最大文件大小（字节）"""
        size_mb = self.get('video.max_file_size_mb', 500)
        return size_mb * 1024 * 1024

    def create_directories(self) -> None:
        """创建必要的目录"""
        directories = [
            self.get('system.temp_dir', 'temp'),
            self.get('system.log_dir', 'logs'),
            self.get('advanced.results_dir', 'results'),
            'models/whisper'
        ]

        for directory in directories:
            Path(directory).mkdir(parents=True, exist_ok=True)
            logger.debug(f"创建目录: {directory}")

# 全局配置实例
CONFIG = ConfigManager()

# 确保必要目录存在
CONFIG.create_directories()

def get_config() -> ConfigManager:
    """获取全局配置实例"""
    return CONFIG

if __name__ == "__main__":
    # 测试配置管理器
    config = ConfigManager()

    print("=== 配置测试 ===")
    print(f"应用名称: {config.get('app.name')}")
    print(f"Whisper模型: {config.get('whisper.model')}")
    print(f"Ollama模型: {config.get('ollama.model')}")
    print(f"GPU启用: {config.is_gpu_enabled()}")
    print(f"支持格式: {config.get_supported_video_formats()}")

    # 测试嵌套访问
    config.set('test.nested.value', '测试值')
    print(f"嵌套测试: {config.get('test.nested.value')}")