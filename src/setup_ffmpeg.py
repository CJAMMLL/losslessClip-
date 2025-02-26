import os
import sys
import zipfile
import requests
import tempfile
from pathlib import Path
from tqdm import tqdm

def download_ffmpeg():
    """下载并配置FFmpeg"""
    ffmpeg_url = "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"
    bin_dir = Path("bin")
    
    # 创建bin目录
    bin_dir.mkdir(exist_ok=True)
    
    print("正在下载FFmpeg...")
    try:
        # 使用临时文件
        with tempfile.NamedTemporaryFile(delete=False, suffix='.zip') as temp_file:
            # 下载文件并显示进度条
            response = requests.get(ffmpeg_url, stream=True, verify=True)
            response.raise_for_status()
            total_size = int(response.headers.get('content-length', 0))
            
            with tqdm(total=total_size, unit='B', unit_scale=True) as pbar:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        temp_file.write(chunk)
                        pbar.update(len(chunk))
            
            temp_file_path = temp_file.name
        
        print("下载完成，正在解压...")
        
        # 解压文件
        with zipfile.ZipFile(temp_file_path, 'r') as zip_ref:
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
        # 清理临时文件
        if os.path.exists(temp_file_path):
            os.unlink(temp_file_path)

if __name__ == "__main__":
    download_ffmpeg() 