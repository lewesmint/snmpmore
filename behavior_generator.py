import subprocess
import os

class BehaviorGenerator:
    """Handles generation of behavior JSON from compiled MIB Python files."""
    def __init__(self, output_dir: str = 'mock-behavior') -> None:
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)

    def generate(self, compiled_py_path: str, mib_name: str) -> str:
        json_path = os.path.join(self.output_dir, f'{mib_name}_behavior.json')
        if not os.path.exists(json_path):
            subprocess.run(['python', 'mib_to_json.py', compiled_py_path, mib_name], check=True)
        return json_path
