"""API 验证器 - 支持多个 API 服务的验证

Supports validation for:
- DeepSeek
- Baidu AI
- Picovoice
"""

import requests
from typing import Dict, Any, Optional
from package.core_utils.log_manager import LogManager

logger = LogManager.get_logger(__name__)


class APIValidator:
    """统一的 API 验证器"""
    
    # 验证配置
    VALIDATORS = {
        'DEEPSEEK_API_KEY': {
            'name': 'DeepSeek Chat API',
            'required': True,
            'timeout': 5,
            'func': 'validate_deepseek'
        },
        'BAIDU_APP_ID': {
            'name': 'Baidu Speech API',
            'required': False,
            'timeout': 10,
            'func': 'validate_baidu'
        },
        'PICOVOICE_ACCESS_KEY': {
            'name': 'Picovoice Leopard',
            'required': False,
            'timeout': 10,
            'func': 'validate_picovoice'
        }
    }
    
    @classmethod
    def test_model_provider(cls, config: Dict[str, Any]) -> Dict[str, Any]:
        """通用 AI 大模型提供商连通性与密钥在线测试

        Args:
            config: 包含 provider, api_key, base_url, model_name, secret_key, app_id 等字典

        Returns:
            {
                'valid': bool,
                'latency_ms': int,
                'error': Optional[str],
                'models': List[str]
            }
        """
        import time
        provider = config.get('provider', 'deepseek').lower()
        api_key = config.get('api_key', '').strip()
        base_url = (config.get('base_url') or '').rstrip('/')
        model_name = config.get('model_name', '').strip()
        secret_key = config.get('secret_key', '').strip()
        app_id = config.get('app_id', '').strip()

        start_time = time.time()

        # 1. Ollama (本地免 Key)
        if provider == 'ollama':
            url = base_url if base_url else "http://localhost:11434"
            # Ollama 模型列表接口固定为 /api/tags，去除可能的 /v1 后缀
            tags_base = url.rstrip('/')
            if tags_base.endswith('/v1'):
                tags_base = tags_base[:-3]
            try:
                # 获取可用模型列表
                resp = requests.get(f"{tags_base}/api/tags", timeout=5)
                elapsed_ms = int((time.time() - start_time) * 1000)
                if resp.status_code == 200:
                    models_data = resp.json().get('models', [])
                    model_list = [m.get('name') for m in models_data if m.get('name')]
                    return {
                        'valid': True,
                        'latency_ms': elapsed_ms,
                        'error': None,
                        'models': model_list
                    }
                else:
                    return {'valid': False, 'latency_ms': elapsed_ms, 'error': f"Ollama 服务响应 HTTP {resp.status_code}", 'models': []}
            except Exception as e:
                return {'valid': False, 'latency_ms': 0, 'error': f"无法连接 Local Ollama: {str(e)[:80]}", 'models': []}

        # 2. 百度千帆 (Qianfan / Baidu)
        if provider in ('qianfan', 'baidu'):
            # 若提供了 api_key + secret_key 走 oauth
            if secret_key:
                try:
                    oauth_url = f"https://aip.baidubce.com/oauth/2.0/token?grant_type=client_credentials&client_id={api_key}&client_secret={secret_key}"
                    token_resp = requests.get(oauth_url, timeout=5)
                    elapsed_ms = int((time.time() - start_time) * 1000)
                    if token_resp.status_code == 200 and 'access_token' in token_resp.json():
                        return {'valid': True, 'latency_ms': elapsed_ms, 'error': None, 'models': ['ernie-4.0-8k', 'ernie-3.5-8k', 'ernie-speed-128k']}
                    else:
                        err = token_resp.json().get('error_description', f'HTTP {token_resp.status_code}')
                        return {'valid': False, 'latency_ms': elapsed_ms, 'error': f"百度 Auth 校验失败: {err}", 'models': []}
                except Exception as e:
                    return {'valid': False, 'latency_ms': 0, 'error': f"百度 Auth 请求失败: {str(e)[:80]}", 'models': []}
            elif not api_key:
                return {'valid': False, 'latency_ms': 0, 'error': "API Key 不能为空", 'models': []}

        # 3. Anthropic (Claude)
        if provider in ('anthropic', 'claude'):
            if not api_key:
                return {'valid': False, 'latency_ms': 0, 'error': "API Key 不能为空", 'models': []}
            url = base_url if base_url else "https://api.anthropic.com"
            try:
                resp = requests.post(
                    f"{url}/v1/messages",
                    headers={
                        "x-api-key": api_key,
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json"
                    },
                    json={
                        "model": model_name or "claude-3-5-sonnet-20241022",
                        "max_tokens": 1,
                        "messages": [{"role": "user", "content": "ping"}]
                    },
                    timeout=8
                )
                elapsed_ms = int((time.time() - start_time) * 1000)
                if resp.status_code == 200:
                    return {'valid': True, 'latency_ms': elapsed_ms, 'error': None, 'models': ['claude-3-5-sonnet-20241022', 'claude-3-5-haiku-20241022', 'claude-3-opus-20240229']}
                elif resp.status_code == 401:
                    return {'valid': False, 'latency_ms': elapsed_ms, 'error': "Anthropic API Key 无效或未授权 (401)", 'models': []}
                else:
                    err_msg = resp.json().get('error', {}).get('message', f'HTTP {resp.status_code}')
                    return {'valid': False, 'latency_ms': elapsed_ms, 'error': f"Anthropic 错误: {err_msg}", 'models': []}
            except Exception as e:
                return {'valid': False, 'latency_ms': 0, 'error': f"连接 Anthropic 失败: {str(e)[:80]}", 'models': []}

        # 4. Standard OpenAI / DeepSeek / Custom OpenAI-compatible
        if not api_key and provider != 'custom':
            return {'valid': False, 'latency_ms': 0, 'error': "API Key 不能为空", 'models': []}

        # Determine target Base URL
        if not base_url:
            if provider == 'deepseek':
                base_url = "https://api.deepseek.com/v1"
            elif provider == 'openai':
                base_url = "https://api.openai.com/v1"
            elif provider == 'zhipu':
                base_url = "https://open.bigmodel.cn/api/paas/v4"
            else:
                base_url = "https://api.openai.com/v1"

        test_model = model_name or ("deepseek-chat" if provider == 'deepseek' else "gpt-3.5-turbo")

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

        # Fetch models list if available
        fetched_models = []
        try:
            models_resp = requests.get(f"{base_url}/models", headers=headers, timeout=5)
            if models_resp.status_code == 200:
                data = models_resp.json().get('data', [])
                if isinstance(data, list):
                    fetched_models = [m.get('id') for m in data if isinstance(m, dict) and m.get('id')]
        except Exception:
            pass

        # Perform chat completion ping
        try:
            chat_url = f"{base_url}/chat/completions"
            payload = {
                "model": test_model,
                "messages": [{"role": "user", "content": "ping"}],
                "max_tokens": 1
            }
            resp = requests.post(chat_url, headers=headers, json=payload, timeout=8)
            elapsed_ms = int((time.time() - start_time) * 1000)

            if resp.status_code == 200:
                return {
                    'valid': True,
                    'latency_ms': elapsed_ms,
                    'error': None,
                    'models': fetched_models
                }
            elif resp.status_code == 401:
                return {'valid': False, 'latency_ms': elapsed_ms, 'error': "API 密钥无效或未授权 (错误 401)", 'models': fetched_models}
            elif resp.status_code == 404:
                # If models endpoint worked or chat completions not found, fallback to checking /models
                if fetched_models:
                    return {'valid': True, 'latency_ms': elapsed_ms, 'error': None, 'models': fetched_models}
                return {'valid': False, 'latency_ms': elapsed_ms, 'error': f"Base URL Endpoint 未找到 (错误 404): {chat_url}", 'models': []}
            else:
                err_msg = f"HTTP 错误 {resp.status_code}"
                try:
                    r_json = resp.json()
                    if 'error' in r_json:
                        if isinstance(r_json['error'], dict):
                            err_msg = r_json['error'].get('message', err_msg)
                        else:
                            err_msg = str(r_json['error'])
                except Exception:
                    pass
                return {'valid': False, 'latency_ms': elapsed_ms, 'error': err_msg, 'models': fetched_models}

        except requests.exceptions.Timeout:
            return {'valid': False, 'latency_ms': 0, 'error': '连接超时（网络似乎稍慢）', 'models': fetched_models}
        except requests.exceptions.ConnectionError:
            return {'valid': False, 'latency_ms': 0, 'error': '网络连接失败（请检查 Endpoint URL）', 'models': fetched_models}
        except Exception as e:
            return {'valid': False, 'latency_ms': 0, 'error': str(e)[:100], 'models': fetched_models}

    @staticmethod
    def validate_deepseek(api_key: str) -> Dict[str, Any]:
        """验证 DeepSeek API 密钥
        
        Args:
            api_key: DeepSeek API 密钥
            
        Returns:
            {
                'valid': bool,
                'error': Optional[str],
                'provider': str,
                'quota': Optional[Dict]
            }
        """
        try:
            response = requests.post(
                "https://api.deepseek.com/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "deepseek-chat",
                    "messages": [{"role": "user", "content": "test"}],
                    "max_tokens": 1,
                    "temperature": 0.5
                },
                timeout=5
            )
            
            if response.status_code == 200:
                logger.info("🔑 DeepSeek API 密钥有效")
                return {
                    'valid': True,
                    'error': None,
                    'provider': 'DeepSeek',
                    'quota': None
                }
            elif response.status_code == 401:
                error = '密钥不有效或已过期 (错误 401)'
            elif response.status_code == 429:
                error = '请求过于频繁，请稍后再试 (错误 429)'
            elif response.status_code == 500:
                error = 'DeepSeek 服务器错误 (错误 500)'
            else:
                error = f'HTTP 错误: {response.status_code}'
                try:
                    resp_data = response.json()
                    if 'error' in resp_data:
                        error = f"{resp_data['error'].get('message', str(resp_data['error'])[:100])}"
                except:
                    pass
            
            return {'valid': False, 'error': error, 'provider': 'DeepSeek'}
            
        except requests.exceptions.Timeout:
            return {'valid': False, 'error': '连接超时（网络似乎稍慢）', 'provider': 'DeepSeek'}
        except requests.exceptions.ConnectionError:
            return {'valid': False, 'error': '网络连接失败（请检查你的互联网）', 'provider': 'DeepSeek'}
        except Exception as e:
            error_msg = str(e)[:100]
            logger.error(f"测试 DeepSeek 密钥时出错: {e}")
            return {'valid': False, 'error': error_msg, 'provider': 'DeepSeek'}
    
    @staticmethod
    def validate_baidu(app_id: str, api_key: str = None, secret_key: str = None) -> Dict[str, Any]:
        """验证 Baidu API 配置
        
        如果提供了 API Key 和 Secret Key，则尝试获取 Access Token 进行深度验证
        """
        try:
            if not app_id:
                return {'valid': False, 'error': 'App ID 为空', 'provider': 'Baidu'}
            
            if len(app_id) < 5:
                return {'valid': False, 'error': 'App ID 格式无效（太短）', 'provider': 'Baidu'}
            
            # 如果提供了三要素，进行深度验证
            if api_key and secret_key:
                try:
                    url = f"https://aip.baidubce.com/oauth/2.0/token?grant_type=client_credentials&client_id={api_key}&client_secret={secret_key}"
                    response = requests.get(url, timeout=10)
                    if response.status_code == 200:
                        data = response.json()
                        if 'access_token' in data:
                            logger.info("🔑 Baidu API 验证成功")
                            return {
                                'valid': True,
                                'error': None,
                                'provider': 'Baidu',
                                'note': 'Access Token 获取成功，API 配置有效'
                            }
                        else:
                            return {'valid': False, 'error': f"验证失败: {data.get('error_description', '未知错误')}", 'provider': 'Baidu'}
                    else:
                        return {'valid': False, 'error': f"HTTP 错误: {response.status_code}", 'provider': 'Baidu'}
                except Exception as e:
                    return {'valid': False, 'error': f"深度验证失败: {str(e)[:50]}", 'provider': 'Baidu'}

            logger.info("🔑 Baidu App ID 格式有效")
            return {
                'valid': True,
                'error': None,
                'provider': 'Baidu',
                'note': 'App ID 格式正确（未提供 API Key 进行深度验证）'
            }
        except Exception as e:
            return {'valid': False, 'error': str(e), 'provider': 'Baidu'}
    
    @staticmethod
    def validate_picovoice(access_key: str) -> Dict[str, Any]:
        """验证 Picovoice Access Key
        
        验证访问密钥的格式和有效性
        """
        try:
            if not access_key:
                return {'valid': False, 'error': 'Access Key 为空', 'provider': 'Picovoice'}
            
            # Picovoice 密钥直接使用 Leopard SDK 验证
            # 接下次尝试导入，但不强制要求
            try:
                import pvleopard
                leopard = pvleopard.create(access_key=access_key)
                leopard.delete()
                
                logger.info("🔑 Picovoice Access Key 有效")
                return {
                    'valid': True,
                    'error': None,
                    'provider': 'Picovoice',
                    'model': 'Leopard'
                }
            except ImportError:
                # 没有安装 Picovoice SDK，只检查格式
                if len(access_key) > 10 and access_key.replace('_', '').isalnum():
                    logger.warning("🔑 Picovoice Access Key 格式看起来有效（未安装 SDK，混合检查）")
                    return {
                        'valid': True,
                        'error': None,
                        'provider': 'Picovoice',
                        'note': 'SDK 未安装，不能完整验证'
                    }
                else:
                    return {'valid': False, 'error': 'Access Key 格式无效', 'provider': 'Picovoice'}
            except Exception as e:
                return {'valid': False, 'error': f'验证失败: {str(e)[:50]}', 'provider': 'Picovoice'}
        
        except Exception as e:
            return {'valid': False, 'error': str(e), 'provider': 'Picovoice'}
    
    @classmethod
    def validate_all(cls, config: Dict[str, str]) -> Dict[str, Dict[str, Any]]:
        """验证所有配置的 API 密钥"""
        results = {}
        
        for key_name, validator_config in cls.VALIDATORS.items():
            value = config.get(key_name)
            if value:
                validator_func = getattr(cls, validator_config['func'])

                # Baidu 需要特殊处理多参数
                if key_name == 'BAIDU_APP_ID':
                    results[key_name] = validator_func(
                        value,
                        config.get('BAIDU_API_KEY'),
                        config.get('BAIDU_SECRET_KEY')
                    )
                else:
                    results[key_name] = validator_func(value)
            else:
                if validator_config.get('required', False):
                    results[key_name] = {
                        'valid': False,
                        'error': '必需的密钥未提供',
                        'required': True,
                        'provider': validator_config['name']
                    }
        
        return results
    
    @classmethod
    def validate_key(cls, key_name: str, api_key: str) -> Dict[str, Any]:
        """验证单个 API 密钥
        
        Args:
            key_name: 密钥名称（如 'DEEPSEEK_API_KEY'）
            api_key: 密钥值
            
        Returns:
            验证结果
        """
        if key_name not in cls.VALIDATORS:
            return {'valid': False, 'error': f'未知的密钥类型: {key_name}'}
        
        validator_config = cls.VALIDATORS[key_name]
        validator_func = getattr(cls, validator_config['func'])
        return validator_func(api_key)


# 例子
if __name__ == '__main__':
    # 测试
    result = APIValidator.validate_deepseek('sk-test')
    print(result)
