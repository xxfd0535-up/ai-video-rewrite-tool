"""
🎬 主应用程序模块
PyQt5图形用户界面
"""

import sys
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime
import json

try:
    from PyQt5.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QLabel, QPushButton, QTextEdit, QProgressBar, QFileDialog,
        QMessageBox, QGroupBox, QSplitter, QFrame, QStatusBar,
        QMenuBar, QMenu, QAction, QDialog, QFormLayout, QLineEdit,
        QComboBox, QSpinBox, QDoubleSpinBox, QCheckBox, QTabWidget,
        QTextBrowser, QToolBar, QStatusBar, QSystemTrayIcon,
        QStyle
    )
    from PyQt5.QtCore import Qt, QThread, pyqtSignal, QSize, QPoint, QTimer
    from PyQt5.QtGui import QFont, QIcon, QTextCursor, QDragEnterEvent, QDropEvent
    PYQT_AVAILABLE = True
except ImportError:
    PYQT_AVAILABLE = False
    logging.warning("PyQt5 未安装，无法启动图形界面")

from .config import CONFIG
from .utils import VideoUtils, TextUtils, FileUtils, LogUtils
from .audio_extractor import AudioExtractor
from .whisper_manager import WhisperManager
from .ollama_client import OllamaClient

logger = logging.getLogger(__name__)

class WorkerThread(QThread):
    """后台工作线程"""

    progress_updated = pyqtSignal(int, str)
    status_updated = pyqtSignal(str)
    result_ready = pyqtSignal(dict)
    error_occurred = pyqtSignal(str)

    def __init__(self, operation, **kwargs):
        super().__init__()
        self.operation = operation
        self.kwargs = kwargs
        self._running = True
        self._cancel_event = False  # 额外的取消标志

    def run(self):
        try:
            # 设置运行标志为True
            self._running = True
            self._cancel_event = False
            
            logger.info(f"开始执行线程操作: {self.operation}")
            
            if not self._running or self._cancel_event:
                logger.warning("线程被立即取消")
                return
                
            if self.operation == 'extract_audio':
                self._extract_audio()
            elif self.operation == 'transcribe':
                self._transcribe_audio()
            elif self.operation == 'rewrite_text':
                self._rewrite_text()
            else:
                self.error_occurred.emit(f"未知操作: {self.operation}")
                
        except Exception as e:
            logger.error(f"线程运行出错: {str(e)}")
            if self._running and not self._cancel_event:  # 只在非取消情况下发送错误
                self.error_occurred.emit(f"操作失败: {str(e)}")
        finally:
            logger.info(f"线程操作{self.operation}已结束")
            # 确保重置标志
            self._running = False
            self._cancel_event = True

    def _extract_audio(self):
        try:
            # 检查是否已取消
            if not self._running or self._cancel_event:
                logger.info("音频提取操作已取消")
                return
                
            extractor = AudioExtractor()

            def progress_callback(progress, message):
                # 如果线程已取消，不再发送更新
                if not self._running or self._cancel_event:
                    raise Exception("操作已取消")
                self.progress_updated.emit(progress, message)

            # 发送初始进度
            if not self._running or self._cancel_event:
                return
                
            self.progress_updated.emit(10, "开始提取音频...")

            # 在调用外部函数前再次检查
            if not self._running or self._cancel_event:
                return
                
            result = extractor.extract_audio(
                self.kwargs['video_path'],
                progress_callback=progress_callback
            )

            if self._running and not self._cancel_event:
                if result['success']:
                    self.progress_updated.emit(100, "音频提取完成")
                    self.result_ready.emit({
                        'type': 'audio_extracted',
                        'data': result
                    })
                else:
                    self.error_occurred.emit(result.get('error', '音频提取失败'))

        except Exception as e:
            if self._running and not self._cancel_event:  # 只在非取消情况下报告错误
                self.error_occurred.emit(f"音频提取异常: {str(e)}")
            else:
                logger.info(f"音频提取被取消: {str(e)}")

    def _transcribe_audio(self):
        try:
            # 检查是否已取消
            if not self._running or self._cancel_event:
                logger.info("语音识别操作已取消")
                return
                
            whisper = WhisperManager()
            
            # 注册取消方法
            if hasattr(whisper, 'cancel'):
                # 保存原始的_running方法引用（如果有）
                original_running = getattr(whisper, '_running', None)
                
                # 定义新的_running方法，结合两个取消标志
                def is_running():
                    # 同时检查线程的取消标志和WhisperManager的取消标志
                    return not (self._cancel_event or not self._running)
                
                # 设置新的_running方法
                whisper._running = is_running
            
            # 自定义进度回调，支持取消
            def progress_callback(progress, message):
                # 如果线程已取消，引发异常以中断处理
                if not self._running or self._cancel_event:
                    # 调用WhisperManager的取消方法
                    if hasattr(whisper, 'cancel'):
                        whisper.cancel()
                    raise Exception("操作已取消")
                self.progress_updated.emit(progress, message)

            # 发送初始进度
            if not self._running or self._cancel_event:
                # 确保取消Whisper操作
                if hasattr(whisper, 'cancel'):
                    whisper.cancel()
                return
                
            self.progress_updated.emit(10, "开始语音识别...")

            # 在调用外部函数前再次检查
            if not self._running or self._cancel_event:
                # 确保取消Whisper操作
                if hasattr(whisper, 'cancel'):
                    whisper.cancel()
                return
            
            # 记录开始时间，用于性能监控
            import time
            start_time = time.time()
            
            try:
                result = whisper.transcribe_audio(
                    self.kwargs['audio_path'],
                    progress_callback=progress_callback
                )
            except Exception as e:
                # 捕获取消异常并适当处理
                if "操作已取消" in str(e) or self._cancel_event or not self._running:
                    logger.info(f"语音识别被取消: {str(e)}")
                    # 确保取消Whisper操作
                    if hasattr(whisper, 'cancel'):
                        whisper.cancel()
                    return
                raise

            # 检查操作是否在过程中被取消
            if not self._running or self._cancel_event:
                logger.info("语音识别完成但操作已被取消")
                # 确保取消Whisper操作
                if hasattr(whisper, 'cancel'):
                    whisper.cancel()
                return
                
            # 计算耗时
            elapsed_time = time.time() - start_time
            logger.info(f"语音识别完成，耗时: {elapsed_time:.2f}秒")

            # 处理结果
            if result['success']:
                self.progress_updated.emit(100, "语音识别完成")
                self.result_ready.emit({
                    'type': 'transcription_completed',
                    'data': result
                })
            else:
                # 检查错误是否是取消导致的
                if "取消" in str(result.get('error', '')):
                    logger.info("语音识别因取消而失败")
                else:
                    self.error_occurred.emit(result.get('error', '语音识别失败'))

        except Exception as e:
            # 确保在异常情况下也取消Whisper操作
            try:
                whisper = WhisperManager()
                if hasattr(whisper, 'cancel'):
                    whisper.cancel()
            except:
                pass
                
            # 区分取消异常和其他异常
            if "取消" in str(e) or self._cancel_event or not self._running:
                logger.info(f"语音识别被取消: {str(e)}")
            else:
                logger.error(f"语音识别异常: {str(e)}")
                if self._running and not self._cancel_event:  # 只在非取消情况下报告错误
                    self.error_occurred.emit(f"语音识别异常: {str(e)}")

    def _rewrite_text(self):
        try:
            # 检查是否已取消
            if not self._running or self._cancel_event:
                logger.info("AI改写操作已取消")
                return
                
            ollama = OllamaClient()

            def progress_callback(progress, message):
                # 如果线程已取消，不再发送更新
                if not self._running or self._cancel_event:
                    raise Exception("操作已取消")
                self.progress_updated.emit(progress, message)

            # 发送初始进度
            if not self._running or self._cancel_event:
                return
                
            self.progress_updated.emit(10, "开始AI改写...")

            # 在调用外部函数前再次检查
            if not self._running or self._cancel_event:
                return
                
            result = ollama.rewrite_text(
                self.kwargs['original_text'],
                progress_callback=progress_callback
            )

            if self._running and not self._cancel_event:
                if result['success']:
                    self.progress_updated.emit(100, "AI改写完成")
                    self.result_ready.emit({
                        'type': 'rewrite_completed',
                        'data': result
                    })
                else:
                    self.error_occurred.emit(result.get('error', 'AI改写失败'))

        except Exception as e:
            if self._running and not self._cancel_event:  # 只在非取消情况下报告错误
                self.error_occurred.emit(f"AI改写异常: {str(e)}")
            else:
                logger.info(f"AI改写被取消: {str(e)}")

    def stop(self):
        """安全停止线程"""
        try:
            # 设置两个标志，确保线程能够感知到停止信号
            self._running = False
            self._cancel_event = True
            
            # 如果线程正在运行，进行停止处理
            if self.isRunning():
                logger.info(f"正在停止线程: {self.operation}")
                
                # 尝试通过quit()方法正常退出
                self.quit()
                
                # 协作式等待更长时间，避免使用terminate导致崩溃
                total_wait_ms = 30000  # 最长等待30秒
                step_ms = 1000
                waited = 0
                while self.isRunning() and waited < total_wait_ms:
                    if self.wait(step_ms):
                        break
                    waited += step_ms
                if self.isRunning():
                    # 不再强制终止，记录日志并让后台尽量自行结束
                    logger.warning("线程未能在超时时间内退出，将继续以协作式方式等待后台自行结束")
        except Exception as e:
            logger.warning(f"停止线程时出错: {e}")
            # 不进行强制终止，避免Qt/FFmpeg/Whisper底层崩溃
            try:
                if self.isRunning():
                    # 再次请求退出并等待短时间
                    self.quit()
                    self.wait(2000)
            except Exception:
                pass
            pass

class MainWindow(QMainWindow):
    """主窗口"""

    def __init__(self):
        super().__init__()

        # 初始化组件
        self.audio_extractor = AudioExtractor()
        self.whisper_manager = WhisperManager()
        self.ollama_client = OllamaClient()

        # 状态变量
        self.current_video_path = None
        self.current_audio_path = None
        self.original_text = ""
        self.rewritten_text = ""
        self.current_worker = None

        # 设置UI
        self.init_ui()
        self.setup_connections()

        logger.info("🎬 主窗口初始化完成")

    def init_ui(self):
        """初始化用户界面"""
        # 窗口设置
        self.setWindowTitle(CONFIG.get('app.window_title', '视频文案AI爆款改写工具'))
        self.setGeometry(100, 100,
                     CONFIG.get('app.window_size.width', 1200),
                     CONFIG.get('app.window_size.height', 800))

        # 中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # 主布局
        main_layout = QVBoxLayout(central_widget)

        # 工具栏
        self.create_toolbar()

        # 文件选择区域
        file_group = self.create_file_selection_group()
        main_layout.addWidget(file_group)

        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        main_layout.addWidget(self.progress_bar)

        # 状态标签
        self.status_label = QLabel("就绪")
        main_layout.addWidget(self.status_label)

        # 文本显示区域
        text_splitter = QSplitter(Qt.Horizontal)

        # 原文显示
        original_group = QGroupBox("原始文案")
        original_layout = QVBoxLayout()

        self.original_text_edit = QTextEdit()
        self.original_text_edit.setReadOnly(True)
        self.original_text_edit.setPlaceholderText("视频文案将显示在这里...")
        original_layout.addWidget(self.original_text_edit)
        original_group.setLayout(original_layout)

        # 改写文案显示
        rewritten_group = QGroupBox("AI改写文案")
        rewritten_layout = QVBoxLayout()

        self.rewritten_text_edit = QTextEdit()
        self.rewritten_text_edit.setReadOnly(True)
        self.rewritten_text_edit.setPlaceholderText("AI改写的文案将显示在这里...")
        rewritten_layout.addWidget(self.rewritten_text_edit)
        rewritten_group.setLayout(rewritten_layout)

        text_splitter.addWidget(original_group)
        text_splitter.addWidget(rewritten_group)
        text_splitter.setSizes([600, 600])

        main_layout.addWidget(text_splitter)

        # 操作按钮区域
        button_layout = QHBoxLayout()

        self.copy_button = QPushButton("📋 复制改写文案")
        self.copy_button.setEnabled(False)

        self.save_button = QPushButton("💾 保存结果")
        self.save_button.setEnabled(False)

        self.clear_button = QPushButton("🗑️ 清空")

        button_layout.addWidget(self.copy_button)
        button_layout.addWidget(self.save_button)
        button_layout.addWidget(self.clear_button)

        main_layout.addLayout(button_layout)

        # 状态栏
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        # 设置拖放
        self.setAcceptDrops(True)

        # 设置字体
        font = QFont(CONFIG.get('ui.font_family', 'Microsoft YaHei'))
        font.setPointSize(CONFIG.get('ui.font_size', 10))
        self.setFont(font)

        # 启用拖放
        if CONFIG.get('ui.drag_drop_enabled', True):
            self.setAcceptDrops(True)
            
        # 初始化控件状态
        self.set_controls_enabled(True)

    def create_toolbar(self):
        """创建工具栏"""
        toolbar = self.addToolBar("主工具栏")

        # 选择文件
        select_action = QAction("📁 选择视频文件", self)
        select_action.triggered.connect(self.select_video_file)
        toolbar.addAction(select_action)

        toolbar.addSeparator()

        # 处理视频
        process_action = QAction("🎬 处理视频", self)
        process_action.triggered.connect(self.process_video)
        toolbar.addAction(process_action)

        toolbar.addSeparator()

        # 设置
        settings_action = QAction("⚙️ 设置", self)
        settings_action.triggered.connect(self.show_settings)
        toolbar.addAction(settings_action)

        toolbar.addSeparator()

        # 关于
        about_action = QAction("❓ 关于", self)
        about_action.triggered.connect(self.show_about)
        toolbar.addAction(about_action)

    def create_file_selection_group(self):
        """创建文件选择组"""
        group = QGroupBox("视频文件")
        layout = QVBoxLayout()

        # 文件路径显示
        path_layout = QHBoxLayout()

        self.path_label = QLabel("未选择文件")
        self.path_label.setWordWrap(True)
        path_layout.addWidget(self.path_label)

        # 选择按钮
        self.select_button = QPushButton("📁 选择视频文件")
        self.select_button.clicked.connect(self.select_video_file)
        path_layout.addWidget(self.select_button)

        layout.addLayout(path_layout)

        # 文件信息显示
        self.file_info_label = QLabel("")
        self.file_info_label.setWordWrap(True)
        layout.addWidget(self.file_info_label)

        # 处理按钮区域
        button_layout = QHBoxLayout()
        
        self.process_button = QPushButton("🎬 开始处理")
        self.process_button.setEnabled(False)
        self.process_button.clicked.connect(self.process_video)
        
        self.stop_button = QPushButton("⏹️ 停止")
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(self.stop_processing)
        
        button_layout.addWidget(self.process_button)
        button_layout.addWidget(self.stop_button)
        layout.addLayout(button_layout)

        group.setLayout(layout)
        return group

    def setup_connections(self):
        """设置信号连接"""
        # 注意：在 create_file_selection_group 中已连接 select_button 和 process_button
        # 这里避免重复连接，防止一次点击触发两次，从而导致文件选择框或处理逻辑重复弹出
        self.copy_button.clicked.connect(self.copy_rewritten_text)
        self.save_button.clicked.connect(self.save_results)
        self.clear_button.clicked.connect(self.clear_all)

    def select_video_file(self):
        """选择视频文件"""
        try:
            supported_formats = CONFIG.get('video.supported_formats',
                                      ['.mp4', '.mov', '.mkv', '.avi', '.flv', '.wmv', '.webm'])

            file_filter = f"视频文件 ({' '.join(f'*{fmt}' for fmt in supported_formats)});;所有文件 (*.*)"

            # 创建文件对话框对象，而不是使用静态方法
            file_dialog = QFileDialog(self)
            file_dialog.setWindowTitle("选择视频文件")
            file_dialog.setNameFilter(file_filter)
            file_dialog.setAcceptMode(QFileDialog.AcceptOpen)
            file_dialog.setFileMode(QFileDialog.ExistingFile)
            
            # 设置对话框属性
            file_dialog.setOption(QFileDialog.DontUseNativeDialog, False)
            
            # 显示对话框并获取结果
            if file_dialog.exec_() == QFileDialog.Accepted:
                file_paths = file_dialog.selectedFiles()
                if file_paths:
                    file_path = file_paths[0]
                    # 确保对话框完全关闭
                    file_dialog.deleteLater()
                    # 处理选择的文件
                    self.load_video_file(file_path)
            else:
                # 用户取消选择，也确保对话框完全关闭
                file_dialog.deleteLater()
                
            # 强制进行事件循环，确保窗口关闭
            from PyQt5.QtCore import QCoreApplication
            QCoreApplication.processEvents()
            
        except Exception as e:
            logger.error(f"选择视频文件时出错: {e}")
            QMessageBox.critical(self, "错误", f"选择视频文件时出错：\n{str(e)}")
            # 确保事件循环继续
            from PyQt5.QtCore import QCoreApplication
            QCoreApplication.processEvents()

    def load_video_file(self, file_path):
        """加载视频文件"""
        try:
            video_path = Path(file_path)

            # 验证视频文件
            validation = VideoUtils.validate_video_file(
                video_path,
                CONFIG.get('video.max_file_size_mb', 500)
            )

            if not validation['valid']:
                errors = '\n'.join(validation['errors'])
                QMessageBox.warning(self, "文件错误", f"视频文件无效：\n{errors}")
                return

            # 显示文件信息
            self.current_video_path = video_path
            self.path_label.setText(f"📹 {video_path.name}")

            # 显示文件详细信息
            info = validation.get('info', {})
            info_text = []
            if 'duration' in info:
                info_text.append(f"时长: {VideoUtils.format_duration(info['duration'])}")
            if 'resolution' in info:
                info_text.append(f"分辨率: {info['resolution']}")
            if 'file_size_mb' in info:
                info_text.append(f"大小: {info['file_size_mb']}MB")

            if info_text:
                self.file_info_label.setText(" | ".join(info_text))
            else:
                self.file_info_label.setText("")

            # 显示警告信息
            warnings = validation.get('warnings', [])
            if warnings:
                QMessageBox.warning(self, "文件警告",
                                 f"视频文件有以下警告：\n" + "\n".join(warnings))

            # 启用处理按钮
            self.process_button.setEnabled(True)
            self.status_label.setText("视频文件已加载")

            logger.info(f"视频文件已加载: {video_path}")

        except Exception as e:
            logger.error(f"加载视频文件失败: {e}")
            QMessageBox.critical(self, "错误", f"无法加载视频文件：\n{str(e)}")

    def process_video(self):
        """处理视频文件"""
        try:
            if not self.current_video_path:
                # 使用正确管理的对话框
                warning_dialog = QMessageBox(self)
                warning_dialog.setWindowTitle("警告")
                warning_dialog.setText("请先选择视频文件")
                warning_dialog.setIcon(QMessageBox.Warning)
                warning_dialog.exec_()
                warning_dialog.deleteLater()
                return

            # 使用更直接的对话框创建方式
            dialog = QMessageBox(self)
            dialog.setWindowTitle("确认处理")
            dialog.setText("确定要开始处理这个视频吗？\n这将包括：\n1. 提取音频\n2. 语音识别\n3. AI文案改写")
            dialog.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
            dialog.setDefaultButton(QMessageBox.No)
            dialog.setIcon(QMessageBox.Question)
            
            # 显示对话框并获取结果
            reply = dialog.exec_()
            
            # 确保对话框完全关闭
            dialog.deleteLater()
            
            # 强制进行事件循环，确保对话框完全关闭
            from PyQt5.QtCore import QCoreApplication
            QCoreApplication.processEvents()

            # 处理结果
            if reply == QMessageBox.Yes:
                # 在返回事件循环后立即开始处理，避免阻塞UI
                self.start_processing()
            # 对于No响应，我们不需要做任何事情，只是返回
            
        except Exception as e:
            logger.error(f"处理确认对话框时出错: {e}")
            # 即使对话框出错，也应该提供一个继续处理的选项
            try:
                error_dialog = QMessageBox(self)
                error_dialog.setWindowTitle("错误发生")
                error_dialog.setText(f"显示确认对话框时出现错误：{str(e)}\n是否仍然继续处理？")
                error_dialog.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
                error_dialog.setDefaultButton(QMessageBox.No)
                error_dialog.setIcon(QMessageBox.Question)
                reply = error_dialog.exec_()
                error_dialog.deleteLater()
                
                if reply == QMessageBox.Yes:
                    self.start_processing()
            except:
                # 如果所有对话框都失败，直接开始处理
                self.start_processing()
                
            # 强制进行事件循环，确保程序响应
            from PyQt5.QtCore import QCoreApplication
            QCoreApplication.processEvents()

    def start_processing(self):
        """开始处理流程"""
        try:
            # 禁用控件
            self.set_controls_enabled(False)

            # 显示进度条
            self.progress_bar.setVisible(True)
            self.progress_bar.setValue(0)

            # 创建工作线程
            self.current_worker = WorkerThread('extract_audio',
                                       video_path=self.current_video_path)
            self.current_worker.progress_updated.connect(self.update_progress)
            self.current_worker.status_updated.connect(self.update_status)
            self.current_worker.result_ready.connect(self.handle_worker_result)
            self.current_worker.error_occurred.connect(self.handle_worker_error)
            self.current_worker.finished.connect(self.worker_finished)

            # 启动线程
            self.current_worker.start()

            self.status_label.setText("正在提取音频...")

        except Exception as e:
            logger.error(f"启动处理失败: {e}")
            QMessageBox.critical(self, "错误", f"启动处理失败：\n{str(e)}")
            self.restore_controls()

    def stop_processing(self):
        """停止当前处理"""
        try:
            if self.is_worker_running():
                logger.info("用户请求停止处理")
                
                # 显示确认对话框
                reply = QMessageBox.question(
                    self, 
                    "确认停止", 
                    "确定要停止当前处理吗？",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No
                )
                
                if reply == QMessageBox.Yes:
                    # 更新状态
                    self.status_label.setText("正在停止处理...")
                    
                    # 停止工作线程
                    self.cleanup_worker_threads()
                    
                    # 恢复控件状态
                    self.restore_controls()
                    
                    # 更新状态
                    self.status_label.setText("处理已停止")
                    self.progress_bar.setValue(0)
                    
                    logger.info("处理已被用户停止")
            else:
                logger.warning("没有正在运行的处理任务")
                
        except Exception as e:
            logger.error(f"停止处理时出错: {e}")
            self.restore_controls()

    def update_progress(self, progress, message):
        """更新进度"""
        try:
            self.progress_bar.setValue(progress)
            self.status_label.setText(message)
            
            # 强制进行事件循环，确保UI更新
            from PyQt5.QtCore import QCoreApplication
            QCoreApplication.processEvents()
        except Exception as e:
            logger.error(f"更新进度时出错: {e}")

    def update_status(self, message):
        """更新状态"""
        try:
            self.status_label.setText(message)
            
            # 强制进行事件循环，确保UI更新
            from PyQt5.QtCore import QCoreApplication
            QCoreApplication.processEvents()
        except Exception as e:
            logger.error(f"更新状态时出错: {e}")

    def handle_worker_result(self, result):
        """处理工作线程结果"""
        try:
            result_type = result.get('type')
            data = result.get('data', {})

            if result_type == 'audio_extracted':
                self.current_audio_path = data['audio_path']
                self.start_transcription()

            elif result_type == 'transcription_completed':
                self.original_text = data['text']
                self.original_text_edit.setText(self.original_text)
                self.start_rewrite()

            elif result_type == 'rewrite_completed':
                self.rewritten_text = data['rewritten_text']
                self.rewritten_text_edit.setText(self.rewritten_text)
                self.processing_completed()
                
            # 强制进行事件循环，确保UI更新
            from PyQt5.QtCore import QCoreApplication
            QCoreApplication.processEvents()
            
        except Exception as e:
            logger.error(f"处理工作线程结果时出错: {e}")
            self.handle_worker_error(str(e))

    def handle_worker_error(self, error_message):
        """处理工作线程错误"""
        logger.error(f"处理错误: {error_message}")

        # 清理线程资源
        self.cleanup_worker_threads()

        # 创建并正确管理对话框
        error_dialog = QMessageBox(self)
        error_dialog.setWindowTitle("处理错误")
        error_dialog.setText(f"处理过程中出现错误：\n{error_message}")
        error_dialog.setIcon(QMessageBox.Critical)
        error_dialog.exec_()
        error_dialog.deleteLater()
        
        self.restore_controls()
        
        # 强制进行事件循环，确保程序响应
        from PyQt5.QtCore import QCoreApplication
        QCoreApplication.processEvents()

    def worker_finished(self):
        """工作线程结束 - 安全清理线程资源"""
        try:
            # 使用信号发送者进行精准清理，避免误清理新线程
            from PyQt5.QtCore import QThread, QCoreApplication
            sender_thread = self.sender()
            if isinstance(sender_thread, QThread):
                if sender_thread.isRunning():
                    logger.warning("Worker finished signal received but thread still running; waiting for exit")
                    # 等待线程真正退出
                    total_wait_ms = 5000
                    step_ms = 500
                    waited = 0
                    while sender_thread.isRunning() and waited < total_wait_ms:
                        if sender_thread.wait(step_ms):
                            break
                        waited += step_ms
                # 仅删除发送者线程，避免影响当前正在运行的线程
                try:
                    sender_thread.deleteLater()
                except Exception:
                    pass

                # 若当前引用指向的正是该线程，则一并清理引用
                try:
                    if hasattr(self, 'current_worker') and self.current_worker is sender_thread:
                        self.current_worker = None
                except Exception:
                    pass

                logger.debug("工作线程资源已安全清理")
                QCoreApplication.processEvents()

        except Exception as e:
            logger.warning(f"清理工作线程时出错: {e}")
            # 确保清理引用，避免内存泄漏
            try:
                sender_thread = self.sender()
                if hasattr(self, 'current_worker') and self.current_worker is sender_thread:
                    self.current_worker = None
            except:
                pass
                
            # 强制进行事件循环，确保程序响应
            from PyQt5.QtCore import QCoreApplication
            QCoreApplication.processEvents()

    def start_transcription(self):
        """开始语音识别"""
        self.status_label.setText("正在进行语音识别...")

        self.current_worker = WorkerThread('transcribe',
                                       audio_path=self.current_audio_path)
        self.current_worker.progress_updated.connect(self.update_progress)
        self.current_worker.status_updated.connect(self.update_status)
        self.current_worker.result_ready.connect(self.handle_worker_result)
        self.current_worker.error_occurred.connect(self.handle_worker_error)
        self.current_worker.finished.connect(self.worker_finished)

        self.current_worker.start()

    def start_rewrite(self):
        """开始AI改写"""
        self.status_label.setText("正在进行AI文案改写...")

        self.current_worker = WorkerThread('rewrite_text',
                                       original_text=self.original_text)
        self.current_worker.progress_updated.connect(self.update_progress)
        self.current_worker.status_updated.connect(self.update_status)
        self.current_worker.result_ready.connect(self.handle_worker_result)
        self.current_worker.error_occurred.connect(self.handle_worker_error)
        self.current_worker.finished.connect(self.worker_finished)

        self.current_worker.start()

    def processing_completed(self):
        """处理完成"""
        self.status_label.setText("处理完成！")
        self.progress_bar.setValue(100)
        self.copy_button.setEnabled(True)
        self.save_button.setEnabled(True)
        QMessageBox.information(self, "完成",
                              "视频处理完成！\n\n"
                              "已成功提取文案并进行AI改写。")
        logger.info("视频处理流程完成")
        self.cleanup_temp_files()
        try:
            if CONFIG.get('ui.auto_save_output', False):
                self.auto_save_results()
        except Exception as e:
            logger.error(f"自动保存失败: {e}")

    def auto_save_results(self):
        from pathlib import Path
        from datetime import datetime
        output_dir = FileUtils.ensure_directory(CONFIG.get('ui.output_dir', 'output'))
        time_str = datetime.now().strftime('%Y%m%d_%H%M%S')
        base = Path(getattr(self, 'current_video_path', '')).stem if getattr(self, 'current_video_path', None) else 'result'
        base_clean = FileUtils.clean_filename(f"{time_str}_{base}")
        results = {
            'timestamp': datetime.now().isoformat(),
            'video_file': str(getattr(self, 'current_video_path', '')) if getattr(self, 'current_video_path', None) else None,
            'original_text': self.original_text or '',
            'rewritten_text': self.rewritten_text or ''
        }
        json_path = FileUtils.get_unique_filename(output_dir, f"{base_clean}", ".json")
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        orig_path = FileUtils.get_unique_filename(output_dir, f"{base_clean}.orig", ".txt")
        with open(orig_path, 'w', encoding='utf-8') as f:
            f.write(self.original_text or '')
        rw_path = FileUtils.get_unique_filename(output_dir, f"{base_clean}_爆款文案", ".txt")
        with open(rw_path, 'w', encoding='utf-8') as f:
            f.write(self.rewritten_text or '')
        if hasattr(self, 'status_bar') and self.status_bar:
            try:
                self.status_bar.showMessage(f"结果已自动保存到: {output_dir}", 5000)
            except Exception:
                pass
        logger.info(f"自动保存完成: {json_path}, {orig_path}, {rw_path}")
        from PyQt5.QtCore import QCoreApplication
        QCoreApplication.processEvents()

    def set_controls_enabled(self, enabled):
        """设置控件状态"""
        try:
            # 基本控件状态设置
            if hasattr(self, 'select_button') and self.select_button:
                self.select_button.setEnabled(enabled)
            
            if hasattr(self, 'process_button') and self.process_button:
                self.process_button.setEnabled(enabled and self.current_video_path is not None)
            
            # 停止按钮：只有在处理时（enabled=False）且确实有工作线程运行时才启用
            if hasattr(self, 'stop_button') and self.stop_button:
                try:
                    worker_running = False
                    if hasattr(self, 'is_worker_running') and callable(self.is_worker_running):
                        worker_running = self.is_worker_running()
                        # 确保返回值是布尔类型
                        if worker_running is None:
                            worker_running = False
                        worker_running = bool(worker_running)
                    self.stop_button.setEnabled(not enabled and worker_running)
                except Exception as e:
                    logger.warning(f"设置停止按钮状态时出错: {e}")
                    self.stop_button.setEnabled(False)
            
            if hasattr(self, 'copy_button') and self.copy_button:
                self.copy_button.setEnabled(enabled and bool(self.rewritten_text))
            
            if hasattr(self, 'save_button') and self.save_button:
                self.save_button.setEnabled(enabled and bool(self.rewritten_text))
                
        except Exception as e:
            logger.error(f"设置控件状态时发生错误: {e}")
            # 在出错时至少确保基本控件可用
            try:
                if hasattr(self, 'select_button') and self.select_button:
                    self.select_button.setEnabled(True)
                if hasattr(self, 'stop_button') and self.stop_button:
                    self.stop_button.setEnabled(False)
            except:
                pass

    def restore_controls(self):
        """恢复控件状态"""
        try:
            if hasattr(self, 'progress_bar') and self.progress_bar:
                self.progress_bar.setVisible(False)
                self.progress_bar.setValue(0)
            
            if hasattr(self, 'stop_button') and self.stop_button:
                self.stop_button.setEnabled(False)  # 确保停止按钮被禁用
            
            self.set_controls_enabled(True)
        except Exception as e:
            logger.error(f"恢复控件状态时发生错误: {e}")
            # 至少尝试恢复基本状态
            try:
                if hasattr(self, 'stop_button') and self.stop_button:
                    self.stop_button.setEnabled(False)
            except:
                pass

    def cleanup_worker_threads(self):
        """清理所有工作线程"""
        try:
            if hasattr(self, 'current_worker') and self.current_worker:
                if self.current_worker.isRunning():
                    logger.info("清理时发现运行中的线程，正在停止...")
                    self.current_worker.stop()
                    # 协作式等待，避免强制终止
                    total_wait_ms = 10000
                    step_ms = 500
                    waited = 0
                    while self.current_worker.isRunning() and waited < total_wait_ms:
                        if self.current_worker.wait(step_ms):
                            break
                        waited += step_ms

                # 清理引用
                self.current_worker = None
                logger.debug("工作线程已清理")

        except Exception as e:
            logger.warning(f"清理工作线程失败: {e}")

    def is_worker_running(self):
        """检查是否有工作线程正在运行"""
        try:
            return (hasattr(self, 'current_worker') and
                   self.current_worker and
                   self.current_worker.isRunning())
        except:
            return False

    def cleanup_temp_files(self):
        """清理临时文件"""
        try:
            if self.current_audio_path:
                FileUtils.safe_delete(self.current_audio_path)
                self.current_audio_path = None
                logger.debug("临时音频文件已清理")
        except Exception as e:
            logger.warning(f"清理临时文件失败: {e}")

    def copy_rewritten_text(self):
        """复制改写文案"""
        if self.rewritten_text:
            clipboard = QApplication.clipboard()
            clipboard.setText(self.rewritten_text)

            self.status_bar.showMessage("文案已复制到剪贴板", 3000)
            logger.info("改写文案已复制到剪贴板")

    def save_results(self):
        """保存处理结果"""
        try:
            # 选择保存位置
            file_dialog = QFileDialog()
            file_dialog.setAcceptMode(QFileDialog.AcceptSave)
            file_dialog.setNameFilter("文本文件 (*.txt);;所有文件 (*.*)")
            file_dialog.setDefaultSuffix("txt")

            if file_dialog.exec_():
                file_path = file_dialog.selectedFiles()[0]

                # 保存结果
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write("=" * 50 + "\n")
                    f.write("视频文案AI改写结果\n")
                    f.write("=" * 50 + "\n\n")

                    f.write("【原始文案】\n")
                    f.write("-" * 20 + "\n")
                    f.write(self.original_text + "\n\n")

                    f.write("【AI改写文案】\n")
                    f.write("-" * 20 + "\n")
                    f.write(self.rewritten_text + "\n\n")

                    f.write("=" * 50 + "\n")
                    f.write(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                    f.write("=" * 50 + "\n")

                self.status_bar.showMessage(f"结果已保存到: {file_path}", 5000)
                logger.info(f"处理结果已保存到: {file_path}")

        except Exception as e:
            logger.error(f"保存结果失败: {e}")
            QMessageBox.critical(self, "保存失败", f"保存结果失败：\n{str(e)}")

    def cleanup_worker_threads(self):
        """清理所有工作线程"""
        try:
            if hasattr(self, 'current_worker') and self.current_worker:
                if self.current_worker.isRunning():
                    logger.info("清理时发现运行中的线程，正在停止...")
                    self.current_worker.stop()
                    self.current_worker.wait(2000)

                # 清理引用
                self.current_worker = None
                logger.debug("工作线程已清理")

        except Exception as e:
            logger.warning(f"清理工作线程失败: {e}")
            # 确保清理引用
            try:
                if hasattr(self, 'current_worker'):
                    self.current_worker = None
            except:
                pass

    def clear_all(self):
        """清空所有内容"""
        # 检查是否有任务正在运行
        if self.is_worker_running():
            # 创建并正确管理对话框
            confirm_dialog = QMessageBox(self)
            confirm_dialog.setWindowTitle("确认清空")
            confirm_dialog.setText("当前有任务正在运行，确定要清空所有内容吗？\n这将停止当前任务。")
            confirm_dialog.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
            confirm_dialog.setDefaultButton(QMessageBox.No)
            confirm_dialog.setIcon(QMessageBox.Question)
            reply = confirm_dialog.exec_()
            confirm_dialog.deleteLater()
            
            if reply != QMessageBox.Yes:
                return
            
            # 停止当前任务
            self.cleanup_worker_threads()
        
        reply = QMessageBox.question(
            self, "确认清空",
            "确定要清空所有内容吗？\n这将清除所有文本和文件选择。",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            self.current_video_path = None
            self.current_audio_path = None
            self.original_text = ""
            self.rewritten_text = ""

            self.path_label.setText("未选择文件")
            self.file_info_label.setText("")
            self.original_text_edit.clear()
            self.rewritten_text_edit.clear()

            self.process_button.setEnabled(False)
            self.copy_button.setEnabled(False)
            self.save_button.setEnabled(False)

            self.status_label.setText("已清空所有内容")
            logger.info("用户清空了所有内容")

    def show_settings(self):
        """显示设置对话框"""
        QMessageBox.information(self, "设置",
                             "设置功能正在开发中...\n"
                             "可通过编辑 config/settings.json 手动配置。")

    def show_about(self):
        """显示关于对话框"""
        QMessageBox.about(self, "关于",
                        f"""<h2>🎬 视频文案AI爆款改写工具</h2>
                        <p><b>版本:</b> {CONFIG.get('app.version', '1.0.0')}</p>
                        <p><b>作者:</b> {CONFIG.get('app.author', 'AI Assistant')}</p>
                        <br>
                        <p><b>功能特性:</b></p>
                        <ul>
                            <li>🎬 视频文件智能处理</li>
                            <li>🎤 本地Whisper语音识别</li>
                            <li>🦙 Ollama AI文案改写</li>
                            <li>⚡ GPU/CPU自动切换</li>
                            <li>📁 拖拽文件上传</li>
                            <li>💾 一键保存结果</li>
                        </ul>
                        <br>
                        <p><em>让AI助您创作更精彩的内容！</em></p>
                        """)

    def dragEnterEvent(self, event: QDragEnterEvent):
        """拖拽进入事件"""
        if event.mimeData().hasUrls():
            # 检查是否为视频文件
            urls = event.mimeData().urls()
            for url in urls:
                file_path = url.toLocalFile()
                if VideoUtils.is_video_file(file_path):
                    event.acceptProposedAction()
                    return
        event.ignore()

    def dropEvent(self, event: QDropEvent):
        """拖拽放下事件"""
        urls = event.mimeData().urls()
        for url in urls:
            file_path = url.toLocalFile()
            if VideoUtils.is_video_file(file_path):
                self.load_video_file(file_path)
                break

    def closeEvent(self, event):
        """关闭事件 - 确保线程安全退出"""
        try:
            logger.info("开始关闭应用程序...")

            # 1. 停止当前工作线程
            if hasattr(self, 'current_worker') and self.current_worker:
                if self.current_worker.isRunning():
                    logger.info("正在停止工作线程...")
                    self.current_worker.stop()

                    # 协作式等待更长时间，避免强制终止
                    total_wait_ms = 15000  # 最多等待15秒
                    step_ms = 1000
                    waited = 0
                    while self.current_worker.isRunning() and waited < total_wait_ms:
                        if self.current_worker.wait(step_ms):
                            break
                        waited += step_ms
                    if self.current_worker.isRunning():
                        logger.warning("关闭时线程仍在退出中，将交由系统在退出期间回收")

                # 清理线程引用
                self.current_worker = None

            # 2. 清理其他可能的线程
            from PyQt5.QtCore import QThreadPool
            thread_pool = QThreadPool.globalInstance()
            if thread_pool.activeThreadCount() > 0:
                logger.info(f"发现 {thread_pool.activeThreadCount()} 个活动线程，等待清理...")
                thread_pool.waitForDone(5000)  # 等待5秒

            # 3. 清理临时文件
            self.cleanup_temp_files()

            logger.info("应用程序已安全关闭")

        except Exception as e:
            logger.error(f"关闭应用程序时出错: {e}")
            # 即使出错也要确保窗口关闭
            try:
                # 强制清理线程
                if hasattr(self, 'current_worker') and self.current_worker:
                    self.current_worker.terminate()
                    self.current_worker = None
            except:
                pass

        finally:
            # 确保接受关闭事件
            event.accept()

def main():
    """主函数"""
    try:
        # 设置日志
        LogUtils.setup_logging(
            log_level=CONFIG.get('system.log_level', 'INFO'),
            log_dir=CONFIG.get('system.log_dir', 'logs')
        )

        # 检查PyQt5
        if not PYQT_AVAILABLE:
            print("❌ PyQt5 未安装，无法启动图形界面")
            print("请安装依赖: pip install pyqt")
            return

        # 修复Qt平台插件问题
        import os
        # 设置Qt插件路径环境变量
        if 'QT_PLUGIN_PATH' not in os.environ:
            # 尝试找到conda环境中的Qt插件路径
            conda_prefix = os.environ.get('CONDA_PREFIX')
            if conda_prefix:
                qt_plugin_path = os.path.join(conda_prefix, 'Library', 'plugins')
                if os.path.exists(qt_plugin_path):
                    os.environ['QT_PLUGIN_PATH'] = qt_plugin_path
                    logger.info(f"设置Qt插件路径: {qt_plugin_path}")

        # 设置Qt平台插件
        os.environ['QT_QPA_PLATFORM_PLUGIN_PATH'] = os.environ.get('QT_PLUGIN_PATH', '')
        
        # 创建应用
        app = QApplication(sys.argv)
        app.setStyle('Fusion')  # 使用Fusion样式

        # 创建主窗口
        window = MainWindow()
        window.show()

        # 运行应用
        sys.exit(app.exec_())

    except Exception as e:
        logger.critical(f"应用程序启动失败: {e}")
        print(f"❌ 应用程序启动失败: {e}")

if __name__ == "__main__":
    main()