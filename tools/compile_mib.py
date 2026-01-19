#!/usr/bin/env python3
"""
Standalone MIB compiler tool.
Compiles MIB .txt files to Python using pysmi API.

Usage:
    python compile_mib.py <mib_file_path> [output_dir]

Examples:
    python compile_mib.py MY-AGENT-MIB.txt
    python compile_mib.py data/mibs/UDP-MIB.txt compiled-mibs
"""
from pysmi.reader.localfile import FileReader
from pysmi.searcher import PyFileSearcher
from pysmi.writer import PyFileWriter
from pysmi.parser.smi import parserFactory
from pysmi.codegen.pysnmp import PySnmpCodeGen
from pysmi.compiler import MibCompiler
import sys
import os
from typing import Any, cast

# Uncomment for debugging
# from pysmi import debug
# debug.setLogger(debug.Debug('all'))


def compile_mib(mib_file_path: str, output_dir: str = 'compiled-mibs') -> None:
    """Compile a MIB file to Python.

    Args:
        mib_file_path: Path to the MIB .txt file
        output_dir: Directory to write compiled Python files
    """
    # Ensure output directory exists
    os.makedirs(output_dir, exist_ok=True)

    # Get the directory containing the MIB file
    mib_dir = os.path.dirname(os.path.abspath(mib_file_path))
    mib_filename = os.path.basename(mib_file_path)

    compiler = MibCompiler(
        parserFactory()(),
        PySnmpCodeGen(),
        PyFileWriter(output_dir)
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
    compiler.add_searchers(PyFileSearcher(output_dir))

    results = compiler.compile(mib_filename)

    for mib, status in results.items():
        print(f'{mib}: {status}')

    if not all(str(cast(Any, compile_status)) == 'compiled' for compile_status in results.values()):
        sys.exit(1)


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(__doc__)
        print("\nError: Missing required argument <mib_file_path>")
        sys.exit(1)

    mib_path = sys.argv[1]
    output = sys.argv[2] if len(sys.argv) > 2 else 'compiled-mibs'

    if not os.path.exists(mib_path):
        print(f"Error: MIB file not found: {mib_path}")
        sys.exit(1)

    compile_mib(mib_path, output)
