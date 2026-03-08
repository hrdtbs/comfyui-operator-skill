import argparse
import subprocess
import time
import requests
import os
import json
from pathlib import Path

def is_comfyui_running(urls: list[str]) -> str | None:
    for url in urls:
        try:
            response = requests.get(f"{url}/system_stats", timeout=2)
            if response.status_code == 200:
                return url
        except requests.RequestException:
            pass
    return None

def get_comfyui_executable_info(override_path: str = None) -> tuple[Path, list[str]]:
    """Returns the working directory and the command list to execute ComfyUI."""
    if override_path:
        base_path = Path(override_path)
        if not base_path.exists():
            raise FileNotFoundError(f"Provided path does not exist: {override_path}")
        
        # Check standard portable scripts
        bat_script = base_path / "run_nvidia_gpu.bat"
        main_script = base_path / "ComfyUI" / "main.py"
        if bat_script.exists():
            return base_path, [str(bat_script)]
        elif main_script.exists():
            return base_path / "ComfyUI", ["python", "main.py"]
        
        # Check if it points directly to an executable
        if base_path.is_file() and base_path.suffix == ".exe":
            return base_path.parent, [str(base_path)]
            
        raise FileNotFoundError(f"Could not find startup script in {override_path}")

    # Fallback 1: Desktop App
    local_app_data = os.environ.get('LOCALAPPDATA', '')
    app_data = os.environ.get('APPDATA', '')

    desktop_app_exe = Path(local_app_data) / "Programs" / "ComfyUI" / "ComfyUI.exe"
    if desktop_app_exe.exists():
        return desktop_app_exe.parent, [str(desktop_app_exe)]
    # Fallback 2: Windows Portable default
    portable_bat = Path(r"C:\ComfyUI_windows_portable\run_nvidia_gpu.bat")
    if portable_bat.exists():
        return portable_bat.parent, [str(portable_bat)]

    raise FileNotFoundError("Could not auto-detect ComfyUI installation. Please provide --comfyui_path.")

def start_comfyui(timeout: int = 60, override_path: str = None):
    urls_to_check = ["http://127.0.0.1:8188", "http://127.0.0.1:8000"]
    
    active_url = is_comfyui_running(urls_to_check)
    if active_url:
        print(f"ComfyUI is already running at {active_url}.")
        return

    cwd, cmd = get_comfyui_executable_info(override_path)
    
    print(f"Starting ComfyUI via: {cmd} (cwd: {cwd})...")
    use_shell = str(cmd[0]).endswith('.bat')
    
    creationflags = 0
    if os.name == 'nt' and not use_shell:
        # Use CREATE_NO_WINDOW only for direct process launches, not .bat which need shell=True
        creationflags = 0x08000000
        
    process = subprocess.Popen(cmd, cwd=str(cwd), shell=use_shell, creationflags=creationflags)
    print(f"Waiting up to {timeout} seconds for API to become available on ports 8188 or 8000...")
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        active_url = is_comfyui_running(urls_to_check)
        if active_url:
            print(f"ComfyUI started successfully at {active_url}.")
            return
        time.sleep(2)
        
    raise TimeoutError(f"ComfyUI failed to start within {timeout} seconds.")
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Start ComfyUI and wait for the API.")
    parser.add_argument(
        "--comfyui_path", 
        type=str, 
        default=None,
        help="Optional path to the ComfyUI installation. If omitted, attempts to auto-detect."
    )
    
    args = parser.parse_args()
    
    try:
        start_comfyui(override_path=args.comfyui_path)
    except Exception as e:
        print(f"Error starting ComfyUI: {e}")
        exit(1)
