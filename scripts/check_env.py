# -*- coding: utf-8 -*-
"""
环境预检脚本 check_env.py

用途:
- 在运行应用或测试前，对本机 Python 运行环境、关键第三方依赖、系统组件与外部服务进行自检。
- 输出人类可读结果，并生成 JSON 报告文件，便于问题定位与学习。

执行方式:
- 命令行运行: `python scripts/check_env.py`
- 可选参数: `--ollama-url http://localhost:11434` 指定 Ollama 服务地址

作者注释规范: 所有方法均附中文文档注释，包含参数、返回值、可能的异常说明。
"""

# 尽早设置以避免 OpenMP 运行时冲突（libiomp5md.dll 重复加载）
import os
os.environ['KMP_DUPLICATE_LIB_OK'] = 'TRUE'

import sys
import json
import time
import socket
import argparse
import platform
import subprocess
from datetime import datetime
from typing import Dict, Any, Tuple, Optional


def check_python_version(required_version: Tuple[int, int] = (3, 12)) -> Dict[str, Any]:
    """检查 Python 版本是否满足要求（严格要求主次版本相等）。

    参数:
    - required_version: 必须匹配的主次版本元组，例如 (3, 12)。

    返回值:
    - 字典对象，包含: ok(bool), current(str), required(str)

    可能抛出的异常:
    - 一般不抛出异常；内部已做保护。
    """
    current = sys.version_info
    ok = (current.major, current.minor) == required_version
    return {
        "ok": ok,
        "current": f"{current.major}.{current.minor}.{current.micro}",
        "required": f"{required_version[0]}.{required_version[1]}"
    }


def check_package(pkg_name: str, import_name: Optional[str] = None, min_version: Optional[str] = None) -> Dict[str, Any]:
    """检测第三方包是否已安装且版本满足要求。

    参数:
    - pkg_name: 包名(用于展示)，例如 "pydub"。
    - import_name: 实际导入名，默认与包名一致，某些包可能不同，例如 "PyQt5"。
    - min_version: 最低版本要求字符串，例如 "1.0.0"；可为空。

    返回值:
    - 字典对象，包含: installed(bool), version(str或None), meets_version(bool或None), error(str或None)

    可能抛出的异常:
    - 不直接向外抛出；错误信息写入返回值的 error 字段。
    """
    import importlib
    name = import_name or pkg_name
    try:
        module = importlib.import_module(name)
        version = getattr(module, "__version__", None)
        meets = None
        if min_version and version:
            from packaging.version import Version
            meets = Version(version) >= Version(min_version)
        return {"installed": True, "version": version, "meets_version": meets, "error": None}
    except Exception as e:
        return {"installed": False, "version": None, "meets_version": None, "error": str(e)}


def check_ffmpeg() -> Dict[str, Any]:
    """检测系统是否可用 ffmpeg(音视频处理必要组件)。

    参数:
    - 无。

    返回值:
    - 字典对象，包含: available(bool), version(str或None), error(str或None)

    可能抛出的异常:
    - 不直接抛出；失败信息写入 error 字段。
    """
    try:
        proc = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True, timeout=5)
        if proc.returncode == 0:
            first_line = proc.stdout.splitlines()[0] if proc.stdout else ""
            return {"available": True, "version": first_line, "error": None}
        return {"available": False, "version": None, "error": proc.stderr.strip()}
    except Exception as e:
        return {"available": False, "version": None, "error": str(e)}


def check_whisper_gpu() -> Dict[str, Any]:
    """检测 Whisper/Torch GPU 可用性(加速识别)。

    参数:
    - 无。

    返回值:
    - 字典对象，包含: torch_installed(bool), cuda_available(bool或None), error(str或None)

    可能抛出的异常:
    - 不直接抛出；错误信息写入 error 字段。
    """
    try:
        import torch  # noqa: F401
        cuda = None
        try:
            import torch
            cuda = torch.cuda.is_available()
        except Exception:
            cuda = None
        return {"torch_installed": True, "cuda_available": cuda, "error": None}
    except Exception as e:
        return {"torch_installed": False, "cuda_available": None, "error": str(e)}


def check_ollama_server(url: str = "http://localhost:11434", timeout: float = 3.0) -> Dict[str, Any]:
    """检测 Ollama 服务是否联通。

    参数:
    - url: Ollama 服务根地址，例如 "http://localhost:11434"。
    - timeout: 请求超时时间(秒)。

    返回值:
    - 字典对象，包含: reachable(bool), status_code(int或None), error(str或None)

    可能抛出的异常:
    - 不直接抛出；错误信息写入 error 字段。
    """
    # 采用 requests(若可用) 优先，否则回退到 socket 简测
    try:
        import requests
        try:
            resp = requests.get(url + "/api/tags", timeout=timeout)
            return {"reachable": True, "status_code": resp.status_code, "error": None}
        except Exception as e:
            return {"reachable": False, "status_code": None, "error": str(e)}
    except Exception:
        # requests 不可用时，尝试 socket 连接主机端口
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            host = parsed.hostname
            port = parsed.port or 80
            sock = socket.socket()
            sock.settimeout(timeout)
            sock.connect((host, port))
            sock.close()
            return {"reachable": True, "status_code": None, "error": None}
        except Exception as e:
            return {"reachable": False, "status_code": None, "error": str(e)}


def check_pyqt5() -> Dict[str, Any]:
    """检查 PyQt5 是否可用(用于 GUI)。

    参数:
    - 无。

    返回值:
    - 字典对象，包含: installed(bool), error(str或None)

    可能抛出的异常:
    - 不直接抛出；错误写入 error 字段。
    """
    try:
        import PyQt5.QtWidgets  # noqa: F401
        return {"installed": True, "error": None}
    except Exception as e:
        return {"installed": False, "error": str(e)}


def check_pydub_and_backend() -> Dict[str, Any]:
    """检查 pydub 以及其后端(ffmpeg)可用性。

    参数:
    - 无。

    返回值:
    - 字典对象，包含: pydub_installed(bool), ffmpeg_available(bool), error(str或None)

    可能抛出的异常:
    - 不直接抛出；错误写入 error 字段。
    """
    pydub = check_package("pydub")
    ffm = check_ffmpeg()
    return {
        "pydub_installed": pydub.get("installed", False),
        "ffmpeg_available": ffm.get("available", False),
        "error": pydub.get("error") or ffm.get("error")
    }


def discover_ollama_url_from_config() -> Optional[str]:
    """尝试从项目配置中发现 Ollama 服务地址。

    参数:
    - 无。

    返回值:
    - 若成功读取到配置返回字符串 URL，否则返回 None。

    可能抛出的异常:
    - 不直接抛出；读取失败返回 None。
    """
    try:
        # 优先尝试增强配置管理器
        from src.modules.enhanced_config import get_config_manager
        manager = get_config_manager()
        cfg = manager.get_ollama_config()
        if cfg and getattr(cfg, "url", None):
            return cfg.url
    except Exception:
        pass
    try:
        # 回退尝试旧配置接口
        from src.modules.config import get_config
        CONFIG = get_config()  # 可能是单例或管理对象
        url = None
        try:
            # 假设 CONFIG.get('ollama.url') 可用
            url = CONFIG.get("ollama.url")
        except Exception:
            # 或者属性式访问
            url = getattr(CONFIG, "ollama", {}).get("url") if hasattr(CONFIG, "ollama") else None
        return url
    except Exception:
        return None


def gather_env_info(ollama_url: Optional[str]) -> Dict[str, Any]:
    """汇总环境信息与各项检查结果。

    参数:
    - ollama_url: 外部传入的 Ollama 服务地址；为 None 时自动探测或使用默认。

    返回值:
    - 字典对象，包含系统信息、依赖检查、服务联通等多项内容。

    可能抛出的异常:
    - 不直接抛出；各子检查内部自处理。
    """
    sys_info = {
        "platform": platform.platform(),
        "python": platform.python_version(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "cwd": os.getcwd()
    }

    ollama_url_final = ollama_url or discover_ollama_url_from_config() or "http://localhost:11434"

    result = {
        "timestamp": datetime.now().isoformat(),
        "system": sys_info,
        "checks": {
            "python_version": check_python_version(),
            "pyqt5": check_pyqt5(),
            "pydub_backend": check_pydub_and_backend(),
            "whisper_pkg": check_package("whisper"),
            "torch_gpu": check_whisper_gpu(),
            "ollama_server": check_ollama_server(ollama_url_final)
        },
        "config": {
            "ollama_url": ollama_url_final
        }
    }
    return result


def print_human_readable(report: Dict[str, Any]) -> None:
    """以人类可读形式打印检测结果概要。

    参数:
    - report: `gather_env_info` 返回的报告字典。

    返回值:
    - 无。

    可能抛出的异常:
    - 打印过程一般不抛出异常。
    """
    print("== 环境预检结果 ==")
    print(f"时间: {report['timestamp']}")
    print(f"平台: {report['system']['platform']}")
    print(f"Python: {report['system']['python']}")
    print(f"工作目录: {report['system']['cwd']}")
    print("")
    checks = report["checks"]
    def ok_str(x: bool) -> str:
        return "✅ 通过" if x else "❌ 未通过"

    py_ok = checks["python_version"]["ok"]
    print(f"Python版本检查: {ok_str(py_ok)} (当前 {checks['python_version']['current']}, 要求 {checks['python_version']['required']})")

    print(f"PyQt5: {'已安装' if checks['pyqt5']['installed'] else '未安装'}")

    print(f"pydub: {'已安装' if checks['pydub_backend']['pydub_installed'] else '未安装'} | ffmpeg: {'可用' if checks['pydub_backend']['ffmpeg_available'] else '不可用'}")

    whisper_installed = checks['whisper_pkg']['installed']
    print(f"whisper: {'已安装' if whisper_installed else '未安装'}")

    torch_gpu = checks['torch_gpu']
    print(f"torch: {'已安装' if torch_gpu['torch_installed'] else '未安装'} | CUDA: {'可用' if torch_gpu['cuda_available'] else '不可用或未知'}")

    ollama = checks['ollama_server']
    print(f"Ollama服务({report['config']['ollama_url']}): {'可达' if ollama['reachable'] else '不可达'}")
    if ollama['error']:
        print(f"  说明: {ollama['error']}")


def save_json_report(report: Dict[str, Any]) -> str:
    """保存 JSON 报告到日志目录。

    参数:
    - report: 预检报告字典。

    返回值:
    - 保存后的文件路径字符串。

    可能抛出的异常:
    - 文件写入错误可能抛出异常；一般情况下目录会自动创建。
    """
    logs_dir = os.path.join("logs")
    os.makedirs(logs_dir, exist_ok=True)
    path = os.path.join(logs_dir, f"env_check_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
    with open(path, "w", encoding="utf-8"):
        json.dump(report, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    return path


def main():
    """命令行入口: 解析参数、执行检测、打印与保存报告。

    参数:
    - 无(命令行参数通过 argparse 解析)。

    返回值:
    - 无；以退出码表示运行是否成功(0成功，非0为部分失败)。

    可能抛出的异常:
    - 顶层不抛出异常；内部异常会被捕获并转为退出码与提示。
    """
    parser = argparse.ArgumentParser(description="环境预检脚本: 检查依赖与服务是否可用")
    parser.add_argument("--ollama-url", type=str, default=None, help="Ollama 服务地址，例如 http://localhost:11434")
    args = parser.parse_args()

    try:
        report = gather_env_info(args.ollama_url)
        print_human_readable(report)
        # 尝试保存 JSON 报告
        try:
            # 避免在有权限问题时导致脚本失败
            logs_dir = os.path.join("logs")
            os.makedirs(logs_dir, exist_ok=True)
            out_path = os.path.join(logs_dir, f"env_check_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(report, f, ensure_ascii=False, indent=2)
            print(f"\nJSON报告已保存: {out_path}")
        except Exception as e:
            print(f"\nJSON报告保存失败: {e}")
        # 退出码策略：Python版本与关键依赖(pydub+ffmpeg、whisper 或 torch)以及 Ollama 可达性综合评估
        checks = report["checks"]
        critical_ok = (
            checks["python_version"]["ok"] and
            checks["pydub_backend"]["pydub_installed"] and checks["pydub_backend"]["ffmpeg_available"] and
            (checks["whisper_pkg"]["installed"] or checks["torch_gpu"]["torch_installed"]) and
            checks["ollama_server"]["reachable"]
        )
        sys.exit(0 if critical_ok else 2)
    except Exception as e:
        print(f"预检过程中出现未捕获错误: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()