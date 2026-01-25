import pytest
from app.snmp_agent import SNMPAgent
from typing import Any, List

class DummyAppConfig:
    def __init__(self, mibs: List[str]) -> None:
        self._mibs = mibs
    def get(self, key: str, default: Any = None) -> Any:
        if key == 'mibs':
            return self._mibs
        return default
    def get_platform_setting(self, key: str, default: Any = None) -> Any:
        if key == 'system_mib_dir':
            return '/opt/homebrew/opt/net-snmp/share/snmp/mibs'
        return default

@pytest.mark.parametrize("mib_name", [
    "IF-MIB", "HOST-RESOURCES-MIB", "CISCO-ALARM-MIB", "SNMPv2-MIB"
])
def test_agent_table_registration_errors(mocker: Any, mib_name: str) -> None:
    """
    Test that agent logs no table registration errors for supported MIBs.
    This test will fail if any table registration warning/error is logged.
    """
    warnings: List[str] = []
    def warning_patch(msg: Any, *args: Any, **kwargs: Any) -> None:
        warnings.append(str(msg))
    # Patch both AppLogger.warning and root logger warning to catch all warnings
    mocker.patch("app.app_logger.AppLogger.warning", warning_patch)
    mocker.patch("logging.Logger.warning", warning_patch)
    mocker.patch("app.app_logger.AppLogger.info", lambda *a, **k: None)
    mocker.patch("logging.Logger.info", lambda *a, **k: None)
    config = DummyAppConfig([mib_name])
    agent = SNMPAgent(config_path="dummy.yaml", app_config=config)  # type: ignore[arg-type]
    error_msgs = [w for w in warnings if "Could not register table" in w or "value model incompatible" in w]
    assert not error_msgs, f"Agent produced registration errors/warnings: {error_msgs}"
