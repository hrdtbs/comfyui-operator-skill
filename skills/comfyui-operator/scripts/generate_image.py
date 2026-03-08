import argparse
import json
import urllib.request
import urllib.parse
import time
import uuid
import websocket
import os
from pathlib import Path

def queue_prompt(prompt, client_id, server_address):
    p = {"prompt": prompt, "client_id": client_id}
    data = json.dumps(p).encode('utf-8')
    req = urllib.request.Request(f"http://{server_address}/prompt", data=data)
    req.add_header('Content-Type', 'application/json')
    try:
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read())
    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8', errors='ignore')
        raise ConnectionError(f"HTTP {e.code}: Failed to queue prompt on {server_address}. Server responded with: {error_body}")
    except urllib.error.URLError as e:
        raise ConnectionError(f"Failed to connect to ComfyUI at {server_address}. Is it running? Error: {e}")

def get_image(filename, subfolder, folder_type, server_address):
    data = {"filename": filename, "subfolder": subfolder, "type": folder_type}
    url_values = urllib.parse.urlencode(data)
    with urllib.request.urlopen(f"http://{server_address}/view?{url_values}") as response:
        return response.read()

def get_history(prompt_id, server_address):
    with urllib.request.urlopen(f"http://{server_address}/history/{prompt_id}") as response:
        return json.loads(response.read())

def get_images(ws, prompt, client_id, server_address):
    prompt_id = queue_prompt(prompt, client_id, server_address)['prompt_id']
    output_images = {}
    while True:
        try:
            out = ws.recv()
            if isinstance(out, str):
                message = json.loads(out)
                if message['type'] == 'executing':
                    data = message['data']
                    if data['node'] is None and data['prompt_id'] == prompt_id:
                        break # Execution is done
            else:
                continue # previews are binary data
        except websocket.WebSocketTimeoutException:
            raise TimeoutError("WebSocket connection timed out while waiting for generation.")
            
    # Generation is complete, retrieve from history
    history = get_history(prompt_id, server_address)[prompt_id]
    for o in history['outputs']:
        for node_id in history['outputs']:
            node_output = history['outputs'][node_id]
            if 'images' in node_output:
                images_output = []
                for image in node_output['images']:
                    image_data = get_image(image['filename'], image['subfolder'], image['type'], server_address)
                    images_output.append({
                        'filename': image['filename'],
                        'data': image_data
                    })
                output_images[node_id] = images_output
                
    return output_images

def get_images_http_fallback(workflow, client_id, server_address):
    res = queue_prompt(workflow, client_id, server_address)
    prompt_id = res['prompt_id']
    print(f"Prompt queued via HTTP fallback. ID: {prompt_id}")
    
    print("Waiting for generation to complete (polling history)...")
    while True:
        try:
            history = get_history(prompt_id, server_address)
            if prompt_id in history:
                break
        except Exception:
            pass
        time.sleep(2)
        
    history_data = history[prompt_id]
    output_images = {}
    
    for node_id in history_data['outputs']:
        node_output = history_data['outputs'][node_id]
        if 'images' in node_output:
            images_output = []
            for image in node_output['images']:
                image_data = get_image(image['filename'], image['subfolder'], image['type'], server_address)
                images_output.append({
                    'filename': image['filename'],
                    'data': image_data
                })
            output_images[node_id] = images_output
    return output_images

def apply_overrides(workflow: dict, overrides: dict) -> dict:
    """Safely applies node overrides based on node ID."""
    for node_id_str, changes in overrides.items():
        if node_id_str in workflow:
            # specifically update inputs
            if "inputs" in changes and "inputs" in workflow[node_id_str]:
                workflow[node_id_str]["inputs"].update(changes["inputs"])
        else:
            print(f"Warning: Node ID {node_id_str} not found in the workflow. Override ignored.")
    return workflow

def find_active_server(default_server="127.0.0.1:8188"):
    servers_to_try = [default_server, "127.0.0.1:8000", "127.0.0.1:8188"]
    for server in set(servers_to_try):
        try:
            req = urllib.request.Request(f"http://{server}/system_stats")
            with urllib.request.urlopen(req, timeout=2) as response:
                if response.status == 200:
                    return server
        except Exception:
            continue
    return default_server

if __name__ == "__main__":
    import sys
    if sys.stdout.encoding.lower() != 'utf-8':
        sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description="Generate image(s) using a ComfyUI API workflow.")
    parser.add_argument("--workflow_path", type=str, required=True, help="Path to the JSON workflow file (API format).")
    parser.add_argument("--output_dir", type=str, default=None, help="Path to save the generated image(s). Defaults to the workspace root.")
    parser.add_argument("--overrides", type=str, default="{}", help="JSON string representing node overrides.")
    parser.add_argument("--overrides_file", type=str, default=None, help="Path to a JSON file containing node overrides. Recommended on Windows to avoid shell quote stripping.")
    parser.add_argument("--comfyui_path", type=str, default=r"C:\ComfyUI_windows_portable", help="Path to ComfyUI (used for error context if needed, but not directly for API).")
    parser.add_argument("--server", type=str, default="127.0.0.1:8188", help="ComfyUI server address.")

    args = parser.parse_args()
    
    # If not provided, save to the current working directory
    if args.output_dir is None:
        args.output_dir = os.getcwd()

    # Load workflow
    try:
        with open(args.workflow_path, "r", encoding="utf-8") as f:
            workflow = json.load(f)
    except FileNotFoundError:
        print(f"Error: Workflow file not found at {args.workflow_path}")
        exit(1)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in workflow file: {e}")
        exit(1)

    # Parse overrides
    overrides = {}
    if args.overrides_file:
        try:
            with open(args.overrides_file, "r", encoding="utf-8") as f:
                overrides = json.load(f)
        except Exception as e:
            print(f"Error reading overrides file {args.overrides_file}: {e}")
            exit(1)

    try:
        cli_overrides = json.loads(args.overrides)
        overrides.update(cli_overrides)
    except json.JSONDecodeError as e:
        if args.overrides != "{}":
            print(f"Error: Invalid JSON string provided for --overrides: {e}")
            print("Tip: If you are seeing JSON decode errors on Windows, we heavily recommend using --overrides_file instead.")
            exit(1)

    # Apply overrides
    workflow = apply_overrides(workflow, overrides)

    # Ensure output directory exists
    os.makedirs(args.output_dir, exist_ok=True)

    client_id = str(uuid.uuid4())
    
    active_server = find_active_server(args.server)
    ws_url = f"ws://{active_server}/ws?clientId={client_id}"

    try:
        print(f"Connecting to {ws_url}...")
        ws = websocket.WebSocket()
        ws.connect(ws_url, timeout=5)
        
        print("Submitting prompt and waiting for generation...")
        images = get_images(ws, workflow, client_id, active_server)
    except Exception as e:
        print(f"WebSocket connection failed ({e}). Falling back to HTTP polling...")
        images = get_images_http_fallback(workflow, client_id, active_server)
        
    try:
        for node_id, image_list in images.items():
            for image in image_list:
                file_path = os.path.join(args.output_dir, image['filename'])
                with open(file_path, "wb") as f:
                    f.write(image['data'])
                print(f"Saved: {file_path}")
                
    except Exception as e:
        print(f"Error generating image: {e}")
        exit(1)
    finally:
        if 'ws' in locals() and hasattr(ws, 'connected') and ws.connected:
            ws.close()
