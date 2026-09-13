import unittest
import os
import json
from butler.core.config_manager import config_manager
from butler.core.api_validator import APIValidator

class TestModelConfigCore(unittest.TestCase):
    def setUp(self):
        self.original_provider = config_manager.get('api.provider', 'deepseek')

    def tearDown(self):
        config_manager.set('api.provider', self.original_provider, persist=True)

    def test_provider_defaults_and_persistence(self):
        config_manager.set('api.provider', 'openai', persist=True)
        self.assertEqual(config_manager.get('api.provider'), 'openai')

        config_manager.set('api.model_name', 'gpt-4o', persist=True)
        self.assertEqual(config_manager.get('api.model_name'), 'gpt-4o')

        config_manager.set('api.temperature', 0.8, persist=True)
        self.assertEqual(config_manager.get('api.temperature'), 0.8)

        config_manager.set('api.max_tokens', 8192, persist=True)
        self.assertEqual(config_manager.get('api.max_tokens'), 8192)

    def test_api_validator_provider_test(self):
        # Test Ollama offline
        res = APIValidator.test_model_provider({
            'provider': 'ollama',
            'base_url': 'http://127.0.0.1:99999'
        })
        self.assertFalse(res['valid'])
        self.assertIn('error', res)

        # Test DeepSeek invalid key
        res_ds = APIValidator.test_model_provider({
            'provider': 'deepseek',
            'api_key': 'sk-invalid-key-test'
        })
        self.assertFalse(res_ds['valid'])
        self.assertEqual(res_ds['error'], 'API 密钥无效或未授权 (错误 401)')

if __name__ == '__main__':
    unittest.main()
