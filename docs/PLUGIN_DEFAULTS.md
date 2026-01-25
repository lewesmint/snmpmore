# Plugin-based Default Value Hooks for SNMP Behaviour Generation

## Overview
This document describes a proposed extension to the SNMP behaviour generator to allow plugin code to supply initial/default values for non-basic SNMP types (such as `ObjectIdentifier`, `IpAddress`, or custom types). This enables more flexible, context-aware, or environment-specific initialization of SNMP table/column values, beyond the current hardcoded defaults.

## Motivation
- **Current Limitation:** The generator uses hardcoded defaults for non-basic types (e.g., `'1.3.6.1.1'` for OID, `'0.0.0.0'` for IP address).
- **Desired Flexibility:** Some deployments may require context-specific, randomized, or externally-supplied initial values for these types.
- **Plugin Approach:** By allowing a plugin (Python module or callable) to provide these values, the generator becomes more extensible and adaptable.

gen = BehaviourGenerator(plugin=get_default_value)
gen.generate('compiled-mibs/SNMPv2-MIB.py')
## Proposed Design

### 1. Plugin Discovery and Interface
- All plugin Python scripts must be placed in a `plugins/` directory in the project root.
- On startup, the generator loads all `.py` files in `plugins/` as modules.
- Each plugin module must implement a standard function:
  ```python
  def get_default_value(symbol_name: str, type_info: dict) -> Any:
      # Return a value for the given symbol/type, or None if not handled
  ```
- The expected return type is determined dynamically by the SNMP type (e.g., string for OID, int for Integer, etc.).
- The generator will call each plugin's `get_default_value` in turn for every default value request. The first non-`None` result is used.

#### Example Plugin Function
```python
def get_default_value(symbol_name: str, type_info: dict) -> Any:
    if type_info.get('base_type') == 'ObjectIdentifier':
        # Example: generate a random OID or fetch from config
        return '1.3.6.1.4.1.99999.1.1'
    if type_info.get('base_type') == 'IpAddress':
        return '192.168.1.1'
    return None  # Not handled by this plugin
```

### 2. Generator Integration and Failure Handling
- The generator will call all loaded plugins for each default value request in `_get_default_value_from_type_info`.
- If any plugin returns a non-`None` value, it is used as the initial value.
- If no plugin provides a value for a required type (and the type is not a basic type with a built-in default), the generator will halt with an error, instructing the user to implement a plugin for that type.
- This ensures that all non-basic types are handled explicitly and no silent fallback occurs.

#### Example Integration
```python
def _get_default_value_from_type_info(self, type_info, symbol_name):
    for plugin in self.plugins:
        value = plugin.get_default_value(symbol_name, type_info)
        if value is not None:
            return value
    # If not handled and required, raise error
    raise RuntimeError(f"No plugin found to provide default value for {symbol_name} (type: {type_info.get('base_type')})")
```

### 3. Configuration and Extensibility
- To add support for a new type, simply add a new plugin script to the `plugins/` directory with the required logic.
- No changes to the generator core are needed for new types.

## Benefits
- **Extensibility:** Users can customize initial values for any type or symbol by adding plugins.
- **Strictness:** The generator will not proceed with missing or ambiguous defaults for non-basic types, ensuring correctness.
- **Separation of Concerns:** Defaulting logic for special cases moves out of the generator core.
- **Testing:** Easier to test different initialization strategies.

## Example Usage
```python
# Place plugin scripts in plugins/ directory
gen = BehaviourGenerator()
gen.generate('compiled-mibs/SNMPv2-MIB.py')
```

## Backward Compatibility
- For basic types with built-in defaults, the generator behaves as before.
- For non-basic types, a plugin is now required; otherwise, the generator will halt and instruct the user to add one.

## Next Steps
1. Implement the plugin discovery and integration in the generator.
2. Provide example plugin(s) in the plugins/ directory and update documentation.
3. Optionally, support plugin loading by module path (string) for CLI use.

---
