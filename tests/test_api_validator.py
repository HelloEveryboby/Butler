import pytest
from unittest.mock import patch, MagicMock
from butler.core.api_validator import APIValidator

class TestAPIValidator:

    @patch('requests.post')
    def test_validate_deepseek_success(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        result = APIValidator.validate_deepseek("valid_key")
        assert result['valid'] is True
        assert result['provider'] == 'DeepSeek'

    @patch('requests.post')
    def test_validate_deepseek_fail(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_post.return_value = mock_response

        result = APIValidator.validate_deepseek("invalid_key")
        assert result['valid'] is False
        assert '401' in result['error']

    def test_validate_baidu_basic(self):
        result = APIValidator.validate_baidu("123456")
        assert result['valid'] is True
        assert '格式正确' in result['note']

        result = APIValidator.validate_baidu("123")
        assert result['valid'] is False
        assert '太短' in result['error']

    @patch('requests.get')
    def test_validate_baidu_deep(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'access_token': 'test_token'}
        mock_get.return_value = mock_response

        result = APIValidator.validate_baidu("123456", "api_key", "secret_key")
        assert result['valid'] is True
        assert 'Access Token 获取成功' in result['note']

    def test_validate_all(self):
        with patch.object(APIValidator, 'validate_deepseek') as mock_ds, \
             patch.object(APIValidator, 'validate_baidu') as mock_bd:

            mock_ds.return_value = {'valid': True}
            mock_bd.return_value = {'valid': True}

            config = {
                'DEEPSEEK_API_KEY': 'ds_key',
                'BAIDU_APP_ID': 'bd_id'
            }

            results = APIValidator.validate_all(config)
            assert 'DEEPSEEK_API_KEY' in results
            assert 'BAIDU_APP_ID' in results
            assert results['DEEPSEEK_API_KEY']['valid'] is True
