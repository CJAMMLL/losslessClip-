import os
import re
import subprocess
import sys
import json
from pathlib import Path
from typing import Tuple, List, Optional
import cv2

class VideoProcessor:
    """视频处理核心类，负责视频信息获取和剪辑操作"""
    
    def __init__(self):
        """初始化视频处理器"""
        # 获取程序运行路径
        if getattr(sys, 'frozen', False):
            # 打包后的路径
            base_path = Path(sys._MEIPASS)
        else:
            # 开发环境路径
            base_path = Path(__file__).parent.parent
            
        # 设置 FFmpeg 路径
        self.ffmpeg_path = str(base_path / "bin" / "ffmpeg.exe")
        self.ffprobe_path = str(base_path / "bin" / "ffprobe.exe")
        
        # 添加这些行来隐藏命令行窗口
        self.startupinfo = subprocess.STARTUPINFO()
        self.startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        self.startupinfo.wShowWindow = subprocess.SW_HIDE
        self.current_file = None
        self.duration = 0.0

    def load_video(self, file_path: str) -> bool:
        """加载视频文件并获取基本信息"""
        try:
            # 检查文件是否存在
            if not os.path.exists(file_path):
                print(f"文件不存在: {file_path}")
                return False
            
            # 获取视频基本信息
            cmd = [
                self.ffprobe_path,
                "-v", "error",
                "-select_streams", "v:0",
                "-show_entries", "stream=width,height,duration",
                "-of", "json",
                file_path
            ]
            
            result = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True,
                startupinfo=self.startupinfo
            )
            
            if result.returncode != 0:
                print(f"获取视频信息失败: {result.stderr}")
                return False
            
            # 解析视频信息
            info = json.loads(result.stdout)
            stream = info.get('streams', [{}])[0]
            
            # 存储视频信息
            self.width = int(stream.get('width', 0))
            self.height = int(stream.get('height', 0))
            self.current_file = file_path
            
            # 获取视频时长
            cmd = [
                self.ffprobe_path,
                "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                file_path
            ]
            result = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True,
                startupinfo=self.startupinfo
            )
            if result.returncode != 0:
                print(f"获取视频时长失败: {result.stderr}")
                return False
                
            self.duration = float(result.stdout.strip())
            return True
            
        except Exception as e:
            print(f"加载视频失败: {str(e)}")
            return False

    def find_nearest_frame(self, cap: cv2.VideoCapture, current_time: float, align_mode: str = 'prev') -> float:
        """
        计算最近的帧时间点
        
        Args:
            cap: OpenCV视频捕获对象
            current_time: 当前时间点（秒）
            align_mode: 对齐模式，'prev' 向前对齐，'next' 向后对齐
            
        Returns:
            float: 对齐后的时间点
        """
        fps = cap.get(cv2.CAP_PROP_FPS)
        frame_duration = 1.0 / fps  # 每帧的持续时间
        
        # 计算当前帧号
        current_frame = int(current_time * fps)
        
        if align_mode == 'prev':
            # 向前对齐（用于开始时间点）
            aligned_time = current_frame * frame_duration
        else:
            # 向后对齐（用于结束时间点）
            aligned_time = (current_frame + 1) * frame_duration
        
        # 确保不会超出视频范围
        if aligned_time < 0:
            aligned_time = 0
        if aligned_time > self.duration:
            aligned_time = self.duration
            
        return aligned_time

    def cut_video(self, start_time: float, end_time: float, output_path: str) -> bool:
        """
        执行视频剪辑
        
        Args:
            start_time: 起始时间（秒）
            end_time: 结束时间（秒）
            output_path: 输出文件路径
            
        Returns:
            bool: 是否成功剪辑
        """
        if not self.current_file:
            return False
            
        try:
            cmd = [
                self.ffmpeg_path,
                "-ss", str(start_time),
                "-i", self.current_file,
                "-t", str(end_time - start_time),
                "-c", "copy",
                "-y",  # 覆盖已存在的文件
                output_path
            ]
            
            result = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True,
                startupinfo=self.startupinfo
            )
            return result.returncode == 0
            
        except Exception as e:
            print(f"剪辑失败: {str(e)}")
            return False

    def generate_output_filename(self) -> str:
        """
        生成输出文件名（自动递增序号）
        
        Returns:
            str: 生成的文件路径
        """
        if not self.current_file:
            return ""
            
        source_path = Path(self.current_file)
        base_name = source_path.stem
        target_dir = source_path.parent
        prefix = f"{base_name}_cut_"
        pattern = re.compile(rf"^{prefix}(\d+)\.mp4$")
        
        max_num = 0
        for file in os.listdir(target_dir):
            match = pattern.match(file)
            if match:
                current_num = int(match.group(1))
                max_num = max(max_num, current_num)
                
        return str(target_dir / f"{prefix}{max_num + 1}.mp4") 