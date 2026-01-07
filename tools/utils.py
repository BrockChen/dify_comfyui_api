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

