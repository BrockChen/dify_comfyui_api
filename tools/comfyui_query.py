import time
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
    build_view_url,
    get_history,
    process_outputs
)

logger = get_logger(__name__)

class ComfyuiQueryTool(Tool):
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage]:
        try:
            # 获取 prompt_id
            prompt_id = tool_parameters.get("prompt_id")
            if not prompt_id:
                logger.error("prompt_id parameter is required")
                yield self.create_text_message("Error: prompt_id parameter is required")
                return
            
            logger.info(f"Starting query for prompt_id: {prompt_id}")
            
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
            
            # HTTP 轮询直到任务完成或超时
            max_wait_time = 600  # 最多等待 10 分钟
            poll_interval = 10  # 每 10 秒轮询一次
            start_time = time.time()
            
            logger.info(f"Starting polling loop. Max wait time: {max_wait_time}s, Poll interval: {poll_interval}s")
            
            history = None
            poll_count = 0
            
            # 轮询队列状态，直到任务完成
            while (time.time() - start_time) < max_wait_time:
                elapsed_time = time.time() - start_time
                poll_count += 1
                
                logger.debug(f"Poll attempt #{poll_count}, Elapsed time: {elapsed_time:.2f}s, Prompt ID: {prompt_id}")
                
                # 先检查队列状态
                queue_status = self._get_queue_status(server_url, headers, prompt_id)
                
                if queue_status:
                    status = queue_status.get("status")
                    # 任务还在运行或等待中
                    logger.debug(f"Workflow is still {status}. Waiting {poll_interval}s before next poll...")
                    time.sleep(poll_interval)
                    continue
                
                # 任务不在队列中，说明已完成，从History获取结果
                logger.debug(f"Prompt_id {prompt_id} not found in queue. Checking history...")
                history = get_history(server_url, headers, prompt_id, logger)
                
                if history:
                    logger.info(f"Found prompt_id {prompt_id} in history after {elapsed_time:.2f}s ({poll_count} polls)")
                    
                    # 任务已完成，检查是否有错误
                    
                    status = history.get("status", {})
                    status_str = status.get("status_str")
                    
                    logger.debug(f"Prompt data status: {status_str}, Full status: {status}")
                    
                    if status_str == "error":
                        error_msg = status.get("error", "Unknown error")
                        logger.error(f"Workflow execution failed. Error: {error_msg}")
                        yield self.create_text_message(f"Error: Workflow execution failed - {error_msg}")
                        return
                    
                    # 任务成功完成
                    logger.info(f"Workflow completed successfully. Processing output images...")
                    break
                else:
                    # 既不在队列中，也不在历史记录中，可能是刚提交还没进入队列，继续等待
                    logger.debug(f"Prompt_id {prompt_id} not found in queue or history yet. Waiting {poll_interval}s before next poll...")
                    time.sleep(poll_interval)
                    continue
            
            # 如果超时仍未完成
            elapsed_time = time.time() - start_time
            if not history:
                # 最后再检查一次队列状态
                queue_status = self._get_queue_status(server_url, headers, prompt_id)
                if queue_status:
                    status = queue_status.get("status")
                    logger.warning(f"Timeout after {elapsed_time:.2f}s ({poll_count} polls). Prompt_id {prompt_id} still in queue with status: {status}")
                    yield self.create_json_message({
                        "status": "running",
                        "message": f"Workflow is still running after {elapsed_time:.2f}s. Status: {status}"
                    })
                else:
                    logger.warning(f"Timeout after {elapsed_time:.2f}s ({poll_count} polls). Prompt_id {prompt_id} not found in queue or history")
                    yield self.create_json_message({
                        "status": "timeout",
                        "message": f"Workflow execution timeout after {elapsed_time:.2f}s. It may still be running or has been removed from history."
                    })
                return
            
            # 处理输出图片：下载并上传到 Dify 存储
            logger.info("Processing output images...")
            output_result = process_outputs(history, server_url, prompt_id, logger)
            
            logger.info(f"Query completed successfully. Found {len(output_result.get('outputs', []))} outputs")
            yield self.create_variable_message("status", output_result.get("status"))
            yield self.create_variable_message("outputs", output_result.get("outputs"))
            # 返回结果
            yield self.create_json_message(output_result)
            
        except Exception as e:
            logger.exception(f"Unexpected error in query tool: {str(e)}")
            yield self.create_text_message(f"Error: {str(e)}")
    
    def _get_queue_status(self, server_url: str, headers: dict[str, str], prompt_id: str) -> dict[str, Any] | None:
        """通过 HTTP 获取队列状态，检查任务是否在队列中"""
        try:
            # ComfyUI 的 /queue 端点返回队列状态
            # 格式: {"queue_running": [...], "queue_pending": [...]}
            url = f"{server_url}/queue"
            logger.debug(f"Requesting queue status from: {url}")
            
            response = requests.get(
                url,
                headers=headers,
                timeout=10
            )
            response.raise_for_status()
            queue_data = response.json()
            
            if not isinstance(queue_data, dict):
                logger.warning(f"Queue API returned unexpected format: {type(queue_data)}")
                return None
            
            # 检查运行中的队列
            queue_running = queue_data.get("queue_running", [])
            for item in queue_running:
                if isinstance(item, list) and len(item) >= 2:
                    item_prompt_id = item[1]
                    if item_prompt_id == prompt_id:
                        logger.debug(f"Found prompt_id {prompt_id} in queue_running")
                        return {
                            "status": "running"
                        }
            
            # 检查等待中的队列
            queue_pending = queue_data.get("queue_pending", [])
            for item in queue_pending:
                if isinstance(item, list) and len(item) >= 2:
                    # 尝试从第二个元素（prompt_data）获取prompt_id
                    item_prompt_id = item[1]
                    
                    if item_prompt_id == prompt_id:
                        logger.debug(f"Found prompt_id {prompt_id} in queue_pending")
                        return {
                            "status": "pending"
                        }
            
            logger.debug(f"Prompt_id {prompt_id} not found in queue")
            return None
        except requests.exceptions.Timeout:
            logger.warning(f"Queue API request timeout for prompt_id: {prompt_id}")
            return None
        except requests.exceptions.RequestException as e:
            logger.warning(f"Queue API request failed: {str(e)}")
            return None
        except Exception as e:
            logger.exception(f"Unexpected error in _get_queue_status: {str(e)}")
            return None
    
