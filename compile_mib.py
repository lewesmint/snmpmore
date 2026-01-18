# compile_mib.py
# Script to compile MY-AGENT-MIB.txt to Python using pysmi API
from pysmi.reader.localfile import FileReader
from pysmi.searcher import PyFileSearcher
from pysmi.writer import PyFileWriter
from pysmi.parser.smi import parserFactory
from pysmi.codegen.pysnmp import PySnmpCodeGen
from pysmi.compiler import MibCompiler
import sys
from typing import Any, cast

# Uncomment for debugging
# debug.setLogger(debug.Debug('all'))

input_mib = 'MY-AGENT-MIB.txt'
output_dir = 'compiled-mibs'

compiler = MibCompiler(
    parserFactory()(),
    PySnmpCodeGen(),
    PyFileWriter(output_dir)
)

compiler.add_sources(FileReader('.'))
compiler.add_sources(FileReader('/var/lib/mibs/ietf'))
compiler.add_searchers(PyFileSearcher(output_dir))

results = compiler.compile(input_mib)

for mib, status in results.items():
    print(f'{mib}: {status}')

if not all(str(cast(Any, compile_status)) == 'compiled' for compile_status in results.values()):
    sys.exit(1)
