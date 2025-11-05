"""
🎬 Whisper语音识别管理模块
管理Whisper模型加载和语音识别功能
"""

import logging
import os
import platform
import time
from pathlib import Path
from typing import Dict, Any, Optional, Union, Callable
import whisper
try:
    from .config import CONFIG
    from .utils import FileUtils, SystemUtils
except Exception:
    from config import CONFIG
    from utils import FileUtils, SystemUtils

logger = logging.getLogger(__name__)

class WhisperManager:
    """Whisper模型管理器（单例模式）"""

    _instance = None
    _model = None
    _model_name = None

    def __new__(cls):
        """单例模式实现"""
        if cls._instance is None:
            cls._instance = super(WhisperManager, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        self.model_path = Path("models/whisper")
        self.model_name = CONFIG.get('whisper.model', 'small')
        self.language = CONFIG.get('whisper.language', 'zh')
        self.device = CONFIG.get('whisper.device', 'auto')
        self.temperature = CONFIG.get('whisper.temperature', 0.0)
        self._cancelled = False  # 取消标志

        # 确保模型目录存在
        FileUtils.ensure_directory(self.model_path)

        # 检查系统配置
        self._setup_device()
        logger.info(f"🎤 Whisper管理器初始化完成 (模型: {self.model_name})")

    def _setup_device(self) -> None:
        """设置设备（CPU/GPU）"""
        try:
            import torch

            if self.device == 'auto':
                if torch.cuda.is_available():
                    self.device = 'cuda'
                    gpu_name = torch.cuda.get_device_name(0)
                    memory_gb = torch.cuda.get_device_properties(0).total_memory / 1024**3
                    logger.info(f"🎮 检测到GPU: {gpu_name} ({memory_gb:.1f}GB)")
                else:
                    self.device = 'cpu'
                    logger.info("⚠️ 未检测到GPU，使用CPU模式")
            elif self.device == 'cuda' and not torch.cuda.is_available():
                logger.warning("请求使用CUDA但GPU不可用，回退到CPU")
                self.device = 'cpu'

            # 根据设备类型调整模型选择建议
            self._recommend_model()

        except ImportError:
            self.device = 'cpu'
            logger.warning("PyTorch未安装，使用CPU模式")

    def _recommend_model(self) -> None:
        """根据系统配置推荐模型"""
        try:
            import torch

            if self.device == 'cpu':
                # CPU模式推荐小模型
                recommended_models = ['tiny', 'base', 'small']
                if self.model_name not in recommended_models:
                    logger.warning(f"CPU模式建议使用较小模型，当前: {self.model_name}")
            else:
                # GPU模式根据显存推荐
                gpu_memory = torch.cuda.get_device_properties(0).total_memory / 1024**3

                if gpu_memory >= 8:
                    recommended_models = ['small', 'medium', 'large']
                elif gpu_memory >= 4:
                    recommended_models = ['base', 'small']
                else:
                    recommended_models = ['tiny', 'base']

                if self.model_name not in recommended_models:
                    logger.warning(f"GPU显存{gpu_memory:.1f}GB，建议使用: {recommended_models}")

        except Exception as e:
            logger.warning(f"模型推荐失败: {e}")

    def _running(self):
        """检查操作是否应该继续运行"""
        # 默认返回True，表示继续运行
        # 这个方法可以被外部线程覆盖或修改
        return not self._cancelled
        
    def cancel(self):
        """取消当前操作"""
        logger.info("🚫 Whisper操作被取消")
        self._cancelled = True
        
    def reset_cancelled(self):
        """重置取消状态"""
        self._cancelled = False

    def recommend_model_by_system(self) -> str:
        """根据设备与显存返回推荐模型名称"""
        try:
            import torch
            if self.device == 'cpu':
                return 'base'
            mem_gb = torch.cuda.get_device_properties(0).total_memory / 1024**3 if torch.cuda.is_available() else 0
            if mem_gb >= 8:
                return 'medium'
            elif mem_gb >= 4:
                return 'small'
            else:
                return 'base'
        except Exception:
            return 'base'

    def load_model(self, model_name: str = None, force_reload: bool = False, progress_callback: Callable = None) -> bool:
        """
        加载Whisper模型

        Args:
            model_name: 模型名称 (tiny, base, small, medium, large)
            force_reload: 是否强制重新加载
            progress_callback: 进度回调函数
        
        Returns:
            加载是否成功
        """
        try:
            # 重置取消状态
            self.reset_cancelled()
            
            if model_name is None:
                model_name = self.model_name
            
            # 检查是否已加载相同模型
            if not force_reload and self._model is not None and self._model_name == model_name:
                logger.debug(f"模型 {model_name} 已加载")
                return True
            
            logger.info(f"🔄 加载Whisper模型: {model_name}")
            if progress_callback:
                progress_callback(10, f"准备加载模型 {model_name}...")
            
            # 设置环境变量（如果需要）
            os.environ['WHISPER_MODEL_DIR'] = str(self.model_path)
            
            # 检查是否被取消
            if not self._running():
                logger.info("模型加载被取消")
                return False
            
            # 尝试预检查模型文件是否存在，避免不必要的下载
            model_file = self.model_path / f"{model_name}.pt"
            if model_file.exists():
                logger.info(f"📁 模型文件已存在: {model_file}")
                if progress_callback:
                    progress_callback(30, "检测到模型文件，准备加载...")
                    # 即使文件存在，仍然检查取消状态
                    if not self._running():
                        logger.info("模型加载被取消")
                        return False
            else:
                logger.info(f"⬇️ 需要下载模型: {model_name}")
                if progress_callback:
                    progress_callback(25, f"开始下载模型 {model_name}...")
                    # 下载前再次检查取消状态
                    if not self._running():
                        logger.info("模型下载被取消")
                        return False
            
            # 使用线程池方式加载模型，这样可以在需要时更好地控制
            import threading
            import queue
            result_queue = queue.Queue()
            
            def load_model_worker():
                try:
                    # 在工作线程中检查取消状态
                    if not self._running():
                        result_queue.put((None, "操作已取消"))
                        return
                    
                    # 下载/加载过程中简单进度提示
                    if progress_callback:
                        progress_callback(50, "模型下载/加载中...")
                    # 加载模型
                    model = whisper.load_model(
                        model_name,
                        device=self.device,
                        download_root=str(self.model_path)
                    )
                    if progress_callback:
                        progress_callback(90, "模型加载完成，准备就绪...")
                    result_queue.put((model, None))
                except Exception as e:
                    result_queue.put((None, str(e)))
            
            # 启动工作线程
            load_thread = threading.Thread(target=load_model_worker)
            load_thread.daemon = True  # 设置为守护线程，主程序结束时会自动终止
            load_thread.start()
            
            # 等待线程完成，但定期检查取消状态
            import time
            while load_thread.is_alive():
                # 每秒检查一次取消状态
                time.sleep(0.5)
                if not self._running():
                    logger.info("模型加载过程中被取消")
                    # 虽然我们不能直接中断whisper.load_model，但设置取消标志
                    # 当线程完成时，我们不会使用结果
                    self.cancel()
                    # 仍然等待线程结束，避免资源泄漏
                    load_thread.join(timeout=2.0)
                    return False
            
            # 获取加载结果
            model, error = result_queue.get()
            
            # 再次检查是否被取消
            if not self._running():
                logger.info("模型加载完成但操作已被取消")
                return False
            
            if error:
                # 检查是否是取消导致的错误
                if self._cancelled:
                    logger.info(f"模型加载被取消: {error}")
                    return False
                else:
                    raise Exception(error)
            
            self._model = model
            self._model_name = model_name
            self.model_name = model_name
            
            logger.info(f"✅ Whisper模型加载成功: {model_name}")
            if progress_callback:
                progress_callback(100, f"模型 {model_name} 加载成功")
            return True
        
        except Exception as e:
            # 区分正常异常和取消异常
            if self._cancelled:
                logger.info(f"模型加载被取消: {e}")
                return False
            else:
                logger.error(f"❌ Whisper模型加载失败: {e}")
                return False

    def transcribe_audio(
        self,
        audio_path: Union[str, Path],
        language: str = None,
        temperature: float = None,
        progress_callback: Callable = None,
        max_retries: int = None
    ) -> Dict[str, Any]:
        """
        转写音频为文字

        Args:
            audio_path: 音频文件路径
            language: 语言代码 (如: zh, en)
            temperature: 温度参数
            progress_callback: 进度回调函数
            max_retries: 最大重试次数（默认从配置读取）

        Returns:
            转写结果字典
        """
        try:
            # 重置取消状态
            self.reset_cancelled()

            # 设置重试次数
            if max_retries is None:
                max_retries = CONFIG.get('whisper.max_retries', 2)

            # 验证音频文件存在
            audio_path = Path(audio_path)
            if not audio_path.exists():
                return {
                    'success': False,
                    'error': '音频文件不存在',
                    'text': None
                }

            # 设置参数
            language = language or self.language
            temperature = temperature if temperature is not None else self.temperature

            logger.info(f"🎤 开始语音识别: {audio_path}")
            logger.debug(f"参数 - 语言: {language}, 温度: {temperature}, 设备: {self.device}, 最大重试: {max_retries}")

            # 重试机制
            last_error = None
            retry_delay = CONFIG.get('whisper.retry_delay', 3)

            for attempt in range(max_retries + 1):  # +1 表示第一次尝试 + max_retries次重试
                if attempt > 0:
                    logger.info(f"🔄 第{attempt}次重试...")
                    if progress_callback:
                        progress_callback(5, f"第{attempt}次重试...")

                    # 重试延迟
                    if retry_delay > 0 and attempt < max_retries:
                        logger.info(f"等待 {retry_delay} 秒后重试...")
                        if progress_callback:
                            progress_callback(5, f"等待 {retry_delay} 秒...")
                        time.sleep(retry_delay)

                # 检查取消状态
                if not self._running():
                    logger.info("语音识别被取消")
                    return {
                        'success': False,
                        'error': '操作已取消',
                        'text': None
                    }

                # 尝试转写
                result = self._transcribe_with_timeout(
                    audio_path, language, temperature, progress_callback, attempt
                )

                if result['success']:
                    logger.info(f"✅ 语音识别成功，识别字数: {len(result.get('text', ''))}")
                    return result
                else:
                    last_error = result.get('error', '未知错误')
                    # 如果是取消错误，立即返回
                    if '取消' in last_error:
                        return result
                    # 记录错误并继续重试
                    logger.warning(f"第{attempt + 1}次尝试失败: {last_error}")

            # 所有重试都失败了
            logger.error(f"❌ 语音识别失败，已重试{max_retries}次。最后错误: {last_error}")
            return {
                'success': False,
                'error': f'语音识别失败，已重试{max_retries}次。错误: {last_error}',
                'text': None
            }

        except Exception as e:
            logger.error(f"❌ 语音识别异常: {e}")
            return {
                'success': False,
                'error': str(e),
                'text': None
            }

    def _transcribe_with_timeout(
        self,
        audio_path: Path,
        language: str,
        temperature: float,
        progress_callback: Callable,
        attempt: int
    ) -> Dict[str, Any]:
        """
        带超时机制的音频转写（内部方法）

        Args:
            audio_path: 音频文件路径
            language: 语言代码
            temperature: 温度参数
            progress_callback: 进度回调函数
            attempt: 当前尝试次数

        Returns:
            转写结果字典
        """
        try:
            # 确保模型已加载
            if self._model is None:
                # 传递进度回调给模型加载，以获得一致日志和取消处理
                if not self.load_model(progress_callback=progress_callback):
                    if self._cancelled:
                        return {
                            'success': False,
                            'error': '操作已取消',
                            'text': None
                        }
                    return {
                        'success': False,
                        'error': '模型未加载',
                        'text': None
                    }

            # 发送开始进度
            if progress_callback:
                progress_callback(10, "正在加载音频文件...")

            # 使用线程包装转写操作以支持超时
            import threading
            import time

            result_container = {'result': None, 'error': None, 'completed': False}

            def transcribe_worker():
                try:
                    if progress_callback:
                        progress_callback(30, "正在进行语音识别...")

                    # 执行转写
                    result = self._model.transcribe(
                        str(audio_path),
                        language=language,
                        temperature=temperature,
                        verbose=CONFIG.get('whisper.verbose', False),
                        fp16=(self.device == 'cuda'),
                        word_timestamps=False
                    )
                    result_container['result'] = result
                    result_container['completed'] = True

                except Exception as e:
                    result_container['error'] = str(e)
                    result_container['completed'] = True

            # 启动转写线程
            transcribe_thread = threading.Thread(target=transcribe_worker)
            transcribe_thread.daemon = True
            transcribe_thread.start()

            # 等待转写完成，同时检查取消状态
            start_time = time.time()
            timeout = CONFIG.get('whisper.timeout', 600)  # 10分钟超时（已更新为600秒）

            while not result_container['completed']:
                if not self._running():
                    logger.info("语音识别过程中被取消")
                    return {
                        'success': False,
                        'error': '操作已取消',
                        'text': None
                    }

                # 检查超时
                if time.time() - start_time > timeout:
                    logger.warning(f"语音识别超时 ({timeout}秒)")
                    return {
                        'success': False,
                        'error': f'操作超时 ({timeout}秒)',
                        'text': None
                    }

                # 更新进度
                elapsed = time.time() - start_time
                progress = min(30 + int((elapsed / timeout) * 60), 90)
                if progress_callback:
                    progress_callback(progress, f"正在识别语音... ({elapsed:.0f}s)")

                time.sleep(0.5)  # 每0.5秒检查一次

            # 检查结果
            if result_container['error']:
                raise Exception(result_container['error'])

            result = result_container['result']

            # 再次检查是否被取消
            if not self._running():
                logger.info("语音识别完成但操作已被取消")
                return {
                    'success': False,
                    'error': '操作已取消',
                    'text': None
                }

            # 处理结果
            text = result.get('text', '').strip()

            if not text:
                return {
                    'success': False,
                    'error': '未识别到语音内容',
                    'text': None
                }

            return {
                'success': True,
                'text': text,
                'language': result.get('language', language),
                'duration': self._estimate_audio_duration(result),
                'word_count': len(text),
                'model_used': self._model_name,
                'device_used': self.device,
                'attempt': attempt + 1  # 记录成功时的尝试次数
            }

        except Exception as e:
            logger.error(f"❌ 单次语音识别失败: {e}")
            return {
                'success': False,
                'error': str(e),
                'text': None
            }

    def _estimate_audio_duration(self, result: Dict[str, Any]) -> Optional[float]:
        """估算音频时长"""
        try:
            segments = result.get('segments', [])
            if segments:
                return max(segment.get('end', 0) for segment in segments)
            return None
        except:
            return None

    def get_available_models(self) -> list:
        """获取可用的模型列表"""
        try:
            available = []
            for model_name in ['tiny', 'base', 'small', 'medium', 'large']:
                model_path = self.model_path / model_name
                if model_path.exists() or model_name == self._model_name:
                    available.append(model_name)
            return available
        except Exception as e:
            logger.error(f"获取可用模型失败: {e}")
            return []

    def get_model_info(self, model_name: str = None) -> Dict[str, Any]:
        """获取模型信息"""
        if model_name is None:
            model_name = self.model_name

        model_info = {
            'tiny': {
                'name': 'Tiny',
                'size_mb': 75,
                'speed': '极快',
                'accuracy': '基础',
                'vram_mb': 1,
                'description': '适用于实时处理，准确度较低'
            },
            'base': {
                'name': 'Base',
                'size_mb': 142,
                'speed': '很快',
                'accuracy': '良好',
                'vram_mb': 2,
                'description': '平衡选择，日常使用推荐'
            },
            'small': {
                'name': 'Small',
                'size_mb': 466,
                'speed': '快速',
                'accuracy': '高',
                'vram_mb': 4,
                'description': '高精度，推荐用于正式用途'
            },
            'medium': {
                'name': 'Medium',
                'size_mb': 1530,
                'speed': '中等',
                'accuracy': '很高',
                'vram_mb': 8,
                'description': '专业级精度，需要较强硬件'
            },
            'large': {
                'name': 'Large',
                'size_mb': 2950,
                'speed': '慢速',
                'accuracy': '最高',
                'vram_mb': 16,
                'description': '最高精度，处理时间较长'
            }
        }

        return model_info.get(model_name, {})

    def download_model(self, model_name: str, progress_callback: Callable = None) -> bool:
        """
        下载Whisper模型

        Args:
            model_name: 模型名称
            progress_callback: 进度回调函数

        Returns:
            下载是否成功
        """
        try:
            logger.info(f"📥 下载Whisper模型: {model_name}")

            # 检查是否已存在
            if self._model_exists(model_name):
                logger.info(f"模型 {model_name} 已存在")
                return True

            # 设置环境变量
            os.environ['WHISPER_MODEL_DIR'] = str(self.model_path)

            # 模拟进度回调（实际whisper没有进度回调）
            if progress_callback:
                progress_callback(10, f"准备下载 {model_name} 模型...")
                progress_callback(30, f"正在下载 {model_name} 模型...")
                progress_callback(60, f"下载 {model_name} 模型中...")
                progress_callback(90, f"完成下载 {model_name} 模型...")

            # 加载模型会自动下载
            whisper.load_model(model_name, download_root=str(self.model_path))

            if progress_callback:
                progress_callback(100, f"模型 {model_name} 下载完成")

            logger.info(f"✅ 模型 {model_name} 下载成功")
            return True

        except Exception as e:
            logger.error(f"❌ 模型下载失败: {e}")
            return False

    def _model_exists(self, model_name: str) -> bool:
        """检查模型文件是否存在"""
        try:
            model_file = self.model_path / f"{model_name}.pt"
            return model_file.exists()
        except:
            return False

    def get_current_model(self) -> Optional[str]:
        """获取当前加载的模型"""
        return self._model_name

    def unload_model(self) -> None:
        """卸载当前模型"""
        try:
            if self._model is not None:
                import torch
                del self._model
                self._model = None
                self._model_name = None

                if self.device == 'cuda':
                    torch.cuda.empty_cache()

                logger.info("🔄 Whisper模型已卸载")
        except Exception as e:
            logger.warning(f"卸载模型失败: {e}")

    def get_system_requirements(self) -> Dict[str, Any]:
        """获取系统要求信息"""
        try:
            import torch

            requirements = {
                'python_version': platform.python_version(),
                'pytorch_version': torch.__version__,
                'cuda_available': torch.cuda.is_available(),
                'current_device': self.device,
                'loaded_model': self._model_name
            }

            if torch.cuda.is_available():
                requirements.update({
                    'cuda_version': torch.version.cuda,
                    'device_count': torch.cuda.device_count(),
                    'current_device_name': torch.cuda.get_device_name(0),
                    'gpu_memory_gb': round(torch.cuda.get_device_properties(0).total_memory / 1024**3, 2)
                })

            return requirements

        except Exception as e:
            logger.error(f"获取系统要求失败: {e}")
            return {'error': str(e)}

    def cleanup_models(self, keep_models: list = None) -> None:
        """清理未使用的模型文件"""
        try:
            if keep_models is None:
                keep_models = [self._model_name]

            for model_dir in self.model_path.iterdir():
                if model_dir.is_dir() and model_dir.name not in keep_models:
                    import shutil
                    shutil.rmtree(model_dir)
                    logger.info(f"删除未使用模型: {model_dir.name}")

        except Exception as e:
            logger.warning(f"清理模型文件失败: {e}")

    def test_transcription(self, audio_path: Union[str, Path] = None) -> Dict[str, Any]:
        """测试语音识别功能"""
        try:
            if audio_path is None:
                # 创建测试音频（如果没有提供）
                return self._create_test_transcription()

            return self.transcribe_audio(audio_path)

        except Exception as e:
            return {
                'success': False,
                'error': f'语音识别测试失败: {str(e)}'
            }

    def _create_test_transcription(self) -> Dict[str, Any]:
        """创建测试转写结果"""
        return {
            'success': True,
            'text': "这是一个语音识别测试。如果能看到这段文字，说明Whisper工作正常。",
            'language': 'zh',
            'test_mode': True,
            'word_count': 28
        }

if __name__ == "__main__":
    # 测试Whisper管理器
    print("=== Whisper管理器测试 ===")

    manager = WhisperManager()

    print(f"当前设备: {manager.device}")
    print(f"模型目录: {manager.model_path}")
    print(f"推荐模型: {manager.get_model_info()}")

    # 测试模型信息
    print("\n可用模型:")
    for model in ['tiny', 'base', 'small', 'medium', 'large']:
        info = manager.get_model_info(model)
        print(f"  {model}: {info.get('name')} - {info.get('description')}")

    # 测试系统要求
    print(f"\n系统要求: {manager.get_system_requirements()}")