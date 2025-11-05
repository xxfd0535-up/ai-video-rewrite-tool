"""
🎬 音频提取模块
从视频文件中提取音频并转换为最佳格式
"""

import logging
import subprocess
import os
from pathlib import Path
from typing import Dict, Any, Optional, Union
try:
    from .config import CONFIG
    from .utils import FileUtils, SystemUtils
except Exception:
    from config import CONFIG
    from utils import FileUtils, SystemUtils

logger = logging.getLogger(__name__)

class AudioExtractor:
    """音频提取器"""

    def __init__(self):
        self.temp_dir = Path(CONFIG.get('audio.temp_dir', 'temp'))
        self.sample_rate = CONFIG.get('audio.sample_rate', 16000)
        self.channels = CONFIG.get('audio.channels', 1)
        self.audio_format = CONFIG.get('audio.format', 'wav')
        self.quality = CONFIG.get('audio.quality', 'high')

        # 确保临时目录存在
        FileUtils.ensure_directory(self.temp_dir)
        logger.info("🎤 音频提取器初始化完成")

    def extract_audio(
        self,
        video_path: Union[str, Path],
        output_path: Optional[Union[str, Path]] = None,
        progress_callback = None
    ) -> Dict[str, Any]:
        """
        从视频中提取音频

        Args:
            video_path: 视频文件路径
            output_path: 输出音频文件路径（可选）
            progress_callback: 进度回调函数

        Returns:
            提取结果字典
        """
        try:
            video_path = Path(video_path)

            if not video_path.exists():
                return {
                    'success': False,
                    'error': '视频文件不存在',
                    'audio_path': None
                }

            # 生成输出路径
            if output_path is None:
                # 清理文件名，移除特殊字符，限制长度
                base_name = video_path.stem
                # 移除或替换常见特殊字符
                clean_name = base_name.replace('！', '').replace('？', '').replace('……', '').replace('——', '').replace('---', '')
                # 限制文件名长度，避免路径过长
                if len(clean_name) > 30:
                    clean_name = clean_name[:30]
                output_path = self.temp_dir / f"{clean_name}_extracted.{self.audio_format}"
            else:
                output_path = Path(output_path)

            # 确保输出目录存在
            FileUtils.ensure_directory(output_path.parent)

            logger.info(f"开始提取音频: {video_path} -> {output_path}")

            # 使用FFmpeg提取音频
            result = self._extract_with_ffmpeg(video_path, output_path, progress_callback)

            if result['success']:
                logger.info(f"音频提取成功: {output_path}")
                return result
            else:
                logger.error(f"音频提取失败: {result.get('error')}")
                return result

        except Exception as e:
            logger.error(f"音频提取异常: {e}")
            return {
                'success': False,
                'error': str(e),
                'audio_path': None
            }

    def _extract_with_ffmpeg(
        self,
        video_path: Path,
        output_path: Path,
        progress_callback = None
    ) -> Dict[str, Any]:
        """使用FFmpeg提取音频"""
        try:
            # 构建FFmpeg命令
            cmd = [
                'ffmpeg',
                '-i', str(video_path),           # 输入文件
                '-vn',                         # 禁用视频
                '-acodec', 'pcm_s16le',       # 音频编码器
                '-ar', str(self.sample_rate),   # 采样率
                '-ac', str(self.channels),      # 声道数
                '-y'                           # 覆盖输出文件
            ]

            # 根据质量设置添加参数
            if self.quality == 'high':
                cmd.extend(['-q:a', '0'])      # 最高质量
            elif self.quality == 'medium':
                cmd.extend(['-q:a', '2'])      # 中等质量
            else:
                cmd.extend(['-q:a', '4'])      # 低质量

            cmd.append(str(output_path))

            logger.debug(f"FFmpeg命令: {' '.join(cmd)}")

            # 执行命令
            if progress_callback:
                result = self._run_ffmpeg_with_progress(cmd, progress_callback)
                # 若进度模式失败，自动回退到简化运行，提升鲁棒性
                if not result.get('success'):
                    logger.warning("FFmpeg 进度模式失败，回退到简化运行模式")
                    return self._run_ffmpeg_simple(cmd)
                return result
            else:
                return self._run_ffmpeg_simple(cmd)

        except Exception as e:
            return {
                'success': False,
                'error': f'FFmpeg执行失败: {str(e)}',
                'audio_path': None
            }

    def _run_ffmpeg_simple(self, cmd: list) -> Dict[str, Any]:
        """简单运行FFmpeg"""
        try:
            # 使用环境变量设置编码
            import os
            env = os.environ.copy()
            env['PYTHONIOENCODING'] = 'utf-8'

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,  # 5分钟超时
                env=env,
                encoding='utf-8',
                errors='ignore'
            )

            if result.returncode == 0:
                return {
                    'success': True,
                    'audio_path': cmd[-1],  # 输出文件路径
                    'output': result.stdout,
                    'duration': self._get_audio_duration(cmd[-1])
                }
            else:
                # 处理错误输出中的编码问题
                error_msg = result.stderr
                try:
                    error_msg = result.stderr.encode('utf-8', errors='ignore').decode('utf-8')
                except:
                    error_msg = "FFmpeg execution failed"

                return {
                    'success': False,
                    'error': f'FFmpeg error: {error_msg}',
                    'audio_path': None
                }

        except subprocess.TimeoutExpired:
            return {
                'success': False,
                'error': 'FFmpeg execution timeout',
                'audio_path': None
            }
        except Exception as e:
            return {
                'success': False,
                'error': f'FFmpeg exception: {str(e)}',
                'audio_path': None
            }

    def _run_ffmpeg_with_progress(self, cmd: list, progress_callback) -> Dict[str, Any]:
        """运行FFmpeg并监控进度（编码安全）"""
        try:
            # 以二进制读取并统一使用 UTF-8 忽略错误，避免 GBK/GB2312 解码异常
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=False,
                bufsize=1024
            )

            duration = None
            current_time = 0

            while True:
                line_bytes = process.stdout.readline()
                if not line_bytes:
                    break

                # 统一按 UTF-8 解码，忽略不可识别字节，彻底避免 UnicodeDecodeError
                try:
                    line = line_bytes.decode('utf-8', errors='ignore')
                except Exception:
                    # 极端情况下退回 latin1，也不会抛异常
                    line = line_bytes.decode('latin1', errors='ignore')

                if 'Duration' in line:
                    duration = self._parse_duration(line)
                    if duration and progress_callback:
                        progress_callback(0, f"Audio extracting... Total duration: {self._format_time(duration)}")
                elif 'time=' in line:
                    current_time = self._parse_time(line)
                    if duration and progress_callback and current_time is not None:
                        try:
                            progress = max(0, min(100, int((current_time / duration) * 100)))
                            progress_callback(progress, f"Audio extracting... {progress}%")
                        except Exception:
                            # 防御性保护，任何计算异常都不阻断提取流程
                            pass

            return_code = process.wait()

            if return_code == 0:
                return {
                    'success': True,
                    'audio_path': cmd[-1],
                    'duration': self._get_audio_duration(cmd[-1])
                }
            else:
                return {
                    'success': False,
                    'error': 'FFmpeg execution failed',
                    'audio_path': None
                }

        except Exception as e:
            return {
                'success': False,
                'error': f'FFmpeg progress monitoring failed: {str(e)}',
                'audio_path': None
            }

    def _parse_duration(self, line: str) -> Optional[float]:
        """解析FFmpeg输出中的时长信息"""
        try:
            import re
            pattern = r'Duration: (\d{2}):(\d{2}):(\d{2}\.\d{2})'
            match = re.search(pattern, line)
            if match:
                hours, minutes, seconds = match.groups()
                return int(hours) * 3600 + int(minutes) * 60 + float(seconds)
            return None
        except:
            return None

    def _parse_time(self, line: str) -> Optional[float]:
        """解析FFmpeg输出中的时间信息"""
        try:
            import re
            pattern = r'time=(\d{2}):(\d{2}):(\d{2}\.\d{2})'
            match = re.search(pattern, line)
            if match:
                hours, minutes, seconds = match.groups()
                return int(hours) * 3600 + int(minutes) * 60 + float(seconds)
            return None
        except:
            return None

    def _format_time(self, seconds: float) -> str:
        """格式化时间显示"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)

        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{secs:02d}"
        else:
            return f"{minutes:02d}:{secs:02d}"

    def _get_audio_duration(self, audio_path: Union[str, Path]) -> Optional[float]:
        """获取音频文件时长"""
        try:
            import soundfile as sf
            with sf.SoundFile(str(audio_path)) as audio_file:
                return len(audio_file) / audio_file.samplerate
        except ImportError:
            logger.warning("soundfile未安装，无法获取音频时长")
            return None
        except Exception as e:
            logger.warning(f"获取音频时长失败: {e}")
            return None

    def validate_audio_file(self, audio_path: Union[str, Path]) -> Dict[str, Any]:
        """验证音频文件"""
        try:
            audio_path = Path(audio_path)

            if not audio_path.exists():
                return {
                    'valid': False,
                    'error': '音频文件不存在'
                }

            # 检查文件大小
            file_size = audio_path.stat().st_size
            if file_size == 0:
                return {
                    'valid': False,
                    'error': '音频文件为空'
                }

            # 尝试读取音频信息
            try:
                import soundfile as sf
                with sf.SoundFile(str(audio_path)) as audio_file:
                    return {
                        'valid': True,
                        'duration': len(audio_file) / audio_file.samplerate,
                        'samplerate': audio_file.samplerate,
                        'channels': audio_file.channels,
                        'format': audio_file.format,
                        'file_size': file_size
                    }
            except ImportError:
                # 如果没有soundfile，只做基本检查
                return {
                    'valid': True,
                    'file_size': file_size,
                    'warning': '无法获取详细音频信息（soundfile未安装）'
                }

        except Exception as e:
            return {
                'valid': False,
                'error': f'音频验证失败: {str(e)}'
            }

    def cleanup_temp_files(self, audio_path: Union[str, Path] = None) -> None:
        """清理临时音频文件"""
        try:
            if audio_path:
                FileUtils.safe_delete(audio_path)
            else:
                # 清理所有临时音频文件
                pattern = f"{self.temp_dir}/*_extracted.{self.audio_format}"
                import glob
                for file_path in glob.glob(pattern):
                    FileUtils.safe_delete(file_path)
        except Exception as e:
            logger.warning(f"清理临时文件失败: {e}")

    def get_audio_info(self, audio_path: Union[str, Path]) -> Dict[str, Any]:
        """获取音频文件信息"""
        try:
            result = self.validate_audio_file(audio_path)
            if not result['valid']:
                return result

            # 添加额外信息
            result['file_size_mb'] = round(result['file_size'] / (1024 * 1024), 2)
            result['format_time'] = self._format_time(result.get('duration', 0))

            return result

        except Exception as e:
            return {
                'error': f'获取音频信息失败: {str(e)}'
            }

    def convert_audio_format(
        self,
        input_path: Union[str, Path],
        output_path: Union[str, Path],
        target_format: str = 'wav',
        progress_callback = None
    ) -> Dict[str, Any]:
        """转换音频格式"""
        try:
            input_path = Path(input_path)
            output_path = Path(output_path)

            if not input_path.exists():
                return {
                    'success': False,
                    'error': '输入音频文件不存在'
                }

            logger.info(f"转换音频格式: {input_path} -> {output_path}")

            # 构建FFmpeg命令
            cmd = [
                'ffmpeg',
                '-i', str(input_path),
                '-acodec', 'pcm_s16le',
                '-ar', str(self.sample_rate),
                '-ac', str(self.channels),
                '-y',
                str(output_path)
            ]

            # 执行转换
            if progress_callback:
                progress_callback(50, "格式转换中...")
                result = self._run_ffmpeg_simple(cmd)
                progress_callback(100, "格式转换完成")
            else:
                result = self._run_ffmpeg_simple(cmd)

            return result

        except Exception as e:
            return {
                'success': False,
                'error': f'音频格式转换失败: {str(e)}'
            }

if __name__ == "__main__":
    # 测试音频提取器
    print("=== 音频提取器测试 ===")

    extractor = AudioExtractor()

    # 测试配置
    print(f"临时目录: {extractor.temp_dir}")
    print(f"采样率: {extractor.sample_rate}")
    print(f"声道数: {extractor.channels}")
    print(f"音频格式: {extractor.audio_format}")

    # 检查FFmpeg
    if SystemUtils.check_command_exists('ffmpeg'):
        print("✅ FFmpeg 已安装")
    else:
        print("❌ FFmpeg 未安装")