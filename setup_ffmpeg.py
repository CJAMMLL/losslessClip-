import os
import sys
import zipfile
import requests
from pathlib import Path

def download_ffmpeg():
    """
    下载并配置FFmpeg
    """
    # FFmpeg下载地址
    ffmpeg_url = "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"
    bin_dir = Path("bin")
    zip_path = bin_dir / "ffmpeg.zip"

    # 创建bin目录
    bin_dir.mkdir(exist_ok=True)

    print("正在下载FFmpeg...")
    try:
        # 下载FFmpeg
        response = requests.get(ffmpeg_url, stream=True)
        response.raise_for_status()
        
        # 保存zip文件
        with open(zip_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

        print("下载完成，正在解压...")
        
        # 解压文件
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            for file in zip_ref.namelist():
                if file.endswith(('ffmpeg.exe', 'ffprobe.exe')):
                    zip_ref.extract(file, bin_dir)
                    # 移动文件到bin目录根目录
                    src = bin_dir / file
                    dst = bin_dir / Path(file).name
                    if src != dst:
                        os.rename(src, dst)

        print("FFmpeg配置完成！")

    except Exception as e:
        print(f"错误：{str(e)}")
        sys.exit(1)
    finally:
        # 清理zip文件
        if zip_path.exists():
            zip_path.unlink()

if __name__ == "__main__":
    download_ffmpeg() 