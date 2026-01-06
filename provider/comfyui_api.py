from typing import Any
from urllib.parse import urlparse

import requests

from dify_plugin import ToolProvider
from dify_plugin.errors.tool import ToolProviderCredentialValidationError


class ComfyuiApiProvider(ToolProvider):
    
    def _validate_credentials(self, credentials: dict[str, Any]) -> None:
        try:
            # 验证服务器地址
            server_url = credentials.get("comfyui_server_url")
            if not server_url:
                raise ToolProviderCredentialValidationError("ComfyUI server URL is required")
            
            # 验证 URL 格式
            parsed = urlparse(server_url)
            if not parsed.scheme or not parsed.netloc:
                raise ToolProviderCredentialValidationError("Invalid ComfyUI server URL format")
            
            # 测试连接（可选，但建议进行基本验证）
            try:
                # 尝试访问 ComfyUI 的 system_stats 端点来验证连接
                headers = {}
                auth_key = credentials.get("auth_key")
                if auth_key:
                    headers["Authorization"] = f"Bearer {auth_key}"
                
                response = requests.get(
                    f"{server_url.rstrip('/')}/system_stats",
                    headers=headers,
                    timeout=5
                )
                # 如果返回 401，说明需要认证但密钥可能错误
                if response.status_code == 401:
                    raise ToolProviderCredentialValidationError("Authentication failed. Please check your auth_key.")
                # 其他错误可能是服务器问题，但不一定是凭据问题
            except requests.exceptions.RequestException as e:
                # 连接失败可能是网络问题，不一定是凭据错误
                # 只记录警告，不抛出错误
                pass
                
        except ToolProviderCredentialValidationError:
            raise
        except Exception as e:
            raise ToolProviderCredentialValidationError(f"Credential validation failed: {str(e)}")

