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
            'timeout': 5,
            'func': 'validate_baidu'
        },
        'PICOVOICE_ACCESS_KEY': {
            'name': 'Picovoice Leopard',
            'required': False,
            'timeout': 5,
            'func': 'validate_picovoice'
        }
    }
    
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
    def validate_baidu(app_id: str) -> Dict[str, Any]:
        """验证 Baidu API 配置
        
        简单检查 App ID 格式
        """
        try:
            if not app_id:
                return {'valid': False, 'error': 'App ID 为空', 'provider': 'Baidu'}
            
            if len(app_id) < 5:
                return {'valid': False, 'error': 'App ID 格式无效（太短）', 'provider': 'Baidu'}
            
            if not app_id.isalnum():
                return {'valid': False, 'error': 'App ID 只能包含字母数字', 'provider': 'Baidu'}
            
            logger.info("🔑 Baidu App ID 格式有效")
            return {
                'valid': True,
                'error': None,
                'provider': 'Baidu',
                'note': '全量验证需要实际 API 调用，简化检查已首先执行'
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
        """验证所有配置的 API 密钥
        
        Args:
            config: {'API_KEY_NAME': 'value', ...}
            
        Returns:
            {'API_KEY_NAME': {'valid': bool, 'error': str, ...}, ...}
        """
        results = {}
        
        for key_name, validator_config in cls.VALIDATORS.items():
            if key_name in config and config[key_name]:
                validator_func = getattr(cls, validator_config['func'])
                results[key_name] = validator_func(config[key_name])
            else:
                if validator_config['required']:
                    results[key_name] = {
                        'valid': False,
                        'error': '密钥未提供',
                        'required': True
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
