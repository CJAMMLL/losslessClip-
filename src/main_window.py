import sys
import os
import cv2
import numpy as np
from pathlib import Path
from datetime import timedelta
from typing import Optional, Tuple

from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QPushButton, QLabel, QFileDialog, QMessageBox,
    QSlider, QLineEdit
)
from PyQt5.QtCore import Qt, QTimer, QPoint, QThread, pyqtSignal, QEvent
from PyQt5.QtGui import QImage, QPixmap, QDragEnterEvent, QDropEvent, QKeyEvent, QIcon

from video_processor import VideoProcessor

# 添加自定义 QSlider 类
class CustomSlider(QSlider):
    """自定义进度条，禁用键盘方向键控制"""
    def keyPressEvent(self, event):
        # 忽略所有键盘事件
        event.ignore()

class VideoLoadThread(QThread):
    """视频加载线程"""
    finished = pyqtSignal(bool)  # 加载完成信号
    progress = pyqtSignal(str)   # 进度信号

    def __init__(self, video_processor, file_path):
        super().__init__()
        self.video_processor = video_processor
        self.file_path = file_path

    def run(self):
        try:
            self.progress.emit("正在加载视频信息...")
            success = self.video_processor.load_video(self.file_path)
            self.finished.emit(success)
        except Exception as e:
            print(f"加载视频线程错误: {str(e)}")
            self.finished.emit(False)

class VideoCutThread(QThread):
    """视频剪辑线程"""
    finished = pyqtSignal(bool, str)  # (成功与否, 输出路径)
    progress = pyqtSignal(str)        # 进度信息

    def __init__(self, video_processor, start_time, end_time, output_path):
        super().__init__()
        self.video_processor = video_processor
        self.start_time = start_time
        self.end_time = end_time
        self.output_path = output_path
        
    def run(self):
        try:
            self.progress.emit("正在导出视频...")
            success = self.video_processor.cut_video(
                self.start_time,
                self.end_time,
                self.output_path
            )
            self.finished.emit(success, self.output_path)
        except Exception as e:
            print(f"视频剪辑线程错误: {str(e)}")
            self.finished.emit(False, self.output_path)

class MainWindow(QMainWindow):
    """主窗口类"""
    
    def __init__(self):
        super().__init__()
        self.video_processor = VideoProcessor()
        self.cap: Optional[cv2.VideoCapture] = None
        self.current_frame: Optional[QImage] = None
        self.is_playing = False
        self.start_time = 0.0
        self.end_time = 0.0
        self.load_thread = None
        self.preview_width = 480   # 降至270p用于处理
        self.preview_height = 270
        self.display_width = 854   # 保持480p的显示大小
        self.display_height = 480
        self.slider_pressed = False
        
        # 初始化帧缓存和pixmap缓存
        self._frame_buffer = None
        self._cached_pixmap = None
        
        # 添加样式表定义
        self.default_button_style = ""  # 默认样式
        self.marked_button_style = "background-color: #2196F3; color: white;"  # 标记后的样式
        
        # 设置窗口
        self.setWindowTitle("losslessClip无损剪辑v1.1")
        self.setMinimumSize(800, 600)
        self.setAcceptDrops(True)
        
        # 设置主窗口接受键盘焦点
        self.setFocusPolicy(Qt.StrongFocus)
        
        # 设置窗口图标
        if hasattr(sys, '_MEIPASS'):
            # PyInstaller 打包后的路径
            icon_path = os.path.join(sys._MEIPASS, 'assets', 'teamG.ico')
        else:
            # 开发环境路径
            icon_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'assets', 'teamG.ico')
            
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
            print(f"窗口图标路径存在: {icon_path}")
        else:
            print(f"窗口图标路径不存在: {icon_path}")
        
        # 创建UI（先创建UI，再设置按钮焦点）
        self._create_ui()
        
        # 设置所有按钮不接受焦点
        self.play_pause_btn.setFocusPolicy(Qt.NoFocus)
        self.prev_frame_btn.setFocusPolicy(Qt.NoFocus)
        self.next_frame_btn.setFocusPolicy(Qt.NoFocus)
        self.mark_start_btn.setFocusPolicy(Qt.NoFocus)
        self.mark_end_btn.setFocusPolicy(Qt.NoFocus)
        self.reset_btn.setFocusPolicy(Qt.NoFocus)
        self.export_btn.setFocusPolicy(Qt.NoFocus)
        
        # 设置定时器用于视频播放
        self.timer = QTimer()
        self.timer.timeout.connect(self._update_frame)
        self.timer.start(66)  # 1000ms/15fps ≈ 66ms
        
    def _create_ui(self):
        """创建用户界面"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
        # 视频显示区域
        self.video_label = QLabel()
        self.video_label.setAlignment(Qt.AlignCenter)
        self.video_label.setStyleSheet("""
            QLabel {
                background-color: black;
                min-width: 854px;
                min-height: 480px;
            }
        """)
        # 设置缩放策略
        self.video_label.setScaledContents(True)
        layout.addWidget(self.video_label, stretch=1)
        
        # 时间显示和输入
        time_layout = QHBoxLayout()
        self.current_time_edit = QLineEdit()
        self.current_time_edit.setFixedWidth(100)
        self.current_time_edit.returnPressed.connect(self._on_time_input)
        self.duration_label = QLabel("/ 00:00:00.000")
        time_layout.addWidget(self.current_time_edit)
        time_layout.addWidget(self.duration_label)
        time_layout.addStretch()
        layout.addLayout(time_layout)
        
        # 进度条
        self.progress_slider = CustomSlider(Qt.Horizontal)
        self.progress_slider.setTracking(True)
        self.progress_slider.sliderMoved.connect(self._on_slider_moved)
        self.progress_slider.sliderReleased.connect(self._on_slider_released)
        layout.addWidget(self.progress_slider)
        
        # 控制按钮
        controls_layout = QHBoxLayout()
        
        # 播放控制
        self.prev_frame_btn = QPushButton("上一帧")
        self.play_pause_btn = QPushButton("播放")
        self.next_frame_btn = QPushButton("下一帧")
        
        self.prev_frame_btn.clicked.connect(self._prev_frame)
        self.play_pause_btn.clicked.connect(self._toggle_play)
        self.next_frame_btn.clicked.connect(self._next_frame)
        
        controls_layout.addWidget(self.prev_frame_btn)
        controls_layout.addWidget(self.play_pause_btn)
        controls_layout.addWidget(self.next_frame_btn)
        
        controls_layout.addStretch()
        
        # 剪辑控制
        self.mark_start_btn = QPushButton("开始")
        self.mark_end_btn = QPushButton("结束")
        self.reset_btn = QPushButton("重置")
        self.export_btn = QPushButton("导出")
        
        self.mark_start_btn.clicked.connect(self._mark_start)
        self.mark_end_btn.clicked.connect(self._mark_end)
        self.reset_btn.clicked.connect(self._reset_marks)
        self.export_btn.clicked.connect(self._export_video)
        
        controls_layout.addWidget(self.mark_start_btn)
        controls_layout.addWidget(self.mark_end_btn)
        controls_layout.addWidget(self.reset_btn)
        controls_layout.addWidget(self.export_btn)
        
        layout.addLayout(controls_layout)
        
    def _format_time(self, seconds: float) -> str:
        """将秒数格式化为时间字符串"""
        td = timedelta(seconds=seconds)
        hours = td.seconds // 3600
        minutes = (td.seconds % 3600) // 60
        seconds = td.seconds % 60
        milliseconds = td.microseconds // 1000
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}.{milliseconds:03d}"
        
    def _parse_time(self, time_str: str) -> float:
        """解析时间字符串为秒数"""
        try:
            parts = time_str.split(":")
            if len(parts) == 3:
                hours, minutes, seconds = parts
                seconds, milliseconds = seconds.split(".")
                total_seconds = (
                    int(hours) * 3600 + 
                    int(minutes) * 60 + 
                    int(seconds) + 
                    int(milliseconds) / 1000
                )
                return total_seconds
        except:
            pass
        return 0.0
        
    def _update_frame(self):
        """更新视频帧"""
        if self.cap and self.is_playing:
            try:
                ret, frame = self.cap.read()
                if ret:
                    # 初始化帧缓存（使用低分辨率）
                    if self._frame_buffer is None:
                        self._frame_buffer = np.empty((self.preview_height, self.preview_width, 3), dtype=np.uint8)
                    
                    # 使用预分配的缓存进行缩放（缩放到低分辨率）
                    if frame.shape[:2] != (self.preview_height, self.preview_width):
                        cv2.resize(
                            frame, 
                            (self.preview_width, self.preview_height),
                            self._frame_buffer,
                            interpolation=cv2.INTER_NEAREST
                        )
                        rgb_frame = cv2.cvtColor(self._frame_buffer, cv2.COLOR_BGR2RGB)
                    else:
                        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    
                    # 创建低分辨率QImage
                    image = QImage(
                        rgb_frame.data,
                        self.preview_width,
                        self.preview_height,
                        rgb_frame.strides[0],
                        QImage.Format_RGB888
                    )
                    
                    # 创建高分辨率QPixmap
                    if self._cached_pixmap is None:
                        self._cached_pixmap = QPixmap.fromImage(image).scaled(
                            self.display_width,
                            self.display_height,
                            Qt.KeepAspectRatio,
                            Qt.SmoothTransformation  # 使用平滑缩放提高显示质量
                        )
                    else:
                        self._cached_pixmap.convertFromImage(image)
                        self._cached_pixmap = self._cached_pixmap.scaled(
                            self.display_width,
                            self.display_height,
                            Qt.KeepAspectRatio,
                            Qt.SmoothTransformation
                        )
                    
                    self.video_label.setPixmap(self._cached_pixmap)
                    
                    # 减少进度更新频率
                    if not self.slider_pressed:
                        current_time = self.cap.get(cv2.CAP_PROP_POS_FRAMES) / self.cap.get(cv2.CAP_PROP_FPS)
                        self._update_time_display(current_time)
                else:
                    self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    
            except Exception as e:
                print(f"更新帧时发生错误: {str(e)}")
            
    def _update_time_display(self, current_time):
        """更新时间显示"""
        try:
            if not hasattr(self, 'video_processor') or not self.video_processor:
                return
            
            if self.video_processor.duration <= 0:
                return
            
            progress = int(current_time * 1000 / self.video_processor.duration)
            self.progress_slider.setValue(progress)
            self.current_time_edit.setText(self._format_time(current_time))
            
        except Exception as e:
            print(f"更新时间显示时发生错误: {str(e)}")
            
    def _on_slider_moved(self, value: int):
        """进度条拖动时的处理"""
        if self.cap:
            self.slider_pressed = True
            time_pos = value * self.video_processor.duration / 1000
            self._update_time_display(time_pos)
            
            # 立即更新画面
            frame_pos = time_pos * self.cap.get(cv2.CAP_PROP_FPS)
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, frame_pos)
            # 强制更新一帧，即使在暂停状态
            ret, frame = self.cap.read()
            if ret:
                # 使用更快的插值算法
                frame = cv2.resize(
                    frame, 
                    (self.preview_width, self.preview_height),
                    interpolation=cv2.INTER_NEAREST
                )
                
                # 转换颜色空间
                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                
                # 创建QImage
                image = QImage(
                    rgb_frame.data,
                    self.preview_width,
                    self.preview_height,
                    rgb_frame.strides[0],
                    QImage.Format_RGB888
                )
                
                self.video_label.setPixmap(QPixmap.fromImage(image))
            
    def _on_slider_released(self):
        """进度条释放时的处理"""
        if self.cap:
            self.slider_pressed = False
            value = self.progress_slider.value()
            time_pos = value * self.video_processor.duration / 1000
            frame_pos = time_pos * self.cap.get(cv2.CAP_PROP_FPS)
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, frame_pos)
            
    def _on_time_input(self):
        """时间输入处理"""
        if self.cap:
            try:
                time_pos = self._parse_time(self.current_time_edit.text())
                frame_pos = time_pos * self.cap.get(cv2.CAP_PROP_FPS)
                self.cap.set(cv2.CAP_PROP_POS_FRAMES, frame_pos)
                
                # 读取并显示当前帧
                ret, frame = self.cap.read()
                if ret:
                    # 调整大小
                    frame = cv2.resize(
                        frame, 
                        (self.preview_width, self.preview_height),
                        interpolation=cv2.INTER_NEAREST
                    )
                    
                    # 转换颜色空间
                    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    
                    # 创建QImage
                    image = QImage(
                        rgb_frame.data,
                        self.preview_width,
                        self.preview_height,
                        rgb_frame.strides[0],
                        QImage.Format_RGB888
                    )
                    
                    self.video_label.setPixmap(QPixmap.fromImage(image))
                
                # 更新时间显示和进度条
                self._update_time_display(time_pos)
                
            except Exception as e:
                print(f"时间输入处理错误: {str(e)}")
            
    def _toggle_play(self):
        """切换播放/暂停状态"""
        if self.cap:
            self.is_playing = not self.is_playing
            self.play_pause_btn.setText("暂停" if self.is_playing else "播放")
            
    def _prev_frame(self):
        """跳转到上一帧"""
        if self.cap:
            try:
                # 获取当前帧位置
                current_frame = self.cap.get(cv2.CAP_PROP_POS_FRAMES)
                # 确保不会跳到负数帧
                if current_frame > 1:
                    # 跳转到上一帧
                    self.cap.set(cv2.CAP_PROP_POS_FRAMES, current_frame - 2)  # 减2是因为读取会自动前进一帧
                    # 读取并显示帧
                    ret, frame = self.cap.read()
                    if ret:
                        # 调整大小
                        frame = cv2.resize(
                            frame, 
                            (self.preview_width, self.preview_height),
                            interpolation=cv2.INTER_NEAREST
                        )
                        
                        # 转换颜色空间
                        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                        
                        # 创建QImage
                        image = QImage(
                            rgb_frame.data,
                            self.preview_width,
                            self.preview_height,
                            rgb_frame.strides[0],
                            QImage.Format_RGB888
                        )
                        
                        self.video_label.setPixmap(QPixmap.fromImage(image))
                        
                        # 更新时间显示
                        current_time = current_frame / self.cap.get(cv2.CAP_PROP_FPS)
                        self._update_time_display(current_time)
                        
            except Exception as e:
                print(f"跳转到上一帧时发生错误: {str(e)}")

    def _next_frame(self):
        """跳转到下一帧"""
        if self.cap:
            try:
                # 读取并显示下一帧
                ret, frame = self.cap.read()
                if ret:
                    # 调整大小
                    frame = cv2.resize(
                        frame, 
                        (self.preview_width, self.preview_height),
                        interpolation=cv2.INTER_NEAREST
                    )
                    
                    # 转换颜色空间
                    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    
                    # 创建QImage
                    image = QImage(
                        rgb_frame.data,
                        self.preview_width,
                        self.preview_height,
                        rgb_frame.strides[0],
                        QImage.Format_RGB888
                    )
                    
                    self.video_label.setPixmap(QPixmap.fromImage(image))
                    
                    # 更新时间显示
                    current_frame = self.cap.get(cv2.CAP_PROP_POS_FRAMES)
                    current_time = current_frame / self.cap.get(cv2.CAP_PROP_FPS)
                    self._update_time_display(current_time)
                    
                else:
                    # 如果到达视频末尾，回到最后一帧
                    total_frames = self.cap.get(cv2.CAP_PROP_FRAME_COUNT)
                    self.cap.set(cv2.CAP_PROP_POS_FRAMES, total_frames - 1)
                    
            except Exception as e:
                print(f"跳转到下一帧时发生错误: {str(e)}")
            
    def _mark_start(self):
        """标记开始时间点"""
        if self.cap:
            try:
                current_time = self.cap.get(cv2.CAP_PROP_POS_FRAMES) / self.cap.get(cv2.CAP_PROP_FPS)
                # 开始时间向前对齐
                self.start_time = self.video_processor.find_nearest_frame(self.cap, current_time, 'prev')
                
                # 设置按钮样式
                self.mark_start_btn.setStyleSheet(self.marked_button_style)
                
                QMessageBox.information(
                    self,
                    "标记起点",
                    f"原始时间点：{self._format_time(current_time)}\n"
                    f"对齐后时间点：{self._format_time(self.start_time)}"
                )
                
            except Exception as e:
                print(f"标记起点时发生错误: {str(e)}")

    def _mark_end(self):
        """标记结束时间点"""
        if self.cap:
            try:
                current_time = self.cap.get(cv2.CAP_PROP_POS_FRAMES) / self.cap.get(cv2.CAP_PROP_FPS)
                # 结束时间向后对齐
                self.end_time = self.video_processor.find_nearest_frame(self.cap, current_time, 'next')
                
                # 设置按钮样式
                self.mark_end_btn.setStyleSheet(self.marked_button_style)
                
                QMessageBox.information(
                    self,
                    "标记终点",
                    f"原始时间点：{self._format_time(current_time)}\n"
                    f"对齐后时间点：{self._format_time(self.end_time)}"
                )
                
            except Exception as e:
                print(f"标记终点时发生错误: {str(e)}")
            
    def _reset_marks(self):
        """重置开始和结束时间标记"""
        try:
            self.start_time = 0.0
            self.end_time = self.video_processor.duration if self.video_processor else 0.0
            
            # 重置按钮样式
            self.mark_start_btn.setStyleSheet(self.default_button_style)
            self.mark_end_btn.setStyleSheet(self.default_button_style)
            
            self._update_time_display(0.0)  # 更新时间显示
            
        except Exception as e:
            print(f"重置标记时发生错误: {str(e)}")
        
    def _export_video(self):
        """导出视频片段"""
        if not self.cap:
            return
            
        if self.start_time == 0.0 and self.end_time == self.video_processor.duration:
            reply = QMessageBox.question(
                self,
                "确认导出",
                "您未手动设置时间点，是否继续导出？",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.No:
                return
                
        # 禁用界面操作
        self.setEnabled(False)
        
        # 创建并启动剪辑线程
        output_path = self.video_processor.generate_output_filename()
        self.cut_thread = VideoCutThread(
            self.video_processor,
            self.start_time,
            self.end_time,
            output_path
        )
        self.cut_thread.finished.connect(self._on_video_cut)
        self.cut_thread.progress.connect(self._update_status)
        self.cut_thread.start()
        
    def _on_video_cut(self, success: bool, output_path: str):
        """视频剪辑完成的回调"""
        self.setEnabled(True)
        if success:
            # 重置按钮样式
            self.mark_start_btn.setStyleSheet(self.default_button_style)
            self.mark_end_btn.setStyleSheet(self.default_button_style)
            
            QMessageBox.information(
                self,
                "导出成功",
                f"已导出：{output_path}"
            )
        else:
            QMessageBox.warning(
                self,
                "导出失败",
                "视频导出失败，请检查日志"
            )
        
    def _update_status(self, message: str):
        """更新状态信息"""
        self.statusBar().showMessage(message)
        
    def load_video(self, file_path: str):
        """加载视频文件"""
        try:
            if not os.path.exists(file_path):
                QMessageBox.warning(self, "错误", "视频文件不存在")
                return False
                
            # 禁用界面操作
            self.setEnabled(False)
            
            # 创建并启动加载线程
            self.load_thread = VideoLoadThread(self.video_processor, file_path)
            self.load_thread.finished.connect(self._on_video_loaded)
            self.load_thread.progress.connect(self._update_status)
            self.load_thread.start()
            
        except Exception as e:
            print(f"加载视频时发生错误: {str(e)}")
            QMessageBox.warning(self, "错误", f"加载视频失败: {str(e)}")
            self.setEnabled(True)
            return False
            
    def _on_video_loaded(self, success: bool):
        """视频加载完成的回调"""
        self.setEnabled(True)
        if not success:
            QMessageBox.warning(self, "错误", "无法获取视频信息")
            return
        
        try:
            # 初始化视频播放
            if self.cap is not None:
                self.cap.release()
            
            # 设置OpenCV的缓冲区大小
            self.cap = cv2.VideoCapture(self.video_processor.current_file)
            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 3)  # 减少缓冲区大小
            
            # 对于4K视频，进一步降低预览分辨率
            if self.video_processor.width >= 3840:  # 4K
                self.preview_width = 480   # 降到270p
                self.preview_height = 270
            elif self.video_processor.width >= 1920:  # 1080p
                self.preview_width = 640   # 360p
                self.preview_height = 360
            else:
                self.preview_width = 854   # 480p
                self.preview_height = 480
            
            if not self.cap.isOpened():
                QMessageBox.warning(self, "错误", "无法打开视频文件")
                return
            
            # 更新UI
            self.duration_label.setText(
                f"/ {self._format_time(self.video_processor.duration)}"
            )
            self.progress_slider.setRange(0, 1000)
            self.start_time = 0.0
            self.end_time = self.video_processor.duration
            self._update_time_display(0.0)
            self.is_playing = True
            self.play_pause_btn.setText("暂停")
            
        except Exception as e:
            print(f"初始化视频播放失败: {str(e)}")
            QMessageBox.warning(self, "错误", f"初始化视频播放失败: {str(e)}")
        
    def dragEnterEvent(self, event: QDragEnterEvent):
        """拖拽进入事件处理"""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            
    def dropEvent(self, event: QDropEvent):
        """拖拽释放事件处理"""
        urls = event.mimeData().urls()
        if urls:
            file_path = urls[0].toLocalFile()
            self.load_video(file_path)
            
    def contextMenuEvent(self, event):
        """右键菜单事件处理"""
        file_path = QFileDialog.getOpenFileName(
            self,
            "打开视频文件",
            "",
            "视频文件 (*.mp4 *.flv *.mov *.avi);;所有文件 (*.*)"
        )[0]  # 只获取文件路径，忽略文件类型
        
        if file_path:
            self.load_video(file_path)
            
    def closeEvent(self, event):
        """窗口关闭事件处理"""
        if self.cap is not None:
            self.cap.release()
        event.accept()

    def _seek_video(self, time_offset: float):
        """跳转视频时间
        
        Args:
            time_offset: 时间偏移量(秒)，正数向前跳转，负数向后跳转
        """
        if not self.cap:
            return
        
        try:
            # 获取当前时间位置
            current_frame = self.cap.get(cv2.CAP_PROP_POS_FRAMES)
            fps = self.cap.get(cv2.CAP_PROP_FPS)
            current_time = current_frame / fps
            
            # 计算目标时间
            target_time = current_time + time_offset
            
            # 确保时间在有效范围内
            if target_time < 0:
                target_time = 0
            if target_time > self.video_processor.duration:
                target_time = self.video_processor.duration
            
            # 计算目标帧位置
            target_frame = int(target_time * fps)
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, target_frame)
            
            # 读取并显示当前帧
            ret, frame = self.cap.read()
            if ret:
                # 使用最快的插值算法
                frame = cv2.resize(
                    frame, 
                    (self.preview_width, self.preview_height),
                    interpolation=cv2.INTER_NEAREST
                )
                
                # 使用更快的颜色空间转换
                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                
                # 避免数据复制
                image = QImage(
                    rgb_frame.data,
                    self.preview_width,
                    self.preview_height,
                    rgb_frame.strides[0],
                    QImage.Format_RGB888
                )
                
                self.video_label.setPixmap(QPixmap.fromImage(image))
                self._update_time_display(target_time)
            
        except Exception as e:
            print(f"跳转视频时间时发生错误: {str(e)}")

    def keyPressEvent(self, event: QKeyEvent):
        """处理键盘事件"""
        if event.key() == Qt.Key_Space:
            # 空格键播放/暂停切换
            self._toggle_play()
            event.accept()
        elif event.key() in (Qt.Key_Left, Qt.Key_Right):
            # 获取修饰键状态
            shift_pressed = event.modifiers() & Qt.ShiftModifier
            ctrl_pressed = event.modifiers() & Qt.ControlModifier
            
            # 根据不同的组合键设置跳转时间
            if shift_pressed and ctrl_pressed:
                # Shift+Ctrl+方向键：逐帧移动
                if event.key() == Qt.Key_Right:
                    self._next_frame()
                else:
                    self._prev_frame()
            elif shift_pressed:
                # Shift+方向键：移动0.5秒
                time_offset = 0.5 if event.key() == Qt.Key_Right else -0.5
                self._seek_video(time_offset)
            else:
                # 单独方向键：移动3秒
                time_offset = 3.0 if event.key() == Qt.Key_Right else -3.0
                self._seek_video(time_offset)
            event.accept()
        else:
            super().keyPressEvent(event)  # 其他键位交给父类处理

    def _init_video_player(self, file_path: str):
        """初始化视频播放器"""
        try:
            # 尝试使用 AMD 硬件加速
            # 首先尝试 AMD AMF 编解码器
            self.cap = cv2.VideoCapture(file_path, cv2.CAP_MSMF)  # Microsoft Media Foundation 支持 AMD 加速
            
            if not self.cap.isOpened():
                # 如果不支持硬件加速，回退到普通模式
                self.cap = cv2.VideoCapture(file_path)
                print("硬件加速不可用，使用软件解码")
            else:
                print("使用硬件加速解码")
            
            # 优化解码参数
            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # 最小缓冲区
            
            # 尝试启用所有可用的硬件加速
            self.cap.set(cv2.CAP_PROP_HW_ACCELERATION, cv2.VIDEO_ACCELERATION_ANY)
            
            # 设置解码参数
            self.cap.set(cv2.CAP_PROP_FORMAT, -1)  # 使用原生格式
            
            # 直接解码为较低分辨率
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.preview_width)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.preview_height)
            
            # 优先使用 H.264/HEVC 解码器
            codecs = [
                cv2.VideoWriter_fourcc('H', 'E', 'V', 'C'),  # HEVC/H.265
                cv2.VideoWriter_fourcc('H', '2', '6', '4'),  # H.264
                cv2.VideoWriter_fourcc('a', 'v', 'c', '1'),  # AVC
            ]
            
            # 尝试设置不同的解码器
            for codec in codecs:
                if self.cap.set(cv2.CAP_PROP_FOURCC, codec):
                    print(f"使用解码器: {chr(codec & 0xFF)}{chr((codec >> 8) & 0xFF)}"
                          f"{chr((codec >> 16) & 0xFF)}{chr((codec >> 24) & 0xFF)}")
                    break
            
            # 设置线程数为CPU核心数的一半
            import multiprocessing
            n_cores = max(1, multiprocessing.cpu_count() // 2)
            self.cap.set(cv2.CAP_PROP_THREAD_COUNT, n_cores)
            
            # 创建帧缓存
            self._frame_buffer = None
            self._cached_pixmap = None
            
        except Exception as e:
            print(f"初始化视频播放器失败: {str(e)}")
        
    def _update_frame(self):
        """更新视频帧"""
        if self.cap and self.is_playing:
            try:
                ret, frame = self.cap.read()
                if ret:
                    # 初始化帧缓存（使用低分辨率）
                    if self._frame_buffer is None:
                        self._frame_buffer = np.empty((self.preview_height, self.preview_width, 3), dtype=np.uint8)
                    
                    # 使用预分配的缓存进行缩放（缩放到低分辨率）
                    if frame.shape[:2] != (self.preview_height, self.preview_width):
                        cv2.resize(
                            frame, 
                            (self.preview_width, self.preview_height),
                            self._frame_buffer,
                            interpolation=cv2.INTER_NEAREST
                        )
                        rgb_frame = cv2.cvtColor(self._frame_buffer, cv2.COLOR_BGR2RGB)
                    else:
                        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    
                    # 创建低分辨率QImage
                    image = QImage(
                        rgb_frame.data,
                        self.preview_width,
                        self.preview_height,
                        rgb_frame.strides[0],
                        QImage.Format_RGB888
                    )
                    
                    # 创建高分辨率QPixmap
                    if self._cached_pixmap is None:
                        self._cached_pixmap = QPixmap.fromImage(image).scaled(
                            self.display_width,
                            self.display_height,
                            Qt.KeepAspectRatio,
                            Qt.SmoothTransformation  # 使用平滑缩放提高显示质量
                        )
                    else:
                        self._cached_pixmap.convertFromImage(image)
                        self._cached_pixmap = self._cached_pixmap.scaled(
                            self.display_width,
                            self.display_height,
                            Qt.KeepAspectRatio,
                            Qt.SmoothTransformation
                        )
                    
                    self.video_label.setPixmap(self._cached_pixmap)
                    
                    # 减少进度更新频率
                    if not self.slider_pressed:
                        current_time = self.cap.get(cv2.CAP_PROP_POS_FRAMES) / self.cap.get(cv2.CAP_PROP_FPS)
                        self._update_time_display(current_time)
                else:
                    self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    
            except Exception as e:
                print(f"更新帧时发生错误: {str(e)}")
            
    def _update_time_display(self, current_time):
        """更新时间显示"""
        try:
            if not hasattr(self, 'video_processor') or not self.video_processor:
                return
            
            if self.video_processor.duration <= 0:
                return
            
            progress = int(current_time * 1000 / self.video_processor.duration)
            self.progress_slider.setValue(progress)
            self.current_time_edit.setText(self._format_time(current_time))
            
        except Exception as e:
            print(f"更新时间显示时发生错误: {str(e)}")
            
    def _on_slider_moved(self, value: int):
        """进度条拖动时的处理"""
        if self.cap:
            self.slider_pressed = True
            time_pos = value * self.video_processor.duration / 1000
            self._update_time_display(time_pos)
            
            # 立即更新画面
            frame_pos = time_pos * self.cap.get(cv2.CAP_PROP_FPS)
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, frame_pos)
            # 强制更新一帧，即使在暂停状态
            ret, frame = self.cap.read()
            if ret:
                # 使用更快的插值算法
                frame = cv2.resize(
                    frame, 
                    (self.preview_width, self.preview_height),
                    interpolation=cv2.INTER_NEAREST
                )
                
                # 转换颜色空间
                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                
                # 创建QImage
                image = QImage(
                    rgb_frame.data,
                    self.preview_width,
                    self.preview_height,
                    rgb_frame.strides[0],
                    QImage.Format_RGB888
                )
                
                self.video_label.setPixmap(QPixmap.fromImage(image))
            
    def _on_slider_released(self):
        """进度条释放时的处理"""
        if self.cap:
            self.slider_pressed = False
            value = self.progress_slider.value()
            time_pos = value * self.video_processor.duration / 1000
            frame_pos = time_pos * self.cap.get(cv2.CAP_PROP_FPS)
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, frame_pos)
            
    def _on_time_input(self):
        """时间输入处理"""
        if self.cap:
            try:
                time_pos = self._parse_time(self.current_time_edit.text())
                frame_pos = time_pos * self.cap.get(cv2.CAP_PROP_FPS)
                self.cap.set(cv2.CAP_PROP_POS_FRAMES, frame_pos)
                
                # 读取并显示当前帧
                ret, frame = self.cap.read()
                if ret:
                    # 调整大小
                    frame = cv2.resize(
                        frame, 
                        (self.preview_width, self.preview_height),
                        interpolation=cv2.INTER_NEAREST
                    )
                    
                    # 转换颜色空间
                    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    
                    # 创建QImage
                    image = QImage(
                        rgb_frame.data,
                        self.preview_width,
                        self.preview_height,
                        rgb_frame.strides[0],
                        QImage.Format_RGB888
                    )
                    
                    self.video_label.setPixmap(QPixmap.fromImage(image))
                
                # 更新时间显示和进度条
                self._update_time_display(time_pos)
                
            except Exception as e:
                print(f"时间输入处理错误: {str(e)}")
            
    def _toggle_play(self):
        """切换播放/暂停状态"""
        if self.cap:
            self.is_playing = not self.is_playing
            self.play_pause_btn.setText("暂停" if self.is_playing else "播放")
            
    def _prev_frame(self):
        """跳转到上一帧"""
        if self.cap:
            try:
                # 获取当前帧位置
                current_frame = self.cap.get(cv2.CAP_PROP_POS_FRAMES)
                # 确保不会跳到负数帧
                if current_frame > 1:
                    # 跳转到上一帧
                    self.cap.set(cv2.CAP_PROP_POS_FRAMES, current_frame - 2)  # 减2是因为读取会自动前进一帧
                    # 读取并显示帧
                    ret, frame = self.cap.read()
                    if ret:
                        # 调整大小
                        frame = cv2.resize(
                            frame, 
                            (self.preview_width, self.preview_height),
                            interpolation=cv2.INTER_NEAREST
                        )
                        
                        # 转换颜色空间
                        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                        
                        # 创建QImage
                        image = QImage(
                            rgb_frame.data,
                            self.preview_width,
                            self.preview_height,
                            rgb_frame.strides[0],
                            QImage.Format_RGB888
                        )
                        
                        self.video_label.setPixmap(QPixmap.fromImage(image))
                        
                        # 更新时间显示
                        current_time = current_frame / self.cap.get(cv2.CAP_PROP_FPS)
                        self._update_time_display(current_time)
                        
            except Exception as e:
                print(f"跳转到上一帧时发生错误: {str(e)}")

    def _next_frame(self):
        """跳转到下一帧"""
        if self.cap:
            try:
                # 读取并显示下一帧
                ret, frame = self.cap.read()
                if ret:
                    # 调整大小
                    frame = cv2.resize(
                        frame, 
                        (self.preview_width, self.preview_height),
                        interpolation=cv2.INTER_NEAREST
                    )
                    
                    # 转换颜色空间
                    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    
                    # 创建QImage
                    image = QImage(
                        rgb_frame.data,
                        self.preview_width,
                        self.preview_height,
                        rgb_frame.strides[0],
                        QImage.Format_RGB888
                    )
                    
                    self.video_label.setPixmap(QPixmap.fromImage(image))
                    
                    # 更新时间显示
                    current_frame = self.cap.get(cv2.CAP_PROP_POS_FRAMES)
                    current_time = current_frame / self.cap.get(cv2.CAP_PROP_FPS)
                    self._update_time_display(current_time)
                    
                else:
                    # 如果到达视频末尾，回到最后一帧
                    total_frames = self.cap.get(cv2.CAP_PROP_FRAME_COUNT)
                    self.cap.set(cv2.CAP_PROP_POS_FRAMES, total_frames - 1)
                    
            except Exception as e:
                print(f"跳转到下一帧时发生错误: {str(e)}")
            
    def _mark_start(self):
        """标记开始时间点"""
        if self.cap:
            try:
                current_time = self.cap.get(cv2.CAP_PROP_POS_FRAMES) / self.cap.get(cv2.CAP_PROP_FPS)
                # 开始时间向前对齐
                self.start_time = self.video_processor.find_nearest_frame(self.cap, current_time, 'prev')
                
                # 设置按钮样式
                self.mark_start_btn.setStyleSheet(self.marked_button_style)
                
                QMessageBox.information(
                    self,
                    "标记起点",
                    f"原始时间点：{self._format_time(current_time)}\n"
                    f"对齐后时间点：{self._format_time(self.start_time)}"
                )
                
            except Exception as e:
                print(f"标记起点时发生错误: {str(e)}")

    def _mark_end(self):
        """标记结束时间点"""
        if self.cap:
            try:
                current_time = self.cap.get(cv2.CAP_PROP_POS_FRAMES) / self.cap.get(cv2.CAP_PROP_FPS)
                # 结束时间向后对齐
                self.end_time = self.video_processor.find_nearest_frame(self.cap, current_time, 'next')
                
                # 设置按钮样式
                self.mark_end_btn.setStyleSheet(self.marked_button_style)
                
                QMessageBox.information(
                    self,
                    "标记终点",
                    f"原始时间点：{self._format_time(current_time)}\n"
                    f"对齐后时间点：{self._format_time(self.end_time)}"
                )
                
            except Exception as e:
                print(f"标记终点时发生错误: {str(e)}")
            
    def _reset_marks(self):
        """重置开始和结束时间标记"""
        try:
            self.start_time = 0.0
            self.end_time = self.video_processor.duration if self.video_processor else 0.0
            
            # 重置按钮样式
            self.mark_start_btn.setStyleSheet(self.default_button_style)
            self.mark_end_btn.setStyleSheet(self.default_button_style)
            
            self._update_time_display(0.0)  # 更新时间显示
            
        except Exception as e:
            print(f"重置标记时发生错误: {str(e)}")
        
    def _export_video(self):
        """导出视频片段"""
        if not self.cap:
            return
            
        if self.start_time == 0.0 and self.end_time == self.video_processor.duration:
            reply = QMessageBox.question(
                self,
                "确认导出",
                "您未手动设置时间点，是否继续导出？",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.No:
                return
                
        # 禁用界面操作
        self.setEnabled(False)
        
        # 创建并启动剪辑线程
        output_path = self.video_processor.generate_output_filename()
        self.cut_thread = VideoCutThread(
            self.video_processor,
            self.start_time,
            self.end_time,
            output_path
        )
        self.cut_thread.finished.connect(self._on_video_cut)
        self.cut_thread.progress.connect(self._update_status)
        self.cut_thread.start()
        
    def _on_video_cut(self, success: bool, output_path: str):
        """视频剪辑完成的回调"""
        self.setEnabled(True)
        if success:
            # 重置按钮样式
            self.mark_start_btn.setStyleSheet(self.default_button_style)
            self.mark_end_btn.setStyleSheet(self.default_button_style)
            
            QMessageBox.information(
                self,
                "导出成功",
                f"已导出：{output_path}"
            )
        else:
            QMessageBox.warning(
                self,
                "导出失败",
                "视频导出失败，请检查日志"
            )
        
    def _update_status(self, message: str):
        """更新状态信息"""
        self.statusBar().showMessage(message) 