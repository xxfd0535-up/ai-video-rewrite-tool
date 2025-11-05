# 🎬 视频文案AI爆款改写工具

一个集成了本地语音识别和AI文案改写的智能工具，专门用于本地短视频文案的提取与二次创作。可免费使用！

## ✨ 主要特性

- 🎬 **智能视频处理** - 支持多种视频格式，自动提取音频
- 🎤 **本地语音识别** - 使用Whisper进行高精度语音转文字
- 🦙 **AI文案改写** - 集成Ollama本地大模型进行智能文案创作
- ⚡ **高效处理** - 支持GPU加速，自动重试机制
- 📁 **拖拽操作** - 支持文件拖拽，操作简单直观
- 💾 **自动保存** - 处理结果自动保存，支持多种格式输出

## 🚀 快速开始

### 环境要求

- **Python**: >= 3.12
- **操作系统**: Windows 10/11
- **内存**: 推荐8GB以上
- **存储**: 至少2GB可用空间

### 安装步骤

1. **克隆项目**
   ```bash
   git clone <项目地址>
   cd 视频文案AI爆款改写整合包
   ```

2. **安装依赖**
   ```bash
   pip install -r requirements.txt
   ```

3. **启动Ollama服务**
   ```bash
   # 下载并启动Ollama
   # 下载地址: https://ollama.com/
   # 启动后拉取模型
   ollama pull deepseek-r1:8b
   ```

4. **运行程序**
   ```bash
   python src/main.py
   ```

## 📖 使用指南

### 基本操作

1. **选择视频文件**
   - 点击"📁 选择视频文件"按钮
   - 或直接拖拽视频文件到窗口

2. **开始处理**
   - 点击"🎬 开始处理"按钮
   - 系统将自动进行：音频提取 → 语音识别 → AI改写

3. **查看结果**
   - 左侧显示原始文案
   - 右侧显示AI改写文案
   - 可复制或保存结果

### 支持的视频格式

- `.mp4`, `.mov`, `.mkv`, `.avi`
- `.flv`, `.wmv`, `.webm`, `.ts`

### 文件限制

- **最大文件大小**: 500MB
- **最长时长**: 60分钟
- **推荐时长**: 1-10分钟（效果最佳）

## ⚙️ 配置说明

### 主要配置文件: `config/settings.json`

```json
{
  "whisper": {
    "model": "medium",        // 识别模型: tiny/base/small/medium/large
    "language": "zh",         // 识别语言
    "device": "cpu",          // 使用设备: cpu/cuda/auto
    "temperature": 0.2,       // 识别温度
    "timeout": 600,           // 超时时间(秒)
    "max_retries": 2,         // 最大重试次数
    "retry_delay": 3           // 重试间隔(秒)
  },
  "ollama": {
    "enabled": true,
    "url": "http://127.0.0.1:11434/api/generate",
    "model": "deepseek-r1:8b", // AI模型
    "timeout": 600,
    "max_retries": 3,
    "retry_delay": 2,
    "stream": false
  },
  "ui": {
    "output_dir": "output",     // 输出目录
    "auto_save_output": true    // 自动保存
  }
}
```

### 目录结构

```
项目根目录/
├── output/          # 最终文案输出
├── temp/           # 临时音频文件(自动清理)
├── logs/           # 系统日志
├── config/         # 配置文件
└── models/whisper/ # Whisper模型文件
```

## 🔧 故障排除

### 常见问题

1. **程序无法启动**
   - 检查Python版本是否>=3.12
   - 确认所有依赖已正确安装
   - 检查PyQt5是否正常安装

2. **Ollama连接失败**
   - 确认Ollama服务正在运行
   - 检查端口11434是否被占用
   - 验证模型是否已下载: `ollama list`

3. **语音识别超时**
   - 对于长视频，可增加timeout值
   - 尝试使用更小的Whisper模型
   - 确保系统内存充足

4. **AI改写失败**
   - 检查Ollama模型是否正确加载
   - 确认网络连接正常
   - 尝试重启Ollama服务

### 性能优化

1. **GPU加速**
   ```json
   "whisper": {
     "device": "cuda"  // 使用GPU加速
   }
   ```

2. **处理速度**
   - 使用small模型提升速度
   - 关闭其他占用内存的程序
   - 确保SSD有足够空间

## 📝 更新日志

### v1.0.0 (2024-11-04)
- ✅ 初始版本发布
- ✅ 集成Whisper语音识别
- ✅ 集成Ollama AI改写
- ✅ 图形界面完整实现
- ✅ 自动保存功能
- ✅ 重试机制优化
- ✅ 中文编码支持

## 🤝 贡献指南

欢迎提交Issue和Pull Request来改进项目！

## 📄 许可证

本项目采用MIT许可证 - 详见 [LICENSE](LICENSE) 文件

## 💡 技术支持

如遇到问题，请检查：
1. 本README文档的故障排除部分
2. `logs/` 目录下的日志文件
3. 确认所有依赖和服务正常运行

---

**让AI助您创作更精彩的短视频文案！** 🚀