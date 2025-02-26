# 视频处理器错误处理案例

## 问题描述
在使用 FFprobe 解析视频关键帧时遇到的错误：
```bash
加载视频失败: not enough values to unpack (expected 2, got 1)
```

## 问题代码
```python
# 原始代码 (video_processor.py)
for line in result.stdout.splitlines():
    pts_time, key_frame = line.split(',')  # 这里直接解包可能导致错误
    if key_frame == '1':
        self.keyframes.append(float(pts_time))
```

## 解决方案
```python
# 改进后的代码 (video_processor.py)
for line in result.stdout.splitlines():
    if line.strip():  # 1. 检查空行
        try:
            parts = line.split(',')  # 2. 安全分割
            if len(parts) >= 2 and parts[1].strip() == '1':  # 3. 格式验证
                pts_time = float(parts[0])  # 4. 安全转换
                self.keyframes.append(pts_time)
        except (ValueError, IndexError) as e:  # 5. 错误处理
            print(f"解析关键帧时间出错: {str(e)}, 行: {line}")
            continue
```

## 改进要点
1. 添加空行检查
2. 使用 try-except 处理异常
3. 增加数据格式验证
4. 添加错误日志
5. 使用 continue 跳过错误行

## 经验总结
在处理外部命令输出时：
- 不要假设数据格式总是完美的
- 添加必要的数据验证
- 做好异常处理
- 保留错误日志以便调试 