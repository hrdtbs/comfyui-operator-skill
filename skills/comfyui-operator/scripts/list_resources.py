import argparse
import os
import json
from pathlib import Path

def list_files_in_dir(directory: Path, extensions: list[str]) -> list[str]:
    """Helper to list files in a directory matching specific extensions."""
    if not directory.exists() or not directory.is_dir():
        return []
    
    files = []
    for ext in extensions:
        # Search recursively using rglob
        files.extend([str(p.relative_to(directory)).replace('\\', '/') for p in directory.rglob(f"*{ext}") if p.is_file()])
    return sorted(files)

def get_base_data_path(override_path: str = None) -> Path:
    if override_path:
        path = Path(override_path)
        if not path.exists():
            raise FileNotFoundError(f"Provided path does not exist: {override_path}")
        return path
        
    # Check Desktop App Config
    appdata = os.environ.get('APPDATA', '')
    config_file = Path(appdata) / "ComfyUI" / "config.json"
    if config_file.exists():
        try:
            with open(config_file, "r", encoding="utf-8") as f:
                config = json.load(f)
                if "basePath" in config and Path(config["basePath"]).exists():
                    return Path(config["basePath"])
        except Exception as e:
            print(f"Warning: Failed to read ComfyUI config.json: {e}")
            
    # Check Portable Default
    portable_path = Path(r"C:\ComfyUI_windows_portable\ComfyUI")
    if portable_path.exists():
        return portable_path

    raise FileNotFoundError("Could not auto-detect ComfyUI data path. Please provide --comfyui_path.")

def get_resources(override_path: str = None) -> dict:
    base_path = get_base_data_path(override_path)

    # Standard ComfyUI folder structure for models and workflows inside the data path
    workflows_dir = base_path / "user" / "default" / "workflows"
    checkpoints_dir = base_path / "models" / "checkpoints"
    loras_dir = base_path / "models" / "loras"

    resources = {
        "comfyui_data_path": str(base_path),
        "workflows": list_files_in_dir(workflows_dir, [".json"]),
        "checkpoints": list_files_in_dir(checkpoints_dir, [".ckpt", ".pt", ".bin", ".safetensors"]),
        "loras": list_files_in_dir(loras_dir, [".ckpt", ".pt", ".bin", ".safetensors"])
    }
    
    return resources

if __name__ == "__main__":
    import sys
    if sys.stdout.encoding.lower() != 'utf-8':
        sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description="List available ComfyUI resources (workflows, checkpoints, loras).")
    parser.add_argument(
        "--output", 
        type=str, 
        default=None,
        help="Optional file path to save the JSON output natively. Defaults to resources.json in the current working directory."
    )
    parser.add_argument(
        "--comfyui_path", 
        type=str, 
        default=None,
        help="Optional path to the ComfyUI installation."
    )
    
    args = parser.parse_args()
    
    try:
        resources = get_resources(args.comfyui_path)
        if not args.output:
            args.output = str(Path(os.getcwd()) / "resources.json")
            
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(resources, f, indent=2, ensure_ascii=False)
        print(f"Resources saved to {args.output}")
    except Exception as e:
        print(json.dumps({"error": str(e)}, indent=2))
        exit(1)
