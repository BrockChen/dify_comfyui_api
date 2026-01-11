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
    check_file_exists,
    download_file_from_dify,
    upload_file_to_comfyui
)

logger = get_logger(__name__)


class ComfyuiUploadFileTool(Tool):
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage]:
        try:
            # 获取参数
            file = tool_parameters.get('input')
            if not file:
                logger.error("input parameter is required")
                yield self.create_text_message("Error: input parameter is required")
                raise ValueError("input parameter is required")
            # 获取凭据
            server_url, auth_key = get_credentials(self.runtime)
            
            if not validate_server_url(server_url):
                logger.error("ComfyUI server URL is not configured")
                yield self.create_text_message("Error: ComfyUI server URL is not configured")
                raise ValueError("ComfyUI server URL is not configured")
            
            logger.info(f"ComfyUI server URL: {server_url}, {file}")
            
            # 准备请求头
            headers = prepare_headers(auth_key)
            if auth_key:
                logger.debug("Using authentication key")

            # file.url
            # file.mime_type
            # file.type
            # file.filename
            
            subfolder = ""
    
            existing_file = check_file_exists(server_url, headers, file.filename, subfolder, "input", logger)
            if existing_file:
                logger.info(f"File {file.filename} already exists in ComfyUI. Skipping upload.")
                file_info = {
                    "status": "success",
                    "filename": file.filename,
                    "mime_type": file.type,
                    "subfolder": subfolder,
                    "type": "input",
                    "url": file.url,
                    "skipped": True,
                    "message": "File already exists in ComfyUI. Skipping upload."
                }
                # yield self.create_json_message(file_info)
                yield self.create_variable_message(
                    "data", file_info
                )
                
                raise ValueError("File already exists in ComfyUI. Skipping upload.")
            
            file_data = download_file_from_dify(file.url)
            if not file_data:
                logger.error("Failed to download file from Dify")
                yield self.create_text_message("Error: Failed to download file from Dify")
                raise ValueError("Failed to download file from Dify")
            # 上传文件到ComfyUI
            upload_result = upload_file_to_comfyui(
                file_data, file.filename, file.mime_type, file.type, subfolder, server_url, headers, logger
            )
            
            if not upload_result:
                logger.error("Failed to upload file to ComfyUI")
                yield self.create_text_message("Error: Failed to upload file to ComfyUI")
                raise ValueError("Failed to upload file to ComfyUI")
            
            logger.info(f"File uploaded successfully. Result: {upload_result}")
            yield self.create_variable_message("data", {
                "status": "success",
                "filename": upload_result.get("filename", file.filename),
                "mime_type": upload_result.get("mime_type", file.mime_type),
                "subfolder": upload_result.get("subfolder", subfolder),
                "type": upload_result.get("type", "input"),
                "url": upload_result.get("url", ""),
                "skipped": False,
                "message": "File uploaded successfully to ComfyUI. Skipping upload."
            })
            return
        except Exception as e:
            logger.exception(f"Unexpected error in upload file tool: {str(e)}")
            yield self.create_text_message(f"Error: {str(e)}")
            raise e
