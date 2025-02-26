import PyInstaller.__main__
import os
from pathlib import Path

def build_exe():
    """打包程序为exe文件"""
    # 项目根目录
    root_dir = Path(__file__).parent.parent
    
    # 确保 bin 目录中有 FFmpeg 文件
    bin_dir = root_dir / "bin"
    if not (bin_dir / "ffmpeg.exe").exists() or not (bin_dir / "ffprobe.exe").exists():
        raise FileNotFoundError("FFmpeg 文件不存在，请确保 bin 目录下有 ffmpeg.exe 和 ffprobe.exe")
    
    # 确保图标文件存在
    icon_path = root_dir / "assets" / "teamG.ico"
    if not icon_path.exists():
        raise FileNotFoundError(f"图标文件不存在: {icon_path}")

    # PyInstaller 参数
    params = [
        'src/main.py',                          # 主程序文件
        '--name=losslessClip无损剪辑v1.1',      # 生成的 exe 文件名
        '--windowed',                           # 不显示命令行窗口
        '--onefile',                            # 打包成单个文件
        '--clean',                              # 清理临时文件
        '--noconfirm',                          # 覆盖现有文件
        f'--add-data=bin/ffmpeg.exe;bin',      # 添加 FFmpeg
        f'--add-data=bin/ffprobe.exe;bin',     # 添加 FFprobe
        f'--add-data=assets/teamG.ico;assets', # 添加图标文件到资源
        '--uac-admin',                          # 请求管理员权限
        '--version-file=version_info.txt',      # 版本信息文件
        '--icon=assets/teamG.ico',              # 设置程序图标
    ]

    # 执行打包
    PyInstaller.__main__.run(params)

if __name__ == "__main__":
    build_exe() 