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
    download_file_from_comfyui,
    get_history,
    process_outputs
)

logger = get_logger(__name__)


class ComfyuiDownloadFileTool(Tool):
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage]:
        try:
            # 获取参数
            prompt_id = tool_parameters.get("prompt_id")
            if not prompt_id:
                logger.error("prompt_id parameter is required")
                yield self.create_text_message("Error: prompt_id parameter is required")
                raise ValueError("prompt_id parameter is required")
            
            logger.info(f"Starting download for prompt_id: {prompt_id}")
            
            # 获取凭据
            server_url, auth_key = get_credentials(self.runtime)
            
            if not validate_server_url(server_url):
                logger.error("ComfyUI server URL is not configured")
                yield self.create_text_message("Error: ComfyUI server URL is not configured")
                raise ValueError("ComfyUI server URL is not configured")
            
            logger.info(f"ComfyUI server URL: {server_url}")
            
            # 准备请求头
            headers = prepare_headers(auth_key)
            if auth_key:
                logger.debug("Using authentication key")
            
            # 从历史记录中获取工作流输出
            logger.info(f"Fetching history for prompt_id: {prompt_id}")
            client_id = tool_parameters.get("client_id")
            history = get_history(server_url, headers, prompt_id, logger, client_id)
            
            if not history:
                logger.error(f"Prompt_id {prompt_id} not found in history")
                yield self.create_text_message(f"Error: Prompt_id {prompt_id} not found in history. The workflow may not have completed yet.")
                raise ValueError(f"Prompt_id {prompt_id} not found in history. The workflow may not have completed yet.")
            
            # 检查是否有错误
            status = history.get("status", {})
            status_str = status.get("status_str")
            
            if status_str == "error":
                error_msg = status.get("error", "Unknown error")
                logger.error(f"Workflow execution failed. Error: {error_msg}")
                yield self.create_text_message(f"Error: Workflow execution failed - {error_msg}")
                raise ValueError(f"Workflow execution failed - {error_msg}")
            
            # 处理输出，获取文件列表
            logger.info("Processing outputs to get file list")
            output_result = process_outputs(history, server_url, prompt_id, logger)
            
            outputs = output_result.get("outputs", [])
            if not outputs:
                logger.warning(f"No outputs found for prompt_id: {prompt_id}")
                yield self.create_json_message({
                    "status": "success",
                    "prompt_id": prompt_id,
                    "message": "No outputs found",
                    "files": []
                })
                raise ValueError("No outputs found for prompt_id: {prompt_id}")
            
            logger.info(f"Found {len(outputs)} output files to download")
            
            # 下载每个文件并上传到Dify存储
            downloaded_files = []
            failed_files = []
            
            for idx, output_info in enumerate(outputs, 1):
                filename = output_info.get("filename")
                subfolder = output_info.get("subfolder", "")
                file_type = output_info.get("type", "output")
                
                logger.info(f"Downloading file {idx}/{len(outputs)}: {filename}")
                
                try:
                    # 从ComfyUI下载文件
                    file_data = download_file_from_comfyui(
                        filename, subfolder, file_type, server_url, headers, logger
                    )
                    
                    if not file_data:
                        logger.error(f"Failed to download file: {filename}")
                        failed_files.append({
                            "filename": filename,
                            "error": "Failed to download from ComfyUI"
                        })
                        continue
                    
                    logger.info(f"Downloaded file: {filename}, Size: {len(file_data)} bytes")
                    
                    # 确定MIME类型
                    mime_type = get_mime_type(filename)
                    
                    # 使用 create_blob_message 返回文件（会自动上传到Dify存储）
                    try:
                        yield self.create_blob_message(
                            blob=file_data,
                            meta={
                                "mime_type": mime_type,
                                "filename": filename
                            }
                        )
                        
                        logger.info(f"File returned as blob message: {filename}")
                        
                        downloaded_files.append({
                            "filename": filename,
                            "comfyui_url": output_info.get("url"),
                            "size": len(file_data),
                            "mime_type": mime_type
                        })
                        
                    except Exception as e:
                        logger.error(f"Failed to create blob message for {filename}: {str(e)}")
                        failed_files.append({
                            "filename": filename,
                            "error": f"Failed to create blob message: {str(e)}"
                        })
                        continue
                        
                except Exception as e:
                    logger.exception(f"Unexpected error processing file {filename}: {str(e)}")
                    failed_files.append({
                        "filename": filename,
                        "error": str(e)
                    })
                    continue
            
            # 准备返回结果
            result = {
                "status": "success" if downloaded_files else "failed",
                "prompt_id": prompt_id,
                "total_files": len(outputs),
                "downloaded": len(downloaded_files),
                "failed": len(failed_files),
                "files": downloaded_files
            }
            
            if failed_files:
                result["failed_files"] = failed_files
            
            logger.info(f"Download completed. Downloaded: {len(downloaded_files)}/{len(outputs)}, Failed: {len(failed_files)}")
            
            # 返回完整结果
            yield self.create_json_message(result)
            
        except Exception as e:
            logger.exception(f"Unexpected error in download file tool: {str(e)}")
            yield self.create_text_message(f"Error: {str(e)}")
            raise e