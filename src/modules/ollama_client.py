"""
🎬 Ollama客户端模块
与本地Ollama服务交互进行AI文案改写
"""

import logging
import json
import time
import requests
from typing import Dict, Any, Optional, Union, Callable
from .config import CONFIG
from .utils import SystemUtils

logger = logging.getLogger(__name__)

class OllamaClient:
    """Ollama客户端"""

    def __init__(self):
        self.api_url = CONFIG.get('ollama.url', 'http://localhost:11434/api/generate')
        self.model = CONFIG.get('ollama.model', 'deepseek-r1:8b')
        self.timeout = CONFIG.get('ollama.timeout', 600)
        self.max_retries = CONFIG.get('ollama.max_retries', 3)
        self.retry_delay = CONFIG.get('ollama.retry_delay', 2)
        self.stream = CONFIG.get('ollama.stream', False)
        self.system_prompt = CONFIG.get('ollama.system_prompt', '')
        self.default_options = {
            # 优先从配置读取，回退到安全低内存值
            'num_ctx': CONFIG.get('ollama.options.num_ctx', 1024),
            'num_predict': CONFIG.get('ollama.options.num_predict', 512),
            'temperature': CONFIG.get('ollama.options.temperature', 0.7),
            'top_p': CONFIG.get('ollama.options.top_p', 0.9),
            'top_k': CONFIG.get('ollama.options.top_k', 40),
            'num_thread': CONFIG.get('advanced.cpu_threads', 4)
        }

        logger.info(f"🦙 Ollama客户端初始化完成 (模型: {self.model})")

    def test_connection(self) -> Dict[str, Any]:
        """测试Ollama服务连接"""
        try:
            # 测试服务基本连接
            response = requests.get(
                'http://localhost:11434',
                timeout=5
            )

            if response.status_code == 200:
                # 获取可用模型列表
                models_response = self._make_request(
                    'http://localhost:11434/api/tags',
                    method='GET'
                )

                if models_response.get('success'):
                    models = models_response.get('data', {}).get('models', [])
                    available_models = [model['name'] for model in models]

                    return {
                        'success': True,
                        'connected': True,
                        'available_models': available_models,
                        'current_model': self.model,
                        'model_available': self.model in available_models
                    }
                else:
                    return {
                        'success': True,
                        'connected': True,
                        'available_models': [],
                        'current_model': self.model,
                        'model_available': False,
                        'warning': '无法获取模型列表'
                    }
            else:
                return {
                    'success': False,
                    'connected': False,
                    'error': f'Ollama服务响应异常: {response.status_code}'
                }

        except requests.exceptions.ConnectionError:
            return {
                'success': False,
                'connected': False,
                'error': '无法连接到Ollama服务，请确认服务正在运行'
            }
        except requests.exceptions.Timeout:
            return {
                'success': False,
                'connected': False,
                'error': '连接Ollama服务超时'
            }
        except Exception as e:
            return {
                'success': False,
                'connected': False,
                'error': f'连接测试失败: {str(e)}'
            }

    def rewrite_text(
        self,
        original_text: str,
        model: str = None,
        system_prompt: str = None,
        progress_callback: Callable = None
    ) -> Dict[str, Any]:
        """
        使用AI改写文案

        Args:
            original_text: 原始文案
            model: 使用的模型（可选）
            system_prompt: 系统提示词（可选）
            progress_callback: 进度回调函数

        Returns:
            改写结果字典
        """
        try:
            # 验证输入
            if not original_text or not original_text.strip():
                return {
                    'success': False,
                    'error': '原始文案不能为空',
                    'rewritten_text': None
                }

            # 使用默认值
            model = model or self.model
            system_prompt = system_prompt or self.system_prompt

            logger.info(f"🦙 开始AI文案改写 (模型: {model})")
            logger.debug(f"原始文案长度: {len(original_text)} 字符")

            # 测试连接
            connection_test = self.test_connection()
            if not connection_test['success']:
                return connection_test

            if not connection_test.get('model_available', True):
                logger.warning(f"模型 {model} 不可用")

            # 构建请求参数（确保仅输出仿写文案）
            request_data = {
                'model': model,
                'prompt': (
                    "请严格根据系统提示词进行仿写。\n"
                    "要求：只输出仿写后的文案，不要输出任何解释或多余内容。\n"
                    f"原文如下：\n{original_text}\n"
                ),
                'system': system_prompt,
                'stream': self.stream,
                'options': dict(self.default_options)
            }

            if progress_callback:
                progress_callback(10, "准备AI改写...")
                progress_callback(30, "发送请求到Ollama...")

            # 发送请求
            response = self._make_request_with_retry(
                self.api_url,
                method='POST',
                data=request_data,
                progress_callback=progress_callback
            )

            # 针对内存布局错误进行一次自动降配重试
            if (not response.get('success')) and isinstance(response.get('error'), str) and (
                'memory layout cannot be allocated' in response['error'] or
                'unable to allocate' in response['error']
            ):
                logger.warning("检测到内存布局分配失败，自动降配重试：减小上下文与预测长度")
                # 降低上下文与预测长度
                request_data['options']['num_ctx'] = max(512, int(request_data['options'].get('num_ctx', 1024) / 2))
                request_data['options']['num_predict'] = max(256, int(request_data['options'].get('num_predict', 512) / 2))
                # 再次尝试
                response = self._make_request_with_retry(
                    self.api_url,
                    method='POST',
                    data=request_data,
                    progress_callback=progress_callback
                )

            # 若仍失败且明确为内存错误，尝试更小模型一次
            if (not response.get('success')) and isinstance(response.get('error'), str) and (
                'memory layout cannot be allocated' in response['error'] or
                'unable to allocate' in response['error']
            ):
                fallback_model = 'qwen2:1.5b'
                logger.warning(f"当前模型 {model} 内存不足，尝试更小模型: {fallback_model}")
                request_data['model'] = fallback_model
                response = self._make_request_with_retry(
                    self.api_url,
                    method='POST',
                    data=request_data,
                    progress_callback=progress_callback
                )
                # 如果返回404模型不存在，则自动拉取并重试一次
                if (not response.get('success')) and str(response.get('error', '')).startswith('HTTP 404'):
                    if progress_callback:
                        progress_callback(35, f"未找到模型 {fallback_model}，开始拉取...")
                    pull_resp = self._pull_model(fallback_model, progress_callback)
                    if pull_resp.get('success'):
                        logger.info(f"模型 {fallback_model} 拉取完成，重试生成")
                        response = self._make_request_with_retry(
                            self.api_url,
                            method='POST',
                            data=request_data,
                            progress_callback=progress_callback
                        )
                    else:
                        logger.warning(f"模型拉取失败: {pull_resp.get('error')}")

            if progress_callback:
                progress_callback(90, "处理AI响应...")

            # 处理响应
            if response['success']:
                rewritten_text = self._extract_text_from_response(response['data'])
                rewritten_text = self._cleanup_output(rewritten_text).strip()
                rewritten_text = self._ensure_same_opening(original_text, rewritten_text)

                if not rewritten_text:
                    return {
                        'success': False,
                        'error': 'AI未生成改写内容',
                        'rewritten_text': None
                    }

                logger.info(f"✅ AI文案改写成功，生成字数: {len(rewritten_text)}")

                return {
                    'success': True,
                    'rewritten_text': rewritten_text,
                    'original_text': original_text,
                    'model_used': model,
                    'original_length': len(original_text),
                    'rewritten_length': len(rewritten_text),
                    'processing_time': response.get('processing_time', 0)
                }
            else:
                return response

        except Exception as e:
            logger.error(f"❌ AI文案改写失败: {e}")
            return {
                'success': False,
                'error': str(e),
                'rewritten_text': None
            }

    def _extract_text_from_response(self, response_data: Dict[str, Any]) -> str:
        """从响应中提取文本内容"""
        try:
            # 处理deepseek-r1:8b等模型的特殊响应格式
            if isinstance(response_data, dict):
                # 检查是否有response字段
                if 'response' in response_data:
                    response_text = response_data['response']
                    # 如果response不为空，直接返回
                    if response_text and response_text.strip():
                        return response_text

                # 如果没有response字段，尝试其他可能的字段
                possible_fields = ['text', 'content', 'generated_text', 'output']
                for field in possible_fields:
                    if field in response_data:
                        value = response_data[field]
                        if value and str(value).strip():
                            return str(value)

                # 如果都没有，尝试从其他字段提取文本
                for key, value in response_data.items():
                    if key not in ['model', 'created_at', 'done', 'done_reason', 'context', 'total_duration', 'load_duration', 'prompt_eval_count', 'prompt_eval_duration', 'eval_count', 'eval_duration', 'thinking'] and isinstance(value, str) and value.strip():
                        return value

                # 最后的备选方案：返回所有字符串字段的组合
                text_parts = []
                for key, value in response_data.items():
                    if isinstance(value, str) and value.strip():
                        text_parts.append(value)
                if text_parts:
                    return ' '.join(text_parts)

            elif isinstance(response_data, str):
                return response_data
            elif isinstance(response_data, list):
                # 处理流式响应的列表格式
                return ''.join(item.get('response', '') if isinstance(item, dict) else str(item) for item in response_data)
            else:
                return str(response_data)

        except Exception as e:
            logger.warning(f"响应文本提取失败: {e}")
            logger.debug(f"响应数据: {response_data}")
            return str(response_data)

    def _cleanup_output(self, text: str) -> str:
        """清理模型输出中的多余标签或前缀，保留纯仿写文案"""
        try:
            cleaned = text.strip()
            # 去除常见前缀
            prefixes = [
                "仿写：", "仿写文案：", "改写：", "改写文案：",
                "以下是仿写后的文案：", "以下为仿写结果：",
                "结果：", "输出："
            ]
            for p in prefixes:
                if cleaned.startswith(p):
                    cleaned = cleaned[len(p):].strip()
                    break
            return cleaned
        except Exception:
            return text

    def _ensure_same_opening(self, original_text: str, rewritten_text: str) -> str:
        """确保仿写文案的开头与原文一致（按首句或首行匹配）"""
        try:
            orig = original_text.strip()
            rew = rewritten_text.strip()

            if not orig or not rew:
                return rew

            # 提取原文首句/首行
            delimiters = ['。', '！', '？', '\n']
            cut_idx = None
            for d in delimiters:
                i = orig.find(d)
                if i != -1:
                    cut_idx = i + len(d)
                    break
            orig_opening = orig[:cut_idx] if cut_idx else orig.split('\n', 1)[0]

            # 如果仿写不以原始开头开始，则强制前置
            if not rew.startswith(orig_opening):
                rew = f"{orig_opening}{rew}"

            return rew
        except Exception:
            return rewritten_text

    def _make_request_with_retry(
        self,
        url: str,
        method: str = 'POST',
        data: Dict[str, Any] = None,
        progress_callback: Callable = None
    ) -> Dict[str, Any]:
        """带重试机制的请求"""
        last_error = None

        for attempt in range(self.max_retries):
            try:
                if progress_callback:
                    progress_callback(50, f"AI处理中... (尝试 {attempt + 1}/{self.max_retries})")

                start_time = time.time()
                response = self._make_request(url, method, data)

                processing_time = time.time() - start_time

                if response['success']:
                    response['processing_time'] = processing_time
                    return response
                else:
                    last_error = response.get('error', '未知错误')

            except Exception as e:
                last_error = str(e)
                logger.warning(f"请求失败 (尝试 {attempt + 1}/{self.max_retries}): {e}")

            # 如果不是最后一次尝试，等待重试
            if attempt < self.max_retries - 1:
                wait_time = self.retry_delay * (2 ** attempt)  # 指数退避
                logger.info(f"等待 {wait_time} 秒后重试...")
                time.sleep(wait_time)

        return {
            'success': False,
            'error': f'请求失败，已重试 {self.max_retries} 次: {last_error}'
        }

    def _make_request(
        self,
        url: str,
        method: str = 'POST',
        data: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """发送HTTP请求"""
        try:
            if method.upper() == 'GET':
                response = requests.get(url, timeout=self.timeout)
            elif method.upper() == 'POST':
                response = requests.post(
                    url,
                    json=data,
                    timeout=self.timeout,
                    headers={'Content-Type': 'application/json'}
                )
            else:
                return {
                    'success': False,
                    'error': f'不支持的HTTP方法: {method}'
                }

            if response.status_code == 200:
                return {
                    'success': True,
                    'data': response.json(),
                    'status_code': response.status_code
                }
            else:
                return {
                    'success': False,
                    'error': f'HTTP {response.status_code}: {response.text}',
                    'status_code': response.status_code
                }

        except requests.exceptions.Timeout:
            return {
                'success': False,
                'error': '请求超时'
            }

    def _pull_model(self, model_name: str, progress_callback: Callable = None) -> Dict[str, Any]:
        """拉取指定模型（如果未安装）"""
        try:
            response = requests.post(
                'http://localhost:11434/api/pull',
                json={'name': model_name},
                timeout=self.timeout,
                headers={'Content-Type': 'application/json'}
            )
            if response.status_code == 200:
                return {
                    'success': True,
                    'data': response.json(),
                    'status_code': response.status_code
                }
            else:
                return {
                    'success': False,
                    'error': f'HTTP {response.status_code}: {response.text}',
                    'status_code': response.status_code
                }
        except Exception as e:
            return {
                'success': False,
                'error': f'拉取模型异常: {str(e)}'
            }
        except requests.exceptions.ConnectionError:
            return {
                'success': False,
                'error': '连接错误'
            }
        except requests.exceptions.JSONDecodeError:
            return {
                'success': False,
                'error': '响应JSON解析失败'
            }
        except Exception as e:
            return {
                'success': False,
                'error': f'请求异常: {str(e)}'
            }

    def get_available_models(self) -> Dict[str, Any]:
        """获取可用模型列表"""
        try:
            response = self._make_request(
                'http://localhost:11434/api/tags',
                method='GET'
            )

            if response['success']:
                models = response.get('data', {}).get('models', [])
                model_info = []

                for model in models:
                    model_info.append({
                        'name': model.get('name'),
                        'size_mb': model.get('size', 0) / (1024 * 1024),
                        'modified_at': model.get('modified_at'),
                        'digest': model.get('digest')[:12]  # 显示前12位
                    })

                return {
                    'success': True,
                    'models': model_info,
                    'total_models': len(model_info)
                }
            else:
                return response

        except Exception as e:
            return {
                'success': False,
                'error': f'获取模型列表失败: {str(e)}'
            }

    def get_model_info(self, model_name: str = None) -> Dict[str, Any]:
        """获取模型信息"""
        if model_name is None:
            model_name = self.model

        # 模型信息映射
        model_specs = {
            'deepseek-r1:8b': {
                'name': 'DeepSeek R1 8B',
                'description': '中文优化，逻辑性强，适合文案改写',
                'size_gb': 4.7,
                'recommended': True
            },
            'llama3-chinese:8b': {
                'name': 'Llama3 Chinese 8B',
                'description': '中文对话，响应快，适合快速改写',
                'size_gb': 4.7,
                'recommended': True
            },
            'qwen:7b': {
                'name': 'Qwen 7B',
                'description': '阿里出品，中文优秀，适合创意文案',
                'size_gb': 4.3,
                'recommended': True
            },
            'qwen:14b': {
                'name': 'Qwen 14B',
                'description': '大模型，质量更高，适合专业创作',
                'size_gb': 8.3,
                'recommended': True
            },
            'llama3:8b': {
                'name': 'Llama3 8B',
                'description': '通用大模型，多语言支持',
                'size_gb': 4.7,
                'recommended': False
            }
        }

        return model_specs.get(model_name, {
            'name': model_name,
            'description': '未知模型',
            'size_gb': 0,
            'recommended': False
        })

    def set_model(self, model_name: str) -> bool:
        """设置当前模型"""
        try:
            # 测试模型是否存在
            models_response = self.get_available_models()
            if models_response['success']:
                available_models = [model['name'] for model in models_response['models']]
                if model_name not in available_models:
                    logger.warning(f"模型 {model_name} 不在可用列表中")
                    return False

            self.model = model_name
            logger.info(f"模型已切换到: {model_name}")
            return True

        except Exception as e:
            logger.error(f"设置模型失败: {e}")
            return False

    def rewrite_with_different_styles(
        self,
        original_text: str,
        styles: list = None,
        progress_callback: Callable = None
    ) -> Dict[str, Any]:
        """使用不同风格改写文案"""
        if styles is None:
            styles = [
                "保持原有风格，但优化表达",
                "更加生动有趣，增加感染力",
                "更加专业正式，突出重点",
                "更加简洁明了，便于理解"
            ]

        results = []
        total_styles = len(styles)

        for i, style in enumerate(styles):
            try:
                # 自定义系统提示词
                custom_prompt = f"{self.system_prompt}\n\n改写风格：{style}"

                if progress_callback:
                    progress = (i / total_styles) * 100
                    progress_callback(progress, f"生成风格{i+1}/{total_styles}: {style[:20]}...")

                result = self.rewrite_text(
                    original_text,
                    system_prompt=custom_prompt
                )

                if result['success']:
                    results.append({
                        'style': style,
                        'text': result['rewritten_text'],
                        'model': result['model_used'],
                        'processing_time': result['processing_time']
                    })

            except Exception as e:
                logger.error(f"风格{i+1}改写失败: {e}")

        if progress_callback:
            progress_callback(100, "多风格改写完成")

        return {
            'success': len(results) > 0,
            'original_text': original_text,
            'style_results': results,
            'total_styles': total_styles,
            'successful_styles': len(results)
        }

    def batch_rewrite(
        self,
        texts: list,
        progress_callback: Callable = None
    ) -> Dict[str, Any]:
        """批量改写文案"""
        try:
            results = []
            total_texts = len(texts)

            for i, text in enumerate(texts):
                try:
                    if progress_callback:
                        progress = (i / total_texts) * 100
                        progress_callback(progress, f"改写文案 {i+1}/{total_texts}")

                    result = self.rewrite_text(text)
                    results.append(result)

                except Exception as e:
                    logger.error(f"文案{i+1}改写失败: {e}")

            if progress_callback:
                progress_callback(100, "批量改写完成")

            successful_results = [r for r in results if r['success']]

            return {
                'success': len(successful_results) > 0,
                'total_texts': total_texts,
                'successful_texts': len(successful_results),
                'results': results,
                'success_rate': len(successful_results) / total_texts if total_texts > 0 else 0
            }

        except Exception as e:
            return {
                'success': False,
                'error': f'批量改写失败: {str(e)}'
            }

if __name__ == "__main__":
    # 测试Ollama客户端
    print("=== Ollama客户端测试 ===")

    client = OllamaClient()

    # 测试连接
    print("\n--- 连接测试 ---")
    connection = client.test_connection()
    print(f"连接状态: {connection}")

    # 获取可用模型
    print("\n--- 可用模型 ---")
    models = client.get_available_models()
    if models['success']:
        for model in models['models']:
            print(f"  {model['name']} - {model['size_mb']:.1f}MB")

    # 模型信息
    print("\n--- 模型信息 ---")
    info = client.get_model_info()
    print(f"当前模型: {info}")

    # 测试改写（如果连接成功）
    if connection['success']:
        print("\n--- 改写测试 ---")
        test_text = "这是一段测试文案，用来测试AI改写功能是否正常工作。"
        result = client.rewrite_text(test_text)

        if result['success']:
            print(f"✅ 改写成功")
            print(f"原文: {test_text}")
            print(f"改写: {result['rewritten_text']}")
        else:
            print(f"❌ 改写失败: {result.get('error')}")
    else:
        print("❌ 连接失败，跳过改写测试")