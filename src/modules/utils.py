"""
🎬 工具函数模块
提供各种实用工具函数
"""

import os
import logging
import platform
import subprocess
from pathlib import Path
from typing import List, Dict, Any, Optional, Union
import re

logger = logging.getLogger(__name__)

class VideoUtils:
    """视频处理工具类"""

    @staticmethod
    def is_video_file(file_path: Union[str, Path]) -> bool:
        """检查是否为视频文件"""
        video_extensions = {'.mp4', '.mov', '.mkv', '.avi', '.flv', '.wmv', '.webm'}
        return Path(file_path).suffix.lower() in video_extensions

    @staticmethod
    def get_video_info(file_path: Union[str, Path]) -> Dict[str, Any]:
        """获取视频信息"""
        try:
            # 先获取文件大小（非阻塞操作）
            file_size = os.path.getsize(file_path)
            file_size_mb = round(file_size / (1024 * 1024), 2)
            
            # 尝试使用ffprobe作为首选方法（更可靠且通常更快）
            try:
                import subprocess
                cmd = [
                    'ffprobe',
                    '-v', 'quiet',
                    '-print_format', 'json',
                    '-show_format',
                    '-show_streams',
                    str(file_path)
                ]
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=5, encoding='utf-8', errors='ignore')
                
                if result.returncode == 0:
                    import json
                    data = json.loads(result.stdout)
                    
                    # 提取视频信息
                    streams = data.get('streams', [])
                    video_stream = next((s for s in streams if s.get('codec_type') == 'video'), None)
                    
                    # 默认值
                    duration = 0
                    resolution = "未知"
                    fps = 0
                    frame_count = 0
                    
                    # 从format部分获取时长
                    if 'format' in data and 'duration' in data['format']:
                        duration = float(data['format']['duration'])
                    
                    # 从视频流获取分辨率和帧率
                    if video_stream:
                        width = video_stream.get('width', 0)
                        height = video_stream.get('height', 0)
                        if width > 0 and height > 0:
                            resolution = f"{width}x{height}"
                        
                        # 获取帧率
                        if 'r_frame_rate' in video_stream:
                            try:
                                num, den = map(int, video_stream['r_frame_rate'].split('/'))
                                fps = num / den if den > 0 else 0
                            except:
                                fps = 0
                        
                        # 尝试计算帧数
                        if fps > 0 and duration > 0:
                            frame_count = int(duration * fps)
                    
                    return {
                        'duration': duration,
                        'fps': fps,
                        'frame_count': frame_count,
                        'resolution': resolution,
                        'file_size': file_size,
                        'file_size_mb': file_size_mb
                    }
            except Exception as ffprobe_error:
                logger.warning(f"FFprobe调用失败，尝试使用OpenCV: {ffprobe_error}")
            
            # 备用方案：使用OpenCV
            try:
                import cv2
                # 设置读取超时，避免长时间阻塞
                cap = cv2.VideoCapture(str(file_path))
                cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # 减少缓冲区大小
                
                if not cap.isOpened():
                    # 返回基本信息，即使无法打开视频
                    return {
                        'duration': 0,
                        'fps': 0,
                        'frame_count': 0,
                        'resolution': "无法确定",
                        'file_size': file_size,
                        'file_size_mb': file_size_mb
                    }

                # 获取视频信息
                fps = cap.get(cv2.CAP_PROP_FPS)
                frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

                duration = frame_count / fps if fps > 0 else 0

                cap.release()

                return {
                    'duration': duration,
                    'fps': fps,
                    'frame_count': frame_count,
                    'resolution': f"{width}x{height}" if width > 0 and height > 0 else "无法确定",
                    'file_size': file_size,
                    'file_size_mb': file_size_mb
                }
            except ImportError:
                logger.warning("OpenCV未安装")
            except Exception as cv2_error:
                logger.error(f"OpenCV读取视频失败: {cv2_error}")
            
            # 最低限度的信息返回（仅文件大小）
            return {
                'duration': 0,
                'fps': 0,
                'frame_count': 0,
                'resolution': "未知",
                'file_size': file_size,
                'file_size_mb': file_size_mb
            }
        except Exception as e:
            logger.error(f"获取视频信息失败: {e}")
            # 即使出错也要返回基本信息
            try:
                file_size = os.path.getsize(file_path)
                return {
                    'duration': 0,
                    'fps': 0,
                    'frame_count': 0,
                    'resolution': "未知",
                    'file_size': file_size,
                    'file_size_mb': round(file_size / (1024 * 1024), 2)
                }
            except:
                return {
                    'duration': 0,
                    'fps': 0,
                    'frame_count': 0,
                    'resolution': "未知",
                    'file_size': 0,
                    'file_size_mb': 0
                }

    @staticmethod
    def validate_video_file(file_path: Union[str, Path], max_size_mb: int = 500) -> Dict[str, Any]:
        """验证视频文件"""
        result = {
            'valid': False,
            'errors': [],
            'warnings': [],
            'info': {}
        }

        try:
            path = Path(file_path)

            # 检查文件存在
            if not path.exists():
                result['errors'].append('文件不存在')
                return result

            # 检查文件格式
            if not VideoUtils.is_video_file(path):
                result['errors'].append('不支持的文件格式')
                return result

            # 检查文件大小
            file_size_mb = path.stat().st_size / (1024 * 1024)
            if file_size_mb > max_size_mb:
                result['warnings'].append(f'文件过大 ({file_size_mb:.1f}MB > {max_size_mb}MB)')

            # 获取视频信息
            video_info = VideoUtils.get_video_info(path)
            # 不再因为获取视频信息失败而直接返回错误
            # 即使无法获取完整信息，也可以尝试处理
            result['info'] = video_info

            # 检查视频时长（如果有）
            duration = video_info.get('duration', 0)
            if duration > 60 * 60:  # 超过1小时
                result['warnings'].append('视频时长超过1小时，处理时间可能较长')

            # 只在最基本的条件满足时就认为文件有效
            # 详细的视频格式检查可以在实际处理时进行
            result['valid'] = True
            return result

        except Exception as e:
            # 即使出错也只添加警告，而不是错误
            result['warnings'].append(f'验证时出现警告: {str(e)}')
            result['valid'] = True  # 允许尝试处理，因为get_video_info已经提供了基本信息
            return result

    @staticmethod
    def format_duration(seconds: float) -> str:
        """格式化时长显示"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)

        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{secs:02d}"
        else:
            return f"{minutes:02d}:{secs:02d}"

class FileUtils:
    """文件处理工具类"""

    @staticmethod
    def ensure_directory(directory: Union[str, Path]) -> Path:
        """确保目录存在"""
        path = Path(directory)
        path.mkdir(parents=True, exist_ok=True)
        return path

    @staticmethod
    def clean_filename(filename: str) -> str:
        """清理文件名，移除非法字符"""
        # Windows文件名非法字符
        illegal_chars = r'[<>:"/\\|?*]'
        cleaned = re.sub(illegal_chars, '_', filename)
        return cleaned.strip()

    @staticmethod
    def get_unique_filename(directory: Union[str, Path], base_name: str, extension: str) -> Path:
        """获取唯一的文件名"""
        dir_path = Path(directory)
        counter = 0
        filename = f"{base_name}{extension}"

        while (dir_path / filename).exists():
            counter += 1
            filename = f"{base_name}_{counter}{extension}"

        return dir_path / filename

    @staticmethod
    def safe_delete(file_path: Union[str, Path]) -> bool:
        """安全删除文件"""
        try:
            path = Path(file_path)
            if path.exists():
                path.unlink()
                logger.debug(f"文件已删除: {path}")
            return True
        except Exception as e:
            logger.warning(f"文件删除失败: {file_path}, 错误: {e}")
            return False

    @staticmethod
    def get_directory_size(directory: Union[str, Path]) -> int:
        """获取目录大小（字节）"""
        total_size = 0
        try:
            for dirpath, dirnames, filenames in os.walk(directory):
                for filename in filenames:
                    file_path = os.path.join(dirpath, filename)
                    if os.path.exists(file_path):
                        total_size += os.path.getsize(file_path)
        except Exception as e:
            logger.warning(f"目录大小计算失败: {e}")
        return total_size

class SystemUtils:
    """系统工具类"""

    @staticmethod
    def get_system_info() -> Dict[str, Any]:
        """获取系统信息"""
        return {
            'platform': platform.platform(),
            'system': platform.system(),
            'release': platform.release(),
            'version': platform.version(),
            'machine': platform.machine(),
            'processor': platform.processor(),
            'python_version': platform.python_version(),
            'hostname': platform.node(),
        }

    @staticmethod
    def check_command_exists(command: str) -> bool:
        """检查命令是否存在"""
        try:
            subprocess.run([command, '--version'],
                         capture_output=True,
                         timeout=5,
                         text=True,
                         encoding='utf-8',
                         errors='ignore')
            return True
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False

    @staticmethod
    def get_memory_info() -> Dict[str, Any]:
        """获取内存信息"""
        try:
            import psutil
            virtual_memory = psutil.virtual_memory()
            return {
                'total_gb': round(virtual_memory.total / 1024**3, 2),
                'available_gb': round(virtual_memory.available / 1024**3, 2),
                'used_gb': round(virtual_memory.used / 1024**3, 2),
                'usage_percent': virtual_memory.percent,
            }
        except ImportError:
            return {'error': 'psutil not available'}
        except Exception as e:
            return {'error': str(e)}

    @staticmethod
    def get_cpu_info() -> Dict[str, Any]:
        """获取CPU信息"""
        try:
            import psutil
            return {
                'physical_cores': psutil.cpu_count(logical=False),
                'logical_cores': psutil.cpu_count(logical=True),
                'current_frequency': psutil.cpu_freq().current if psutil.cpu_freq() else None,
                'max_frequency': psutil.cpu_freq().max if psutil.cpu_freq() else None,
                'usage_percent': psutil.cpu_percent(interval=1),
            }
        except ImportError:
            return {'error': 'psutil not available'}
        except Exception as e:
            return {'error': str(e)}

class TextUtils:
    """文本处理工具类"""

    @staticmethod
    def clean_text(text: str) -> str:
        """清理文本，移除多余空格和换行"""
        if not text:
            return ""

        # 移除首尾空格
        text = text.strip()

        # 替换多个空格为单个空格
        text = re.sub(r'\s+', ' ', text)

        # 移除空行
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        text = '\n'.join(lines)

        return text

    @staticmethod
    def extract_sentences(text: str) -> List[str]:
        """提取句子"""
        # 简单的中文句子分割
        sentences = re.split(r'[。！？；\n]+', text)
        return [s.strip() for s in sentences if s.strip()]

    @staticmethod
    def count_words(text: str) -> int:
        """计算字数（中文字符+英文单词）"""
        if not text:
            return 0

        # 移除标点符号
        text = re.sub(r'[^\w\s\u4e00-\u9fff]', '', text)

        # 统计中文字符
        chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))

        # 统计英文单词
        english_words = len(re.findall(r'[a-zA-Z]+', text))

        return chinese_chars + english_words

    @staticmethod
    def truncate_text(text: str, max_length: int, suffix: str = '...') -> str:
        """截断文本"""
        if len(text) <= max_length:
            return text

        return text[:max_length - len(suffix)] + suffix

    @staticmethod
    def format_duration(seconds: float) -> str:
        """把视频时长秒数格式化为 时:分:秒 或 分:秒"""
        try:
            seconds = int(float(seconds))
            h, m, s = seconds // 3600, (seconds % 3600) // 60, seconds % 60
            if h > 0:
                return f"{h:02d}:{m:02d}:{s:02d}"
            else:
                return f"{m:02d}:{s:02d}"
        except Exception:
            return "未知"

class LogUtils:
    """日志工具类"""

    @staticmethod
    def setup_logging(
        log_level: str = "INFO",
        log_dir: Union[str, Path] = "logs",
        max_files: int = 10
    ) -> None:
        """设置日志系统"""
        import logging.handlers

        # 创建日志目录
        log_path = Path(log_dir)
        log_path.mkdir(parents=True, exist_ok=True)

        # 设置日志格式
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

        # 设置根日志器
        root_logger = logging.getLogger()
        root_logger.setLevel(getattr(logging, log_level.upper()))

        # 清除现有处理器
        root_logger.handlers.clear()

        # 控制台处理器
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)

        # 文件处理器（带轮转）
        log_file = log_path / "runtime.log"
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=10*1024*1024,  # 10MB
            backupCount=max_files,
            encoding='utf-8'
        )
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)

        logger.info("日志系统初始化完成")

    @staticmethod
    def get_log_file(log_dir: Union[str, Path] = "logs") -> Path:
        """获取日志文件路径"""
        return Path(log_dir) / "runtime.log"

    @staticmethod
    def clear_old_logs(log_dir: Union[str, Path] = "logs", days: int = 7) -> None:
        """清理旧日志文件"""
        try:
            from datetime import datetime, timedelta
            log_path = Path(log_dir)
            cutoff_date = datetime.now() - timedelta(days=days)

            for log_file in log_path.glob("*.log*"):
                if log_file.stat().st_mtime < cutoff_date.timestamp():
                    log_file.unlink()
                    logger.debug(f"删除旧日志文件: {log_file}")
        except Exception as e:
            logger.warning(f"清理日志文件失败: {e}")

if __name__ == "__main__":
    # 测试工具函数
    print("=== 工具函数测试 ===")

    # 测试视频工具
    print("\n--- 视频工具测试 ---")
    print(f"是否为视频文件: {VideoUtils.is_video_file('test.mp4')}")
    print(f"时长格式化: {VideoUtils.format_duration(3665)}")

    # 测试文件工具
    print("\n--- 文件工具测试 ---")
    test_dir = FileUtils.ensure_directory("test_temp")
    print(f"创建测试目录: {test_dir}")

    # 测试文本工具
    print("\n--- 文本工具测试 ---")
    test_text = "这是一个测试句子。这是另一个句子！"
    print(f"清理文本: {TextUtils.clean_text(test_text)}")
    print(f"句子分割: {TextUtils.extract_sentences(test_text)}")
    print(f"字数统计: {TextUtils.count_words(test_text)}")

    # 测试系统工具
    print("\n--- 系统工具测试 ---")
    print(f"系统信息: {SystemUtils.get_system_info()}")
    print(f"内存信息: {SystemUtils.get_memory_info()}")