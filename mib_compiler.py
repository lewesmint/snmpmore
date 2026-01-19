import subprocess
import os
from typing import List

class MibCompiler:
    """Handles compilation of MIB .txt files to Python using pysmi."""
    def __init__(self, output_dir: str = 'compiled-mibs') -> None:
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)

    def compile(self, mib_txt_path: str) -> str:
        mib_name = os.path.splitext(os.path.basename(mib_txt_path))[0]
        compiled_py = os.path.join(self.output_dir, f'{mib_name}.py')
        if not os.path.exists(compiled_py):
            try:
                subprocess.run(['python', 'tools/compile_mib.py', mib_txt_path], check=True, capture_output=True, text=True)
            except subprocess.CalledProcessError as e:
                output = e.stdout or ''
                error = e.stderr or ''
                missing = self._parse_missing_dependencies(output + error)
                if missing:
                    print(f"Missing MIB dependencies detected for {mib_name}: {', '.join(missing)}")
                    print("Please provide or download these MIB files and place them in your MIB source directory.")
                raise
        return compiled_py

    def _parse_missing_dependencies(self, output: str) -> List[str]:
        # Look for lines like: '*** <MIB> is missing' or similar
        import re
        missing: set[str] = set()
        for line in output.splitlines():
            m = re.search(r'([A-Za-z0-9\-]+)\s+is missing', line)
            if m:
                missing.add(m.group(1))
        return list(missing)
