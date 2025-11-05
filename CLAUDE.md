# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

这是一个基于AI的视频文案处理工具，提供从视频中提取音频、语音识别、AI文案改写等完整功能。项目采用模块化设计，支持GPU加速和批处理操作。

## 核心架构

### 技术栈
- **Python 3.12+** + Conda环境管理
- **PyQt5** - 图形用户界面
- **PyTorch 2.4.1 + CUDA 12.4** - GPU加速
- **OpenAI Whisper** - 语音识别
- **Ollama** - 本地AI文案改写服务
- **FFmpeg** - 音频提取和处理

### 模块结构

```
src/
├── main.py              # 程序入口
├── app.py               # 简化版GUI
└── modules/
    ├── config.py        # 配置管理器（单例模式）
    ├── utils.py         # 工具函数集合
    ├── whisper_manager.py  # Whisper模型管理
    ├── audio_extractor.py  # 音频提取
    ├── ollama_client.py   # AI客户端
    └── app.py          # 完整版GUI
```

## 开发命令

### 环境设置
```bash
# Windows：自动环境安装
setup_env.bat

# 启动应用
启动.ps1（右键在PowerShell中打开，或者命令窗口拖入文件）

# 或者直接运行
python src/main.py
```

### 命令行工具

# 环境检查
python scripts/check_env.py

# 清理日志
python scripts/clear_logs.py
```

## 核心组件说明

### 配置系统 (modules/config.py)
- 单例模式，支持嵌套配置访问
- 自动创建默认配置文件
- 配置位置：`config/` 目录

### Whisper管理 (modules/whisper_manager.py)
- 自动设备选择（GPU/CPU）
- 支持模型下载和缓存
- 线程安全的取消操作
- 智能重试机制

### GUI应用 (modules/app.py)
- 多线程架构，避免界面阻塞
- 拖拽文件支持
- 实时进度显示
- 错误处理和用户反馈

## 开发注意事项

### 性能优化
- GPU显存要求：≥8GB推荐
- 智能内存管理，自动降级处理
- Whisper模型根据硬件自动选择

### 错误处理
- FFmpeg编码安全：UTF-8容错处理
- OpenMP冲突：设置环境变量解决
- 网络超时和重试机制

### 文件管理
- 临时文件：`temp/` 目录
- 输出结果：`output/` 目录
- 日志文件：`logs/` 目录
- 模型缓存：`models/whisper/`

## 配置文件

主要的配置文件位于 `config/` 目录：
- `settings.json` - 主配置
- `app.json` - 应用设置
- `user.json` - 用户偏好
- `system.json` - 系统配置

## GPU支持

项目自动检测并使用GPU加速：
- CUDA 12.4支持
- 自动设备选择
- 显存不足时自动降级到CPU