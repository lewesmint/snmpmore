import os
from typing import List, Any, cast
from pysmi.reader.localfile import FileReader
from pysmi.searcher import PyFileSearcher
from pysmi.writer import PyFileWriter
from pysmi.parser.smi import parserFactory
from pysmi.codegen.pysnmp import PySnmpCodeGen
from pysmi.compiler import MibCompiler as PysmiMibCompiler


class MibCompilationError(Exception):
    """Raised when MIB compilation fails."""
    def __init__(self, message: str, missing_dependencies: List[str] | None = None) -> None:
        super().__init__(message)
        self.missing_dependencies = missing_dependencies or []


class MibCompiler:
    """Handles compilation of MIB .txt files to Python using pysmi."""
    def __init__(self, output_dir: str = 'compiled-mibs') -> None:
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)

    def compile(self, mib_txt_path: str) -> str:
        """Compile a MIB .txt file to Python.

        Args:
            mib_txt_path: Path to the MIB .txt file

        Returns:
            Path to the compiled .py file

        Raises:
            RuntimeError: If compilation fails
        """
        mib_name = os.path.splitext(os.path.basename(mib_txt_path))[0]
        compiled_py = os.path.join(self.output_dir, f'{mib_name}.py')

        if os.path.exists(compiled_py):
            return compiled_py

        # Get the directory containing the MIB file
        mib_dir = os.path.dirname(os.path.abspath(mib_txt_path))
        mib_filename = os.path.basename(mib_txt_path)

        # Create pysmi compiler
        compiler = PysmiMibCompiler(
            parserFactory()(),
            PySnmpCodeGen(),
            PyFileWriter(self.output_dir)
        )

        # Add sources: the directory containing the MIB file and standard locations
        compiler.add_sources(FileReader(mib_dir))
        compiler.add_sources(FileReader('.'))
        compiler.add_sources(FileReader('data/mibs'))

        # Add system MIB directory (Net-SNMP default location on Windows)
        system_mib_dir = r'c:\net-snmp\share\snmp\mibs'
        if os.path.exists(system_mib_dir):
            compiler.add_sources(FileReader(system_mib_dir))

        # Add searchers for already compiled MIBs
        compiler.add_searchers(PyFileSearcher(self.output_dir))

        # Compile the MIB
        results = compiler.compile(mib_filename)

        # Collect all missing dependencies
        missing_deps: List[str] = []
        failed_mibs: List[tuple[str, str]] = []

        # Check results
        for mib, status in results.items():
            status_str = str(cast(Any, status))
            print(f'{mib}: {status_str}')

            # "compiled" and "untouched" are both success states
            # "untouched" means it was already compiled previously
            if status_str not in ('compiled', 'untouched'):
                failed_mibs.append((mib, status_str))
                # Check if it's a missing dependency error
                if 'missing' in status_str.lower():
                    missing_deps.append(mib)

        # If there are missing dependencies, provide helpful error message
        if missing_deps:
            error_msg = f"\n{'='*70}\n"
            error_msg += f"ERROR: Failed to compile {mib_name}\n"
            error_msg += f"{'='*70}\n"
            error_msg += f"Missing MIB dependencies: {', '.join(missing_deps)}\n\n"
            error_msg += "To resolve this:\n"
            error_msg += f"  1. Download the missing MIB files ({', '.join(missing_deps)})\n"
            error_msg += "  2. Place them in data/mibs/ or a subdirectory\n"
            error_msg += f"  3. Add them to agent_config.yaml before {mib_name}\n"
            error_msg += f"{'='*70}\n"
            raise MibCompilationError(error_msg, missing_dependencies=missing_deps)

        # If there are other failures, report them
        if failed_mibs:
            error_msg = f"Failed to compile {mib_name}:\n"
            for mib, status in failed_mibs:
                error_msg += f"  - {mib}: {status}\n"
            raise MibCompilationError(error_msg)

        if not os.path.exists(compiled_py):
            raise MibCompilationError(f"Compilation reported success but output file not found: {compiled_py}")

        return compiled_py

    def _parse_missing_from_status(self, status: str) -> List[str]:
        """Parse missing dependencies from compilation status message."""
        import re
        missing: set[str] = set()
        # Look for patterns like "MIB-NAME is missing" or similar
        for match in re.finditer(r'([A-Za-z0-9\-]+)\s+is missing', status):
            missing.add(match.group(1))
        return list(missing)
