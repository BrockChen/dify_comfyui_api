## ComfyUI API Plugin

**Author:** brockchen  
**Version:** 0.1.0  
**Type:** tool

### Description

A Dify plugin that integrates with ComfyUI to execute workflows and process images. This plugin automatically handles image transfers between Dify storage and ComfyUI, making it easy to use ComfyUI workflows within Dify applications.

### Features

- Execute ComfyUI workflows by providing workflow JSON objects
- Automatic image upload from Dify storage to ComfyUI
- Automatic image download from ComfyUI to Dify storage
- WebSocket-based real-time execution monitoring
- Support for ComfyUI server authentication

### Installation

1. Install the plugin from the Dify plugin marketplace
2. Configure the plugin with your ComfyUI server URL
3. Optionally configure authentication key if your ComfyUI server requires it

### Configuration

#### Provider Credentials

1. **ComfyUI Server URL** (Required)
   - The URL of your ComfyUI server
   - Example: `http://127.0.0.1:8188`
   - Format: `http://` or `https://` followed by host and port

2. **Authentication Key** (Optional)
   - If your ComfyUI server requires authentication, provide the key here
   - The key will be sent as a Bearer token in the Authorization header

### Usage

#### Tool Parameters

- **workflow_api** (object, required): The ComfyUI workflow JSON object to execute

#### Workflow JSON Format

The workflow JSON should follow ComfyUI's workflow format. Here's a basic example:

```json
{
  "prompt": {
    "1": {
      "inputs": {
        "text": "a beautiful landscape"
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

#### Image Handling

When your workflow contains `LoadImage` nodes, the plugin will:

1. Detect image URLs from Dify storage in the workflow
2. Download images from Dify storage
3. Upload images to ComfyUI
4. Replace image paths in the workflow with ComfyUI-compatible paths

After execution, output images will be:

1. Downloaded from ComfyUI
2. Uploaded to Dify storage
3. Returned as URLs in the result

#### Example Result

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

### How It Works

1. **Workflow Submission**: The plugin submits your workflow JSON to ComfyUI's `/prompt` endpoint
2. **Execution Monitoring**: A WebSocket connection monitors the execution progress in real-time
3. **Image Processing**: 
   - Input images are automatically uploaded from Dify storage to ComfyUI
   - Output images are automatically downloaded from ComfyUI and uploaded to Dify storage
4. **Result Return**: The plugin returns a JSON object with the status and URLs of generated images

### Requirements

- ComfyUI server running and accessible
- Network connectivity between Dify and ComfyUI server
- Sufficient storage quota in Dify for image storage

### Troubleshooting

- **Connection Errors**: Verify that the ComfyUI server URL is correct and the server is running
- **Authentication Errors**: Check if your authentication key is correct if your server requires authentication
- **Timeout Errors**: Complex workflows may take longer to execute. The plugin has a 5-minute timeout
- **Image Upload Errors**: Ensure that images in your workflow are accessible from Dify storage

### Support

For issues and questions, please visit the plugin repository on GitHub.
