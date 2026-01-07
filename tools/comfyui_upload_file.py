import os
from collections.abc import Generator
from typing import Any
from urllib.parse import urlparse

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

from .utils import (
    get_logger,
    get_credentials,
    validate_server_url,
    prepare_headers,
    detect_file_type,
    check_file_exists,
    upload_file_to_comfyui
)

logger = get_logger(__name__)


class ComfyuiUploadFileTool(Tool):
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage]:
        try:
            # 获取参数
            file_url = tool_parameters.get("file_url")
            if not file_url:
                logger.error("file_url parameter is required")
                yield self.create_text_message("Error: file_url parameter is required")
                return
            
            file_type = tool_parameters.get("file_type", "").lower()
            subfolder = tool_parameters.get("subfolder", "")
            
            logger.info(f"Starting file upload. File URL: {file_url}, Type: {file_type}, Subfolder: {subfolder}")
            
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
            
            # 从Dify存储下载文件
            try:
                file_data = self.session.storage.download_file(file_url)
                logger.info(f"Downloaded file from Dify storage. Size: {len(file_data)} bytes")
            except Exception as e:
                logger.error(f"Failed to download file from Dify storage: {str(e)}")
                yield self.create_text_message(f"Error: Failed to download file from Dify storage - {str(e)}")
                return
            
            # 从URL提取文件名
            parsed_url = urlparse(file_url)
            filename = os.path.basename(parsed_url.path)
            if not filename:
                # 如果无法从URL提取，使用默认文件名
                filename = "uploaded_file"
            
            # 自动检测文件类型（如果未指定）
            if not file_type:
                file_type = detect_file_type(filename)
            
            logger.info(f"Detected file type: {file_type}, Filename: {filename}")
            
            # 检查ComfyUI中是否已存在相同文件
            existing_file = check_file_exists(server_url, headers, filename, subfolder, "input", logger)
            if existing_file:
                logger.info(f"File {filename} already exists in ComfyUI. Skipping upload.")
                yield self.create_json_message({
                    "status": "success",
                    "filename": existing_file.get("filename", filename),
                    "subfolder": existing_file.get("subfolder", subfolder),
                    "type": "input",
                    "url": existing_file.get("url", ""),
                    "skipped": True,
                    "message": f"File {filename} already exists in ComfyUI. Upload skipped."
                })
                return
            
            # 上传文件到ComfyUI
            upload_result = upload_file_to_comfyui(
                file_data, filename, file_type, subfolder, server_url, headers, logger
            )
            
            if not upload_result:
                logger.error("Failed to upload file to ComfyUI")
                yield self.create_text_message("Error: Failed to upload file to ComfyUI")
                return
            
            logger.info(f"File uploaded successfully. Result: {upload_result}")
            yield self.create_json_message({
                "status": "success",
                "filename": upload_result.get("filename", filename),
                "subfolder": upload_result.get("subfolder", subfolder),
                "type": "input",
                "url": upload_result.get("url", ""),
                "skipped": False,
                "message": "File uploaded successfully to ComfyUI"
            })
            
        except Exception as e:
            logger.exception(f"Unexpected error in upload file tool: {str(e)}")
            yield self.create_text_message(f"Error: {str(e)}")

