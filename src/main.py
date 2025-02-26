import sys
import os
import logging
import ctypes
from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QIcon
from main_window import MainWindow

# Windows任务栏图标设置
if sys.platform == 'win32':
    # 设置程序ID
    myappid = 'teamg.videocutter.1.1'
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
    
    # 设置任务栏图标
    if hasattr(sys, '_MEIPASS'):
        # PyInstaller 打包后的路径
        icon_path = os.path.join(sys._MEIPASS, 'assets', 'teamG.ico')
    else:
        # 开发环境路径
        icon_path = os.path.join(os.path.dirname(__file__), '..', 'assets', 'teamG.ico')

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('debug.log'),
        logging.StreamHandler()
    ]
)

print("程序开始运行...")

def main():
    """程序入口函数"""
    print("进入 main 函数...")
    app = QApplication(sys.argv)
    
    # 设置应用程序图标
    if hasattr(sys, '_MEIPASS'):
        # PyInstaller 打包后的路径
        icon_path = os.path.join(sys._MEIPASS, 'assets', 'teamG.ico')
    else:
        # 开发环境路径
        icon_path = os.path.join(os.path.dirname(__file__), '..', 'assets', 'teamG.ico')
    
    if os.path.exists(icon_path):
        app_icon = QIcon(icon_path)
        app.setWindowIcon(app_icon)
        print(f"图标路径存在: {icon_path}")
    else:
        print(f"图标路径不存在: {icon_path}")
    
    # 确保图标设置成功
    if not app.windowIcon().isNull():
        print("图标设置成功")
    else:
        print("图标设置失败")
    
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main() 