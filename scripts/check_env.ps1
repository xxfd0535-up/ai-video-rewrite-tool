<#
.SYNOPSIS
    视频文案AI爆款改写工具 - 环境检测脚本
.DESCRIPTION
    全面检测系统环境、依赖和配置状态
.NOTES
    File Name      : check_env.ps1
    Prerequisite   : PowerShell 5.1+
    Copyright 2024 - Video Rewrite Tool
#>

# 设置控制台编码为UTF-8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

# 颜色定义
$colors = @{
    'Success'    = 'Green'
    'Error'      = 'Red'
    'Warning'    = 'Yellow'
    'Info'       = 'Cyan'
    'Highlight'  = 'Magenta'
    'Diagnostic' = 'White'
}

function Write-ColorOutput {
    param([string]$Message, [string]$Color = 'White')
    Write-Host $Message -ForegroundColor $Color
}

function Write-Section {
    param([string]$Title)
    Write-ColorOutput ""
    Write-ColorOutput "=== $Title ===" 'Cyan'
    Write-ColorOutput ""
}

function Write-Result {
    param(
        [string]$Test,
        [bool]$Passed,
        [string]$Details = "",
        [string]$Recommendation = ""
    )

    $status = if ($Passed) { "✅" } else { "❌" }
    $color = if ($Passed) { "Success" } else { "Error" }

    Write-ColorOutput "   $status $Test" $color

    if ($Details) {
        Write-ColorOutput "      详情: $Details" 'Info'
    }

    if ($Recommendation) {
        Write-ColorOutput "      建议: $Recommendation" 'Highlight'
    }

    Write-ColorOutput ""
}

function Test-PythonInstallation {
    Write-Section "Python环境检测"

    # Python版本检查（要求严格为 3.12）
    try {
        $pythonVersion = python --version 2>&1
        if ($pythonVersion -match "Python 3\.12") {
            Write-Result "Python版本" $true $pythonVersion
        } else {
            Write-Result "Python版本" $false $pythonVersion "需要Python 3.12，当前版本不符合要求"
        }
    }
    catch {
        Write-Result "Python安装" $false "Python未安装或不在PATH中" "请安装Python 3.12: https://www.python.org/downloads/"
    }

    # Pip检查
    try {
        $pipVersion = pip --version 2>&1
        Write-Result "Pip包管理器" $true $pipVersion
    }
    catch {
        Write-Result "Pip包管理器" $false "Pip未安装或不在PATH中" "请重新安装Python或手动添加pip到PATH"
    }
}

function Test-CondaEnvironment {
    Write-Section "Conda环境检测"

    # Conda检查
    try {
        $condaVersion = conda --version 2>&1
        Write-Result "Conda安装" $true $condaVersion
    }
    catch {
        Write-Result "Conda安装" $false "Conda未安装或不在PATH中" "请安装Miniconda: https://docs.conda.io/en/latest/miniconda.html"
        return
    }

    # 环境文件检查
    $envFile = "environment.yml"
    if (Test-Path $envFile) {
        $envContent = Get-Content $envFile -Raw -Encoding UTF8
        Write-Result "环境配置文件" $true "environment.yml存在"
    } else {
        Write-Result "环境配置文件" $false "environment.yml不存在" "请确保环境配置文件存在"
    }

    # 环境检查（要求 video_rewrite_env_py312）
    try {
        $envList = conda env list
        $videoEnvExists = $envList | Select-String -Pattern "video_rewrite_env_py312\s"
        if ($videoEnvExists) {
            Write-Result "项目环境" $true "video_rewrite_env_py312 环境已创建"
        } else {
            Write-Result "项目环境" $false "video_rewrite_env_py312 环境不存在" "创建命令: conda create -n video_rewrite_env_py312 python=3.12 -y"
        }
    }
    catch {
        Write-Result "环境列表" $false "无法获取Conda环境列表" "请检查Conda安装"
    }
}

function Test-PythonPackages {
    Write-Section "Python包依赖检测"

    $packages = @(
        @{ Name = "PyQt5"; Command = "import PyQt5"; Description = "图形界面库" },
        @{ Name = "whisper"; Command = "import whisper"; Description = "语音识别库" },
        @{ Name = "torch"; Command = "import torch"; Description = "深度学习框架" },
        @{ Name = "requests"; Command = "import requests"; Description = "HTTP请求库" },
        @{ Name = "ffmpeg-python"; Command = "import ffmpeg"; Description = "FFmpeg Python绑定" },
        @{ Name = "soundfile"; Command = "import soundfile"; Description = "音频文件处理" },
        @{ Name = "cv2"; Command = "import cv2"; Description = "OpenCV计算机视觉" },
        @{ Name = "psutil"; Command = "import psutil"; Description = "系统监控库" },
        @{ Name = "numpy"; Command = "import numpy"; Description = "数值计算库" },
        @{ Name = "PyYAML"; Command = "import yaml"; Description = "YAML解析库" }
    )

    foreach ($pkg in $packages) {
        try {
            $result = python -c "$($pkg.Command); print('OK')" 2>&1
            if ($result -eq "OK") {
                Write-Result "$($pkg.Name)" $true "$($pkg.Description) 已安装"
            } else {
                Write-Result "$($pkg.Name)" $false "$($pkg.Description) 未安装" "pip install $($pkg.Name.ToLower())"
            }
        }
        catch {
            Write-Result "$($pkg.Name)" $false "$($pkg.Description) 安装检查失败" "pip install $($pkg.Name.ToLower())"
        }
    }
}

function Test-PyTorchGPU {
    Write-Section "PyTorch GPU检测"

    try {
        $torchTest = python -c @"
import torch
print(f'CUDA可用: {torch.cuda.is_available()}')
if torch.cuda.is_available():
    print(f'GPU设备数: {torch.cuda.device_count()}')
    print(f'当前GPU: {torch.cuda.get_device_name(0)}')
    print(f'CUDA版本: {torch.version.cuda}')
    print(f'GPU显存: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.1f}GB')
else:
    print('使用CPU模式')
"@

        $torchLines = $torchTest -split "`n"
        foreach ($line in $torchLines) {
            if ($line.Trim()) {
                Write-ColorOutput "   $line" 'Info'
            }
        }
        Write-ColorOutput "" 'Diagnostic'
    }
    catch {
        Write-Result "PyTorch GPU检测" $false "检测失败" "请检查PyTorch和CUDA安装"
    }
}

function Test-ExternalServices {
    Write-Section "外部服务检测"

    # Ollama服务检查
    try {
        $response = Invoke-RestMethod -Uri "http://localhost:11434" -Method GET -TimeoutSec 5 -ErrorAction Stop
        Write-Result "Ollama服务" $true "Ollama服务正在运行"

        # 获取模型列表
        try {
            $models = Invoke-RestMethod -Uri "http://localhost:11434/api/tags" -Method GET -TimeoutSec 5
            $modelCount = $models.models.Count
            Write-Result "Ollama模型" $true "已安装 $modelCount 个模型"

            if ($modelCount -gt 0) {
                Write-ColorOutput "   可用模型:" 'Info'
                foreach ($model in $models.models) {
                    Write-ColorOutput "     $($model.name)" 'Info'
                }
                Write-ColorOutput "" 'Diagnostic'
            }
        }
        catch {
            Write-Result "模型列表" $false "无法获取Ollama模型列表" "请检查Ollama配置"
        }
    }
    catch {
        Write-Result "Ollama服务" $false "Ollama服务未运行" "请运行: ollama serve"
    }

    # FFmpeg检查
    try {
        $ffmpegVersion = ffmpeg -version 2>&1 | Select-Object -First 1
        Write-Result "FFmpeg" $true $ffmpegVersion
    }
    catch {
        Write-Result "FFmpeg" $false "FFmpeg未安装或不在PATH中" "请安装FFmpeg并添加到PATH"
    }
}

function Test-SystemResources {
    Write-Section "系统资源检测"

    # 内存信息
    try {
        $memory = Get-CimInstance -ClassName Win32_OperatingSystem
        $totalMemoryGB = [math]::Round($memory.TotalVisibleMemorySize / 1MB, 2)
        $freeMemoryGB = [math]::Round($memory.FreePhysicalMemory / 1MB, 2)
        $usedMemoryGB = $totalMemoryGB - $freeMemoryGB
        $usagePercent = [math]::Round(($usedMemoryGB / $totalMemoryGB) * 100, 1)

        Write-ColorOutput "   内存信息:" 'Info'
        Write-ColorOutput "     总内存: $totalMemoryGB GB" 'Info'
        Write-ColorOutput "     已用内存: $usedMemoryGB GB ($usagePercent%)" 'Info'
        Write-ColorOutput "     可用内存: $freeMemoryGB GB" 'Info'

        if ($totalMemoryGB -lt 8) {
            Write-ColorOutput "   ⚠️ 内存不足8GB，可能影响性能" 'Warning'
        }
        Write-ColorOutput "" 'Diagnostic'
    }
    catch {
        Write-Result "内存信息" $false "无法获取内存信息"
    }

    # CPU信息
    try {
        $cpu = Get-CimInstance -ClassName Win32_Processor
        $cores = $cpu.NumberOfCores
        $name = $cpu.Name
        Write-ColorOutput "   CPU信息:" 'Info'
        Write-ColorOutput "     型号: $name" 'Info'
        Write-ColorOutput "     物理核心数: $cores" 'Info'
        Write-ColorOutput "" 'Diagnostic'
    }
    catch {
        Write-Result "CPU信息" $false "无法获取CPU信息"
    }
}

# 脚本入口
Write-Section "环境检测开始"
Test-PythonInstallation
Test-CondaEnvironment
Test-PythonPackages
Test-PyTorchGPU
Test-ExternalServices
Test-SystemResources
Write-Section "环境检测结束"