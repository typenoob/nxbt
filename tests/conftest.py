import pytest
import sys
from unittest.mock import MagicMock, patch

# Mock dbus dependencies before they are imported by nxbt
sys.modules["dbus"] = MagicMock()
sys.modules["dbus.mainloop.glib"] = MagicMock()
sys.modules["dbus.service"] = MagicMock()
# Mock bluez interaction to prevent system level changes during tests (PermissionError)
sys.modules["nxbt.bluez"] = MagicMock()
sys.modules["nxbt.backends.internal.bluez"] = MagicMock()


@pytest.fixture
def mock_bluetooth_adapters():
    """Mock the Bluetooth adapter discovery."""
    with pytest.MonkeyPatch.context() as m:
        from nxbt.backends import BumbleBackend

        m.setattr(
            BumbleBackend,
            "get_available_adapters",
            staticmethod(lambda: ["hci-socket:0"]),
        )
        yield m


@pytest.fixture
def mock_nxbt_web():
    """Patch Nxbt before web.app imports it at module level."""
    with patch("nxbt.web.app.Nxbt") as mock:
        mock.return_value = MagicMock()
        yield mock
