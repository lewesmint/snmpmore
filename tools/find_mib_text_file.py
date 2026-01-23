import os
from typing import Optional, List

def find_mib_text_file(module_name: str, search_dirs: List[str]) -> Optional[str]:
    """
    Search for a MIB text file containing the given module name in all supported extensions and folders.
    Returns the path to the file if found, else None.
    """
    extensions = [".my", ".txt", ".mib"]
    for folder in search_dirs:
        for root, _, files in os.walk(folder):
            for file in files:
                if any(file.endswith(ext) for ext in extensions):
                    file_path = os.path.join(root, file)
                    try:
                        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                            content = f.read(4096)  # Read first 4KB for speed
                            # Look for MODULE-IDENTITY or BEGIN for module name
                            if module_name in content:
                                return file_path
                    except Exception:
                        continue
    return None

# Example usage:
if __name__ == "__main__":
    import sys
    if len(sys.argv) < 3:
        print("Usage: python find_mib_text_file.py <module_name> <search_dir1> [<search_dir2> ...]")
        sys.exit(1)
    module = sys.argv[1]
    dirs = sys.argv[2:]
    result = find_mib_text_file(module, dirs)
    if result:
        print(f"Found: {result}")
    else:
        print("Not found.")
