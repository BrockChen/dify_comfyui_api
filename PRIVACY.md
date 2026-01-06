## Privacy Policy

### Data Handling

This plugin processes data in the following ways:

1. **Workflow Data**: The plugin receives workflow JSON objects from Dify and forwards them to your configured ComfyUI server. The workflow data is sent directly to your ComfyUI instance and is not stored by the plugin.

2. **Image Data**: 
   - Input images are downloaded from Dify storage and uploaded to your ComfyUI server
   - Output images are downloaded from your ComfyUI server and uploaded to Dify storage
   - Images are temporarily processed in memory during transfer but are not permanently stored by the plugin

3. **Server Credentials**: 
   - ComfyUI server URL and authentication keys are stored securely in Dify's credential management system
   - Credentials are only used to authenticate requests to your ComfyUI server
   - Credentials are never shared with third parties

### Communication

- The plugin communicates directly with your configured ComfyUI server
- All communication uses standard HTTP/HTTPS and WebSocket protocols
- If authentication is configured, credentials are sent as Bearer tokens in request headers
- No data is sent to any third-party services except your own ComfyUI server

### Storage

- Images are stored in Dify's storage system (as configured in your Dify instance)
- The plugin does not maintain its own persistent storage
- All data processing is ephemeral and occurs only during workflow execution

### Security

- All network communications should use HTTPS when possible
- Authentication keys are handled securely through Dify's credential management
- The plugin does not log or store sensitive information

### User Responsibility

- Users are responsible for ensuring their ComfyUI server is properly secured
- Users should use HTTPS for ComfyUI server connections in production environments
- Users should keep their authentication keys secure and rotate them regularly

### Compliance

This plugin processes data according to Dify's privacy and security standards. For more information about Dify's data handling practices, please refer to Dify's privacy policy.
