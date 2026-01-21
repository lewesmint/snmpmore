#!/usr/bin/env python3
"""
Build all MIBs in dependency order using tools/mib_to_json.py.
"""
import os
import sys
import re
import subprocess
from collections import defaultdict, deque

MIB_SRC_DIRS = [
    'data/mibs/cisco',
    'data/mibs',
]
MIB_DST_DIR = 'compiled-mibs'
MIB_TO_JSON = 'tools/mib_to_json.py'

# Find all MIB source files
mib_files = []
for d in MIB_SRC_DIRS:
    if not os.path.exists(d):
        continue
    for f in os.listdir(d):
        if f.endswith('.my') or f.endswith('.txt'):
            mib_files.append(os.path.join(d, f))

# Map: mib_name -> (src_path, set(imported_mibs))
mib_imports = {}
mib_name_to_file = {}
for path in mib_files:
    with open(path, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()
    # Find MIB name
    mib_name = None
    for line in lines:
        m = re.match(r'\s*([A-Za-z0-9\-_.]+)\s+DEFINITIONS\s+::=\s+BEGIN', line)
        if m:
            mib_name = m.group(1)
            break
    if not mib_name:
        continue
    mib_name_to_file[mib_name] = path
    # Find IMPORTS section
    imported = set()
    in_imports = False
    for line in lines:
        l = line.strip()
        if l.startswith('IMPORTS'):
            in_imports = True
            continue
        if in_imports:
            if ';' in l:
                in_imports = False
                l = l.split(';')[0]
            parts = l.split('FROM')
            if len(parts) == 2:
                dep = parts[1].strip().rstrip(';').split()[0]
                imported.add(dep)
    mib_imports[mib_name] = (path, imported)

# Build dependency graph
edges = defaultdict(set)
reverse_edges = defaultdict(set)
for mib, (_path, imports) in mib_imports.items():
    for dep in imports:
        if dep in mib_imports:
            edges[mib].add(dep)
            reverse_edges[dep].add(mib)

# Topological sort
order = []
no_deps = deque([mib for mib in mib_imports if not edges[mib]])
visited = set()
while no_deps:
    mib = no_deps.popleft()
    if mib in visited:
        continue
    order.append(mib)
    visited.add(mib)
    for child in reverse_edges[mib]:
        edges[child].remove(mib)
        if not edges[child]:
            no_deps.append(child)

# Add any remaining (cyclic or missing) at the end
for mib in mib_imports:
    if mib not in visited:
        order.append(mib)

print('Build order:')
for mib in order:
    print(f'  {mib}')

# Build each MIB in order
for mib in order:
    src, _ = mib_imports[mib]
    print(f'\nBuilding {mib} from {src}...')
    cmd = [sys.executable, MIB_TO_JSON, src]
    result = subprocess.run(cmd, capture_output=True, text=True)
    print(result.stdout)
    if result.returncode != 0:
        print(result.stderr)
        print(f'Failed to build {mib}!')
        break
print('\nDone.')
