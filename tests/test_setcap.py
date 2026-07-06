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
