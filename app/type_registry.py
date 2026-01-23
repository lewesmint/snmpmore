import importlib
from typing import List
import os

class TypeRegistry:
    def __init__(self) -> None:
        self.registry: dict[str, tuple[str, type]] = {}

    def add_types_from_mib_symbols(self, mib_name: str, mib_symbols: dict[str, object]) -> None:
        """Register all class types from a MIB's symbol dictionary."""
        for name, obj in mib_symbols.items():
            if isinstance(obj, type):
                self.registry[name] = (mib_name, obj)

    def keys(self) -> List[str]:
        return list(self.registry.keys())

    def get_type_names(self, module_name: str) -> List[str]:
        """Return all class names defined in the module for dynamic import."""
        mod = importlib.import_module(module_name)
        type_names: List[str] = []
        for name in dir(mod):
            if name.startswith('_'):
                continue
            obj = getattr(mod, name)
            if isinstance(obj, type) and getattr(obj, '__module__', None) == mod.__name__:
                type_names.append(name)
        return type_names