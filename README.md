# comfyui-agent-skills

A collection of skills (currently featuring comfyui-operator) that enables AI agents to natively interact with a local ComfyUI installation.

## comfyui-operator

The comfyui-operator skill allows your AI agent (Claude, Cursor, Antigravity, etc.) to control your local ComfyUI instance. It can auto-start the server, interrogate available models/workflows, and dynamically generate images by injecting prompts through the ComfyUI API.

### Installation

```bash
npx skills add https://github.com/hrdtbs/comfyui-agent-skills --skill comfyui-operator
```

### Prompt Examples

```txt
I want to generate a YouTube thumbnail.
```

Agent: Search for workflows that seem to be for YouTube thumbnails and execute them.

```txt
I want to generate an image.
```

Agent: Search for API Format workflows and ask the user which one to execute.

### Features

- Auto-Detection: Automatically detects both the standard Windows Portable (C:\ComfyUI_windows_portable) and the official ComfyUI Desktop App (via %LOCALAPPDATA% and %APPDATA% configs) without needing manual configuration.
- Resource Management: Automatically discovers and lists your available Checkpoints, LoRAs, and Workflows (scripts/list_resources.py).
- Dynamic Image Generation: Modifies and queues workflows via WebSocket API (scripts/generate_image.py).
- Prompt Safety: Enforces rules preventing agents from destructively overwriting complex baseline prompts, ensuring tags are safely appended unless explicitly requested otherwise.
- Seed Safety: Enforces rules preventing agents from randomizing seeds unless batch generation is requested, preserving your workflow's established compositions.

### Constraints & Known Limitations

To use this skill effectively, please be aware of the following technical constraints:

1. API Format Workflow Requirement:
   - The provided Python script (generate_image.py) communicates directly with the ComfyUI WebSocket/HTTP backend.
   - It cannot parse standard UI saved workflows. 
   - You must save your base workflow JSON by selecting "Save (API Format)" in the ComfyUI interface. If this option is missing, enable "Enable Dev mode Options" in the ComfyUI settings gear menu.
   - Note: Ensure all node connections (especially VAE connections that might be hidden by custom nodes like Anything Everywhere) are explicitly linked and established before saving the API Format JSON.

2. Desktop Application Background Limit:
   - If you are running the official ComfyUI Desktop App (Electron version), the script will launch it using the standard ComfyUI.exe.
   - Due to complex dependency handling and custom node paths deeply integrated within the Electron runtime, headless (background) execution is currently not supported for the Desktop App install. The ComfyUI application window will visibly open.
   - (Users of the Portable zip install running run_nvidia_gpu.bat via scripts can still be launched in the background without a visible UI).

### Usage (For Agents)

Once installed, agents can interact with the skill directly. If you want to use the scripts manually:

```bash
# 1. Start ComfyUI Server
python comfyui-operator/scripts/start_comfyui.py

# 2. Check Available Resources
python comfyui-operator/scripts/list_resources.py \
    --output "<workspace>/.comfyui/resources.json"

# 3. Generate an Image (with dynamic overrides)
python comfyui-operator/scripts/generate_image.py \
    --workflow_path "path/to/workflow_api.json" \
    --output_dir "<workspace>/.comfyui/outputs" \
    --overrides '{"6": {"inputs": {"text": "A beautiful sunset..."}}}'
```
Note: Agents are instructed to save all generated files (resources and images) to the `.comfyui/` directory of the active workspace.