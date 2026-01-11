import json
import uuid
from collections.abc import Generator
from typing import Any

import requests

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

from .utils import (
    get_logger,
    get_credentials,
    validate_server_url,
    prepare_headers,
    upload_file_to_comfyui
)

logger = get_logger(__name__)


class ComfyuiSubmitTool(Tool):
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage]:
        try:
            # 获取 workflow JSON
            workflow = tool_parameters.get("workflow_api")
            if not workflow:
                logger.error("workflow_api parameter is required")
                yield self.create_text_message("Error: workflow_api parameter is required")
                raise ValueError("workflow_api parameter is required")
            
            # 验证 workflow 格式
            if not isinstance(workflow, dict):
                try:
                    workflow = json.loads(workflow) if isinstance(workflow, str) else workflow
                except json.JSONDecodeError:
                    logger.error("workflow_api must be a valid JSON object")
                    yield self.create_text_message("Error: workflow_api must be a valid JSON object")
                    raise ValueError("workflow_api must be a valid JSON object")
            
            logger.info("Starting workflow submission")
            
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
            
            # 处理输入图片：查找 LoadImage 节点并上传图片
            workflow = self._process_input_images(workflow, server_url, headers)
            
            # 生成客户端 ID
            client_id = str(uuid.uuid4())
            logger.debug(f"Generated client_id: {client_id}")
            
            # 提交工作流
            prompt_id = self._queue_prompt(workflow, server_url, headers, client_id)
            if not prompt_id:
                logger.error("Failed to queue prompt")
                yield self.create_text_message("Error: Failed to queue prompt")
                raise Exception(f"Failed to queue prompt: {str(e)}")
            
            logger.info(f"Workflow submitted successfully. prompt_id: {prompt_id}, client_id: {client_id}")
            
            yield self.create_variable_message("prompt_id", prompt_id)
            yield self.create_variable_message("client_id", client_id)
            yield self.create_variable_message("status", "submitted")
            # 返回 prompt_id 和 client_id
            yield self.create_json_message({
                "prompt_id": prompt_id,
                "client_id": client_id,
                "status": "submitted",
                "message": "Workflow submitted successfully. Use the query tool with this prompt_id to check status and get results."
            })
            
        except Exception as e:
            logger.exception(f"Unexpected error in submit tool: {str(e)}")
            yield self.create_text_message(f"Error: {str(e)}")
            raise e
    
    def _process_input_images(self, workflow: dict[str, Any], server_url: str, headers: dict[str, str]) -> dict[str, Any]:
        """处理输入图片：查找 LoadImage 节点，从 Dify 存储下载并上传到 ComfyUI"""
        if "prompt" not in workflow:
            return workflow
        
        prompt = workflow["prompt"]
        
        # 查找所有 LoadImage 节点
        for node_id, node_data in prompt.items():
            if isinstance(node_data, dict) and node_data.get("class_type") == "LoadImage":
                # 检查是否有图片输入（可能是从 Dify 存储来的 URL）
                inputs = node_data.get("inputs", {})
                image_param = inputs.get("image")
                
                # 如果 image 是字符串（可能是 Dify 存储 URL），需要下载并上传
                if isinstance(image_param, str) and image_param.startswith(("http://", "https://")):
                    # 检查是否是 Dify 存储 URL（需要从存储下载）
                    try:
                        logger.debug(f"Processing input image for node {node_id}: {image_param}")
                        # 从 Dify 存储下载图片
                        image_data = self.session.storage.download_file(image_param)
                        logger.debug(f"Downloaded image from Dify storage. Size: {len(image_data)} bytes")
                        
                        # 上传到 ComfyUI
                        comfyui_image_path = self._upload_image_to_comfyui(
                            image_data, server_url, headers
                        )
                        
                        if comfyui_image_path:
                            # 更新 workflow 中的图片路径
                            # ComfyUI 的 LoadImage 节点期望格式：["filename", subfolder]
                            inputs["image"] = comfyui_image_path
                            logger.debug(f"Updated node {node_id} image path to: {comfyui_image_path}")
                        else:
                            logger.warning(f"Failed to upload image for node {node_id}, keeping original value")
                    except Exception as e:
                        # 如果下载失败，保持原值
                        logger.warning(f"Failed to process input image for node {node_id}: {str(e)}")
                        pass
        
        return workflow
    
    def _upload_image_to_comfyui(self, image_data: bytes, server_url: str, headers: dict[str, str]) -> str | None:
        """上传图片到 ComfyUI"""
        try:
            # 使用公共工具函数上传文件
            result = upload_file_to_comfyui(
                image_data, "image.png", "image", "", server_url, headers, logger
            )
            
            if result:
                # ComfyUI 返回格式：{"name": "filename", "subfolder": "subfolder", "type": "input"}
                # LoadImage 节点需要格式：["filename", "subfolder"]
                filename = result.get("filename")
                subfolder = result.get("subfolder", "")
                if filename:
                    return [filename, subfolder] if subfolder else filename
            return None
        except Exception as e:
            logger.error(f"Failed to upload image to ComfyUI: {str(e)}")
            return None
    
    def _queue_prompt(self, workflow: dict[str, Any], server_url: str, headers: dict[str, str], client_id: str) -> str | None:
        """提交工作流到 ComfyUI"""
        # try:
        payload = {
            "prompt": workflow.get("prompt", workflow),
            "client_id": client_id
        }
        
        logger.debug(f"Submitting workflow to {server_url}/prompt")
        response = requests.post(
            f"{server_url}/prompt",
            json=payload,
            headers=headers,
            timeout=30
        )
        response.raise_for_status()
        result = response.json()
        prompt_id = result.get("prompt_id")
        if prompt_id:
            logger.debug(f"Workflow queued successfully. prompt_id: {prompt_id}")
        return prompt_id
        # except requests.exceptions.RequestException as e:
        #     logger.error(f"Failed to queue prompt: {str(e)}")
        #     return None
        # except Exception as e:
        #     logger.exception(f"Unexpected error queueing prompt: {str(e)}")
        #     return None

