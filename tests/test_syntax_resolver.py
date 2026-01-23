import pytest
from app.syntax_resolver import resolve_syntax_name, normalise_syntax_name

def test_resolve_syntax_name_known_tcs() -> None:
    assert resolve_syntax_name("DisplayString") == "OctetString"
    assert resolve_syntax_name("OwnerString") == "OctetString"
    assert resolve_syntax_name("TruthValue") == "Integer32"
    assert resolve_syntax_name("TimeStamp") == "TimeTicks"
    assert resolve_syntax_name("KBytes") == "Integer32"
    assert resolve_syntax_name("AutonomousType") == "ObjectIdentifier"
    assert resolve_syntax_name("TestAndIncr") == "Integer32"
    assert resolve_syntax_name("ProductID") == "ObjectIdentifier"
    assert resolve_syntax_name("InternationalDisplayString") == "OctetString"
    assert resolve_syntax_name("InterfaceIndexOrZero") == "Integer32"

def test_resolve_syntax_name_base_types() -> None:
    assert resolve_syntax_name("Integer32") == "Integer32"
    assert resolve_syntax_name("OctetString") == "OctetString"
    assert resolve_syntax_name("Counter64") == "Counter64"
    assert resolve_syntax_name("ObjectIdentifier") == "ObjectIdentifier"
    assert resolve_syntax_name("TimeTicks") == "TimeTicks"

def test_resolve_syntax_name_unknown() -> None:
    assert resolve_syntax_name("NonExistentTC") is None

def test_normalise_syntax_name() -> None:
    assert normalise_syntax_name("OCTET STRING") == "OctetString"
    assert normalise_syntax_name("ObjectIdentifier") == "ObjectIdentifier"
    assert normalise_syntax_name("Integer_32") == "Integer32"
