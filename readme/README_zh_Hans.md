## ComfyUI API 插件

**作者:** brockchen  
**版本:** 0.1.0  
**类型:** 工具

### 描述

一个集成 ComfyUI 的 Dify 插件，用于执行工作流和处理图片。该插件自动处理 Dify 存储和 ComfyUI 之间的图片传输，使您可以在 Dify 应用中轻松使用 ComfyUI 工作流。

### 功能特性

- 通过提供工作流 JSON 对象执行 ComfyUI 工作流
- 自动从 Dify 存储上传图片到 ComfyUI
- 自动从 ComfyUI 下载图片到 Dify 存储
- 基于 WebSocket 的实时执行监控
- 支持 ComfyUI 服务器认证

### 安装

1. 从 Dify 插件市场安装插件
2. 配置您的 ComfyUI 服务器地址
3. 如果您的 ComfyUI 服务器需要认证，可选配置认证密钥

### 配置

#### Provider 凭据

1. **ComfyUI 服务器地址**（必填）
   - 您的 ComfyUI 服务器 URL
   - 示例：`http://127.0.0.1:8188`
   - 格式：`http://` 或 `https://` 后跟主机和端口

2. **认证密钥**（可选）
   - 如果您的 ComfyUI 服务器需要认证，请在此提供密钥
   - 密钥将作为 Bearer token 在 Authorization 头中发送

### 使用方法

#### 工具参数

- **workflow_api**（对象，必填）：要执行的 ComfyUI 工作流 JSON 对象

#### 工作流 JSON 格式

工作流 JSON 应遵循 ComfyUI 的工作流格式。以下是一个基本示例：

```json
{
  "prompt": {
    "1": {
      "inputs": {
        "text": "一幅美丽的风景"
      },
      "class_type": "CLIPTextEncode",
      "_meta": {
        "title": "CLIP Text Encode (Prompt)"
      }
    },
    "2": {
      "inputs": {
        "seed": 12345,
        "steps": 20,
        "cfg": 8,
        "sampler_name": "euler",
        "scheduler": "normal",
        "denoise": 1,
        "model": ["4", 0],
        "positive": ["1", 0],
        "negative": ["3", 0],
        "latent_image": ["5", 0]
      },
      "class_type": "KSampler",
      "_meta": {
        "title": "KSampler"
      }
    }
  }
}
```

#### 图片处理

当您的工作流包含 `LoadImage` 节点时，插件将：

1. 检测工作流中来自 Dify 存储的图片 URL
2. 从 Dify 存储下载图片
3. 上传图片到 ComfyUI
4. 将工作流中的图片路径替换为 ComfyUI 兼容的路径

执行完成后，输出图片将：

1. 从 ComfyUI 下载
2. 上传到 Dify 存储
3. 在结果中作为 URL 返回

#### 示例结果

```json
{
  "status": "success",
  "images": [
    {
      "node_id": "10",
      "filename": "ComfyUI_00001_.png",
      "url": "https://dify-storage.example.com/files/..."
    }
  ]
}
```

### 工作原理

1. **工作流提交**：插件将您的工作流 JSON 提交到 ComfyUI 的 `/prompt` 端点
2. **执行监控**：WebSocket 连接实时监控执行进度
3. **图片处理**：
   - 输入图片自动从 Dify 存储上传到 ComfyUI
   - 输出图片自动从 ComfyUI 下载并上传到 Dify 存储
4. **结果返回**：插件返回一个包含状态和生成图片 URL 的 JSON 对象

### 要求

- ComfyUI 服务器正在运行且可访问
- Dify 和 ComfyUI 服务器之间的网络连接
- Dify 中有足够的存储配额用于图片存储

### 故障排除

- **连接错误**：验证 ComfyUI 服务器 URL 是否正确以及服务器是否正在运行
- **认证错误**：如果您的服务器需要认证，请检查您的认证密钥是否正确
- **超时错误**：复杂的工作流可能需要更长时间执行。插件有 5 分钟的超时时间
- **图片上传错误**：确保工作流中的图片可以从 Dify 存储访问

### 支持

如有问题和疑问，请访问 GitHub 上的插件仓库。
