# app/syntax_resolver.py
"""
Resolves SNMP Textual Conventions (TCs) to their base SMI types.
"""

TC_TO_BASE = {
    "DisplayString": "OctetString",
    "OwnerString": "OctetString",
    "InternationalDisplayString": "OctetString",
    "TruthValue": "Integer32",
    "TimeStamp": "TimeTicks",
    "KBytes": "Integer32",
    "InterfaceIndexOrZero": "Integer32",
    "AutonomousType": "ObjectIdentifier",
    "ProductID": "ObjectIdentifier",
    "TestAndIncr": "Integer32",
}

SUPPORTED_BASE_TYPES = {
    "Integer32",
    "OctetString",
    "ObjectIdentifier",
    "Counter32",
    "Gauge32",
    "Counter64",
    "TimeTicks",
}

def normalise_syntax_name(name: str) -> str:
    """Normalise type names for comparison (removes spaces, dashes, underscores, preserves camel case)."""
    s = name.replace(" ", "").replace("-", "").replace("_", "")
    # Special case for known SNMP types that are all uppercase with a space (e.g., 'OCTET STRING')
    if name.strip().upper() == "OCTET STRING":
        return "OctetString"
    if name.strip().upper() == "OBJECT IDENTIFIER":
        return "ObjectIdentifier"
    # If all uppercase, convert to camel case (e.g., 'COUNTER64' -> 'Counter64')
    if s.isupper():
        # Capitalize first, then lowercase the rest except trailing digits
        head = ''.join([c for c in s if not c.isdigit()])
        tail = ''.join([c for c in s if c.isdigit()])
        if head:
            s = head.capitalize() + tail
    return s

def resolve_syntax_name(reported: str) -> str | None:
    """Resolve a reported syntax name to a supported base type, if possible."""
    norm = normalise_syntax_name(reported)
    if norm in SUPPORTED_BASE_TYPES:
        return norm
    base = TC_TO_BASE.get(norm)
    if base and base in SUPPORTED_BASE_TYPES:
        return base
    return None
