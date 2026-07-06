from unittest.mock import patch

from nxbt.setcap import (
    GRANT_CAPS_HINT,
    has_bluez_caps,
    has_cap_net_admin,
)


def test_grant_caps_hint_message():
    assert GRANT_CAPS_HINT == (
        'Run `sudo env HOME="$HOME" nxbt` first to grant permissions.'
    )


def test_has_cap_net_admin():
    with patch(
        "nxbt.setcap.get_executable_caps",
        return_value="cap_net_admin=eip",
    ):
        assert has_cap_net_admin() is True

    with patch("nxbt.setcap.get_executable_caps", return_value=None):
        assert has_cap_net_admin() is False


def test_bumble_get_available_adapters_with_permissions():
    from nxbt.backends.bumble import BumbleBackend

    with (
        patch.object(BumbleBackend, "_detect_adapters", return_value=["hci-socket:0"]),
        patch("nxbt.backends.bumble.has_cap_net_admin", return_value=True),
    ):
        result = BumbleBackend.get_available_adapters()

    assert result == {
        "adapters": ["hci-socket:0"],
        "has_permissions": True,
    }


def test_bumble_get_available_adapters_without_permissions():
    from nxbt.backends.bumble import BumbleBackend

    with (
        patch.object(BumbleBackend, "_detect_adapters", return_value=["hci-socket:0"]),
        patch("nxbt.backends.bumble.has_cap_net_admin", return_value=False),
    ):
        result = BumbleBackend.get_available_adapters()

    assert result == {"adapters": [], "has_permissions": False}


def test_has_bluez_caps():
    with patch(
        "nxbt.setcap.get_executable_caps",
        return_value="cap_net_admin,cap_net_bind_service=eip",
    ):
        assert has_bluez_caps() is True

    with patch(
        "nxbt.setcap.get_executable_caps",
        return_value="cap_net_admin=eip",
    ):
        assert has_bluez_caps() is False


def test_bluez_get_available_adapters_without_override_access():
    from nxbt.backends.bluez import BlueZBackend

    with (
        patch("nxbt.backends.bluez.find_objects", return_value=["/org/bluez/hci0"]),
        patch("nxbt.backends.bluez.get_blocked_hci_indices", return_value=set()),
        patch("nxbt.backends.bluez.has_bluez_caps", return_value=True),
        patch("nxbt.backends.bluez.has_bluez_override_access", return_value=False),
    ):
        result = BlueZBackend.get_available_adapters()

    assert result == {"adapters": [], "has_permissions": False}


def test_bluez_get_available_adapters_with_permissions():
    from nxbt.backends.bluez import BlueZBackend

    with (
        patch("nxbt.backends.bluez.find_objects", return_value=["/org/bluez/hci0"]),
        patch("nxbt.backends.bluez.get_blocked_hci_indices", return_value=set()),
        patch("nxbt.backends.bluez.has_bluez_caps", return_value=True),
        patch("nxbt.backends.bluez.has_bluez_override_access", return_value=True),
    ):
        result = BlueZBackend.get_available_adapters()

    assert result == {
        "adapters": ["/org/bluez/hci0"],
        "has_permissions": True,
    }
