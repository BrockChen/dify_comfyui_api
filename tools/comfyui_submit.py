import json
import uuid
from collections.abc import Generator
from typing import Any

import requests

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage


class ComfyuiSubmitTool(Tool):
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage]:
        try:
            # 获取 workflow JSON
            workflow = tool_parameters.get("workflow_api")
            if not workflow:
                yield self.create_text_message("Error: workflow_api parameter is required")
                return
            
            # 验证 workflow 格式
            if not isinstance(workflow, dict):
                try:
                    workflow = json.loads(workflow) if isinstance(workflow, str) else workflow
                except json.JSONDecodeError:
                    yield self.create_text_message("Error: workflow_api must be a valid JSON object")
                    return
            
            # 获取凭据
            credentials = self.runtime.credentials
            server_url = credentials.get("comfyui_server_url", "").rstrip("/")
            auth_key = credentials.get("auth_key")
            
            if not server_url:
                yield self.create_text_message("Error: ComfyUI server URL is not configured")
                return
            
            # 准备请求头
            headers = {}
            if auth_key:
                headers["Authorization"] = f"Bearer {auth_key}"
            
            # 处理输入图片：查找 LoadImage 节点并上传图片
            workflow = self._process_input_images(workflow, server_url, headers)
            
            # 生成客户端 ID
            client_id = str(uuid.uuid4())
            
            # 提交工作流
            prompt_id = self._queue_prompt(workflow, server_url, headers, client_id)
            if not prompt_id:
                yield self.create_text_message("Error: Failed to queue prompt")
                return
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
            yield self.create_text_message(f"Error: {str(e)}")
    
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
                        # 从 Dify 存储下载图片
                        image_data = self.session.storage.download_file(image_param)
                        
                        # 上传到 ComfyUI
                        comfyui_image_path = self._upload_image_to_comfyui(
                            image_data, server_url, headers
                        )
                        
                        if comfyui_image_path:
                            # 更新 workflow 中的图片路径
                            # ComfyUI 的 LoadImage 节点期望格式：["filename", subfolder]
                            inputs["image"] = comfyui_image_path
                    except Exception as e:
                        # 如果下载失败，保持原值
                        pass
        
        return workflow
    
    def _upload_image_to_comfyui(self, image_data: bytes, server_url: str, headers: dict[str, str]) -> str | None:
        """上传图片到 ComfyUI"""
        try:
            files = {"image": ("image.png", image_data, "image/png")}
            response = requests.post(
                f"{server_url}/upload/image",
                files=files,
                headers=headers,
                timeout=30
            )
            response.raise_for_status()
            result = response.json()
            # ComfyUI 返回格式：{"name": "filename", "subfolder": "subfolder", "type": "input"}
            # LoadImage 节点需要格式：["filename", "subfolder"]
            if "name" in result:
                subfolder = result.get("subfolder", "")
                return [result["name"], subfolder] if subfolder else result["name"]
            return None
        except Exception as e:
            return None
    
    def _queue_prompt(self, workflow: dict[str, Any], server_url: str, headers: dict[str, str], client_id: str) -> str | None:
        """提交工作流到 ComfyUI"""
        try:
            payload = {
                "prompt": workflow.get("prompt", workflow),
                "client_id": client_id
            }
            
            response = requests.post(
                f"{server_url}/prompt",
                json=payload,
                headers=headers,
                timeout=30
            )
            response.raise_for_status()
            result = response.json()
            return result.get("prompt_id")
        except Exception as e:
            return None

