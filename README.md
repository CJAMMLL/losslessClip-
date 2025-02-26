# losslessClip无损剪辑

一款简单易用的视频无损剪辑软件，支持多种视频格式，操作简单直观。

## 重要说明：FFmpeg 安装

本软件依赖 FFmpeg 进行视频处理，首次使用前请按以下步骤安装：

1. 下载 FFmpeg：
   - 访问 [Gyan's FFmpeg Builds](https://www.gyan.dev/ffmpeg/builds/)
   - 下载 `ffmpeg-release-full.7z`
   - 使用 7-Zip 等工具解压下载的文件

2. 安装 FFmpeg：
   - 在程序根目录下创建 `bin` 文件夹（如果不存在）
   - 从解压的文件夹中找到 `ffmpeg.exe` 和 `ffprobe.exe`
   - 将这两个文件复制到程序的 `bin` 文件夹中
   - 最终目录结构应该是：
     ```
     losslessClip无损剪辑/
     ├── bin/
     │   ├── ffmpeg.exe
     │   └── ffprobe.exe
     ├── src/
     ├── assets/
     └── 其他文件...
     ```

## 功能特点

- 无损剪辑：保持原视频的所有质量参数
- 快速导出：使用FFmpeg进行视频处理，速度快
- 精确定位：支持逐帧预览，可以精确定位剪辑点
- 多格式支持：支持mp4、flv、mov、avi等主流视频格式
- 简单易用：拖拽即可导入视频，界面直观

## 使用方法

详细的使用说明请参考 [使用说明.txt](使用说明.txt)

## 快捷键

- 空格键：播放/暂停
- 左右方向键：快进/快退3秒
- Shift+左右方向键：快进/快退0.5秒
- Shift+Ctrl+左右方向键：逐帧移动

## 开发环境

- Python 3.8+
- PyQt5
- OpenCV-Python
- FFmpeg

## 开发说明

1. 克隆仓库：
```bash
git clone https://github.com/CJAMMLL/losslessClip-.git
```

2. 安装依赖：
```bash
pip install -r requirements.txt
```

3. 下载并安装 FFmpeg（必需）：
   - 访问 [Gyan's FFmpeg Builds](https://www.gyan.dev/ffmpeg/builds/)
   - 下载 `ffmpeg-release-full.7z`
   - 解压后将 `ffmpeg.exe` 和 `ffprobe.exe` 放入 `bin` 文件夹

4. 运行程序：
```bash
python src/main.py
```

## 打包说明

使用 PyInstaller 打包：
```bash
python src/build.py
```

## 注意事项

1. 首次运行前必须安装 FFmpeg（见上方说明）
2. 首次运行可能需要管理员权限
3. 建议在剪辑重要视频前先进行备份
4. 如果程序报错找不到 FFmpeg，请检查 bin 目录下是否有 ffmpeg.exe 和 ffprobe.exe

## 常见问题

Q: 程序报错"找不到 FFmpeg"怎么办？
A: 请确保已经按照上方"FFmpeg 安装"部分的说明正确安装了 FFmpeg。

Q: FFmpeg 文件放错位置怎么办？
A: 请确保 ffmpeg.exe 和 ffprobe.exe 都放在程序目录下的 bin 文件夹中，不要放在其他位置。

## 版权信息

Copyright © 2024 losslessClip团队
版本：v1.1 