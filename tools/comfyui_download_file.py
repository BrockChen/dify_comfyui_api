from collections.abc import Generator
from typing import Any

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

from .utils import (
    get_logger,
    get_credentials,
    validate_server_url,
    prepare_headers,
    get_mime_type,
    download_file_from_comfyui
)

logger = get_logger(__name__)


class ComfyuiDownloadFileTool(Tool):
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage]:
        try:
            # 获取参数
            filename = tool_parameters.get("filename")
            if not filename:
                logger.error("filename parameter is required")
                yield self.create_text_message("Error: filename parameter is required")
                return
            
            subfolder = tool_parameters.get("subfolder", "")
            file_type = tool_parameters.get("file_type", "output")
            prompt_id = tool_parameters.get("prompt_id")
            
            logger.info(f"Starting file download. Filename: {filename}, Subfolder: {subfolder}, Type: {file_type}")
            
            # 获取凭据
            server_url, auth_key = get_credentials(self.runtime)
            
            if not validate_server_url(server_url):
                logger.error("ComfyUI server URL is not configured")
                yield self.create_text_message("Error: ComfyUI server URL is not configured")
                return
            
            logger.info(f"ComfyUI server URL: {server_url}")
            
            # 准备请求头
            headers = prepare_headers(auth_key)
            if auth_key:
                logger.debug("Using authentication key")
            
            # 检查Dify存储中是否已存在相同文件名的文件
            existing_url = self._check_file_in_dify_storage(filename)
            if existing_url:
                logger.info(f"File {filename} already exists in Dify storage. Skipping download.")
                yield self.create_json_message({
                    "status": "success",
                    "url": existing_url,
                    "filename": filename,
                    "skipped": True,
                    "message": f"File {filename} already exists in Dify storage. Download skipped."
                })
                return
            
            # 从ComfyUI下载文件
            file_data = download_file_from_comfyui(
                filename, subfolder, file_type, server_url, headers, logger
            )
            
            if not file_data:
                logger.error("Failed to download file from ComfyUI")
                yield self.create_text_message("Error: Failed to download file from ComfyUI")
                return
            
            logger.info(f"Downloaded file from ComfyUI. Size: {len(file_data)} bytes")
            
            # 上传到Dify存储
            try:
                # 确定MIME类型
                mime_type = get_mime_type(filename)
                
                # 上传到Dify存储
                dify_url = self.session.storage.upload_file(
                    file_data,
                    filename=filename,
                    mime_type=mime_type
                )
                
                logger.info(f"File uploaded to Dify storage. URL: {dify_url}")
                
                yield self.create_json_message({
                    "status": "success",
                    "url": dify_url,
                    "filename": filename,
                    "skipped": False,
                    "message": "File downloaded from ComfyUI and uploaded to Dify storage successfully"
                })
                
            except Exception as e:
                logger.error(f"Failed to upload file to Dify storage: {str(e)}")
                yield self.create_text_message(f"Error: Failed to upload file to Dify storage - {str(e)}")
                return
            
        except Exception as e:
            logger.exception(f"Unexpected error in download file tool: {str(e)}")
            yield self.create_text_message(f"Error: {str(e)}")
    
    def _check_file_in_dify_storage(self, filename: str) -> str | None:
        """检查Dify存储中是否已存在相同文件名的文件"""
        try:
            # 方法：尝试从已知的文件URL模式构建URL并验证
            # 由于Dify存储API可能不支持直接查询，我们使用一个简单的启发式方法
            # 如果文件名包含已知的模式，可以尝试构建URL
            
            # 注意：这是一个简化的实现
            # 在实际使用中，如果Dify存储API支持列表或查询功能，应该使用API
            # 这里我们返回None，表示未找到，继续执行下载
            # 如果需要更精确的检查，可能需要维护一个文件名缓存或使用其他方法
            
            logger.debug(f"Checking if file {filename} exists in Dify storage (simplified check)")
            # 由于无法直接查询Dify存储，这里返回None，继续执行下载
            # 在实际场景中，如果文件已存在，上传时会由Dify存储系统处理（可能覆盖或返回现有URL）
            return None
        except Exception as e:
            logger.warning(f"Failed to check file in Dify storage: {str(e)}")
            return None

