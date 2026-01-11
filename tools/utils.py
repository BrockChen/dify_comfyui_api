"""公共工具函数模块，用于减少代码重复"""
import os
import mimetypes
from typing import Any
from urllib.parse import urlencode

import requests

import logging
from dify_plugin.config.logger_format import plugin_logger_handler


def get_logger(name: str) -> logging.Logger:
    """获取配置好的日志记录器"""
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    logger.addHandler(plugin_logger_handler)
    return logger


def get_credentials(runtime: Any) -> tuple[str, str | None]:
    """
    从运行时获取ComfyUI凭据
    
    Returns:
        tuple: (server_url, auth_key)
    """
    credentials = runtime.credentials
    server_url = credentials.get("comfyui_server_url", "").rstrip("/")
    auth_key = credentials.get("auth_key")
    return server_url, auth_key


def validate_server_url(server_url: str) -> bool:
    """验证服务器URL是否配置"""
    return bool(server_url)


def prepare_headers(auth_key: str | None) -> dict[str, str]:
    """
    准备HTTP请求头
    
    Args:
        auth_key: 认证密钥
        
    Returns:
        包含Authorization头的字典（如果有auth_key）
    """
    headers = {}
    if auth_key:
        headers["Authorization"] = f"Bearer {auth_key}"
    return headers


def build_view_url(server_url: str, filename: str, subfolder: str = "", file_type: str = "") -> str:
    """
    构建ComfyUI文件查看URL
    
    Args:
        server_url: ComfyUI服务器URL
        filename: 文件名
        subfolder: 子文件夹（可选）
        file_type: 文件类型（可选）
        
    Returns:
        完整的查看URL
    """
    params = {
        "filename": filename,
        "subfolder": subfolder,
        "type": file_type
    }
    
    # 过滤空值
    filtered_params = {k: v for k, v in params.items() if v}
    query_string = urlencode(filtered_params)
    return f"{server_url}/view?{query_string}"


def get_mime_type(filename: str, default: str = "application/octet-stream") -> str:
    """
    根据文件名获取MIME类型
    
    Args:
        filename: 文件名
        default: 默认MIME类型
        
    Returns:
        MIME类型字符串
    """
    mime_type, _ = mimetypes.guess_type(filename)
    if not mime_type:
        # 根据扩展名设置默认MIME类型
        ext = os.path.splitext(filename)[1].lower()
        mime_map = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".webp": "image/webp",
            ".mp4": "video/mp4",
            ".avi": "video/x-msvideo",
            ".mov": "video/quicktime",
            ".mkv": "video/x-matroska",
            ".webm": "video/webm"
        }
        mime_type = mime_map.get(ext, default)
    return mime_type


def detect_file_type(filename: str) -> str:
    """
    根据文件名自动检测文件类型（image/video）
    
    Args:
        filename: 文件名
        
    Returns:
        "image" 或 "video"
    """
    mime_type, _ = mimetypes.guess_type(filename)
    if mime_type:
        if mime_type.startswith("image/"):
            return "image"
        elif mime_type.startswith("video/"):
            return "video"
    
    # 根据文件扩展名判断
    ext = os.path.splitext(filename)[1].lower()
    video_extensions = [".mp4", ".avi", ".mov", ".mkv", ".webm"]
    if ext in video_extensions:
        return "video"
    
    # 默认作为图片处理
    return "image"

def download_file_from_dify(file_url: str) -> bytes:
    """
    从Dify下载文件
    """
    response = requests.get(file_url)
    response.raise_for_status()
    return response.content

def check_file_exists(server_url: str, headers: dict[str, str], filename: str, 
                     subfolder: str = "", file_type: str = "input", 
                     logger: logging.Logger | None = None) -> dict[str, Any] | None:
    """
    检查ComfyUI中是否已存在文件
    
    Args:
        server_url: ComfyUI服务器URL
        headers: HTTP请求头
        filename: 文件名
        subfolder: 子文件夹
        file_type: 文件类型
        logger: 日志记录器（可选）
        
    Returns:
        如果文件存在，返回文件信息字典；否则返回None
    """
    try:
        url = build_view_url(server_url, filename, subfolder, file_type)
        
        if logger:
            logger.debug(f"Checking if file exists: {url}")
        
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            if logger:
                logger.debug(f"File {filename} exists in ComfyUI")
            return {
                "filename": filename,
                "subfolder": subfolder,
                "type": file_type,
                "url": url
            }
        else:
            if logger:
                logger.debug(f"File {filename} does not exist in ComfyUI (status: {response.status_code})")
            return None
    except requests.exceptions.RequestException as e:
        if logger:
            logger.warning(f"Failed to check file existence: {str(e)}")
        return None
    except Exception as e:
        if logger:
            logger.warning(f"Unexpected error checking file existence: {str(e)}")
        return None


def upload_file_to_comfyui(file_data: bytes, filename: str, file_type: str, 
                           subfolder: str, server_url: str, headers: dict[str, str],
                           logger: logging.Logger | None = None) -> dict[str, Any] | None:
    """
    上传文件到ComfyUI
    
    Args:
        file_data: 文件数据（字节）
        filename: 文件名
        file_type: 文件类型（"image" 或 "video"）
        subfolder: 子文件夹
        server_url: ComfyUI服务器URL
        headers: HTTP请求头
        logger: 日志记录器（可选）
        
    Returns:
        上传结果字典，包含filename、subfolder、type、url；失败返回None
    """
    try:
        # 根据文件类型选择上传端点
        if file_type == "video":
            upload_url = f"{server_url}/upload/video"
            files = {"video": (filename, file_data, "video/mp4")}
        else:
            upload_url = f"{server_url}/upload/image"
            mime_type = get_mime_type(filename, "image/png")
            files = {"image": (filename, file_data, mime_type)}
        
        # 如果有子文件夹，添加到表单数据
        data = {}
        if subfolder:
            data["subfolder"] = subfolder
        
        if logger:
            logger.debug(f"Uploading file to {upload_url}, filename: {filename}, subfolder: {subfolder}")
        
        response = requests.post(
            upload_url,
            files=files,
            data=data,
            headers=headers,
            timeout=60
        )
        
        # 如果视频端点不存在，尝试使用图片端点
        if file_type == "video" and response.status_code == 404:
            if logger:
                logger.debug("Video endpoint not found, trying image endpoint")
            upload_url = f"{server_url}/upload/image"
            mime_type = "video/mp4"
            files = {"image": (filename, file_data, mime_type)}
            response = requests.post(
                upload_url,
                files=files,
                data=data,
                headers=headers,
                timeout=60
            )
        
        response.raise_for_status()
        result = response.json()
        
        # ComfyUI返回格式：{"name": "filename", "subfolder": "subfolder", "type": "input"}
        if "name" in result:
            uploaded_filename = result["name"]
            uploaded_subfolder = result.get("subfolder", "")
            uploaded_type = result.get("type", "input")
            
            # 构建文件URL
            file_url = build_view_url(server_url, uploaded_filename, uploaded_subfolder, uploaded_type)
            
            return {
                "filename": uploaded_filename,
                "subfolder": uploaded_subfolder,
                "type": uploaded_type,
                "url": file_url
            }
        
        return None
    except requests.exceptions.RequestException as e:
        if logger:
            logger.error(f"Failed to upload file to ComfyUI: {str(e)}")
        return None
    except Exception as e:
        if logger:
            logger.exception(f"Unexpected error uploading file: {str(e)}")
        return None


def download_file_from_comfyui(filename: str, subfolder: str, file_type: str,
                               server_url: str, headers: dict[str, str],
                               logger: logging.Logger | None = None) -> bytes | None:
    """
    从ComfyUI下载文件
    
    Args:
        filename: 文件名
        subfolder: 子文件夹
        file_type: 文件类型
        server_url: ComfyUI服务器URL
        headers: HTTP请求头
        logger: 日志记录器（可选）
        
    Returns:
        文件数据（字节）；失败返回None
    """
    try:
        url = build_view_url(server_url, filename, subfolder, file_type)
        
        if logger:
            logger.debug(f"Downloading file from: {url}")
        
        response = requests.get(url, headers=headers, timeout=60, stream=True)
        response.raise_for_status()
        
        file_data = response.content
        
        if logger:
            logger.debug(f"Downloaded {len(file_data)} bytes from ComfyUI")
        
        return file_data
    except requests.exceptions.RequestException as e:
        if logger:
            logger.error(f"Failed to download file from ComfyUI: {str(e)}")
        return None
    except Exception as e:
        if logger:
            logger.exception(f"Unexpected error downloading file: {str(e)}")
        return None


def get_history(server_url: str, headers: dict[str, str], prompt_id: str,
                logger: logging.Logger | None = None, client_id: str = "") -> dict[str, Any] | None:
    """
    通过 HTTP 获取工作流执行历史
    
    Args:
        server_url: ComfyUI服务器URL
        headers: HTTP请求头
        prompt_id: 提示ID
        logger: 日志记录器（可选）
        
    Returns:
        历史记录字典；失败返回None
    """
    try:
        # ComfyUI 的 /history 端点返回所有历史记录
        # 格式: {prompt_id: {...}, ...}
        url = f"{server_url}/history/{prompt_id}?client_id={client_id}"
        if logger:
            logger.debug(f"Requesting history from: {url}")
        
        response = requests.get(
            url,
            headers=headers,
            timeout=10
        )
        response.raise_for_status()
        all_history = response.json()
        
        # 记录历史记录中的 prompt_id 列表（用于调试）
        if isinstance(all_history, dict):
            available_prompt_ids = list(all_history.keys())
            if logger:
                logger.debug(f"History API returned {len(available_prompt_ids)} prompt records. Available IDs: {available_prompt_ids[:10]}...")  # 只显示前10个
            
            # 从所有历史记录中查找对应的 prompt_id
            if prompt_id in all_history:
                if logger:
                    logger.debug(f"Found prompt_id {prompt_id} in history")
                return all_history[prompt_id]
            else:
                if logger:
                    logger.debug(f"Prompt_id {prompt_id} not in available history records")
        else:
            if logger:
                logger.warning(f"History API returned unexpected format: {type(all_history)}")
        
        return None
    except requests.exceptions.Timeout:
        if logger:
            logger.warning(f"History API request timeout for prompt_id: {prompt_id}")
        return None
    except requests.exceptions.RequestException as e:
        if logger:
            logger.warning(f"History API request failed: {str(e)}")
        return None
    except Exception as e:
        if logger:
            logger.exception(f"Unexpected error in get_history: {str(e)}")
        return None


def process_outputs(history: dict[str, Any], server_url: str, 
                   prompt_id: str, logger: logging.Logger | None = None) -> dict[str, Any]:
    """
    处理输出：从历史记录中提取输出文件信息
    
    Args:
        history: 历史记录字典
        server_url: ComfyUI服务器URL
        prompt_id: 提示ID
        logger: 日志记录器（可选）
        
    Returns:
        输出结果字典，包含status、prompt_id和outputs列表
    """
    output_result = {
        "status": "success",
        "prompt_id": prompt_id,
        "outputs": []
    }
    
    # 从历史记录中提取输出信息
    if not history:
        if logger:
            logger.warning(f"Prompt_id {prompt_id} not found in history when processing outputs")
        return output_result

    outputs = history.get("outputs", {})
    
    if logger:
        logger.info(f"Found {len(outputs)} output nodes in prompt data")

    for node_id, node_output in outputs.items():
        if logger:
            logger.debug(f"Node {node_id} has {len(node_output)} outputs")
        
        for output_key, output_value in node_output.items():
            if logger:
                logger.debug(f"Processing output {output_key}: {output_value}")
            
            if output_key not in ["images", "video", "audio"]:
                continue
            for output_info in output_value:
                filename = output_info.get("filename")
                subfolder = output_info.get("subfolder", "")
                file_type = output_info.get("type", "output")
                
                output_url = build_view_url(server_url, filename, subfolder, file_type)
                output_result["outputs"].append({
                    "filename": filename,
                    "subfolder": subfolder,
                    "type": file_type,
                    "url": output_url
                })
    return output_result

