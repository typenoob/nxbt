#   Python test originally created or extracted from Hannah's work (https://github.com/hannahbee91/nxbt).
#   Some modifications might have been made to adapt to my own project.

import sys
import pytest
from unittest.mock import MagicMock, patch

# Ensure dbus is mocked if not already by conftest
if "dbus" not in sys.modules:
    sys.modules["dbus"] = MagicMock()

from nxbt import PRO_CONTROLLER
from nxbt.backends import BumbleBackend


class TestBumbleBackendAliases:
    """Verify ALIASES dict keys match ControllerTypes enum values."""

    def test_alias_keys_are_enum_values(self):
        aliases = BumbleBackend.ALIASES
        from nxbt.controller.controller import ControllerTypes

        assert ControllerTypes.JOYCON_L in aliases
        assert ControllerTypes.JOYCON_R in aliases
        assert ControllerTypes.PRO_CONTROLLER in aliases


class TestBumbleBackendSetupHciToggle:
    """Test that _setup_async toggles the HCI adapter off when it's up."""

    @patch("nxbt.backends.bumble.open_transport_or_link")
    @patch("nxbt.backends.bumble.JsonKeyStore")
    @patch("nxbt.backends.bumble.toggle_hci_adapter")
    @patch("nxbt.backends.bumble.get_hci_state")
    @patch("nxbt.backends.bumble.Device")
    def test_setup_toggles_hci_when_adapter_is_up(
        self,
        mock_device,
        mock_get_hci_state,
        mock_toggle,
        _mock_keystore,
        mock_open_transport,
    ):
        """When HCI adapter is UP, toggle_hci_adapter is called during _setup_async
        in addition to __init__, so total calls should be 2."""
        mock_get_hci_state.return_value = True
        mock_device.with_hci.return_value = MagicMock(
            public_address="AA:BB:CC:DD:EE:FF",
            random_address=None,
        )
        mock_open_transport.return_value = MagicMock(
            source=MagicMock(), sink=MagicMock()
        )

        backend = BumbleBackend(adapter_idx="hci-socket:0")
        backend._start_event_loop = MagicMock()
        backend._stop_event_loop = MagicMock()
        backend._run_async = MagicMock(side_effect=lambda coro: coro)
        backend._build_sdp_record = MagicMock(return_value=[])
        backend.setup(PRO_CONTROLLER)

        # __init__ calls toggle once; _setup_async calls toggle when adapter is UP
        assert mock_toggle.call_count == 2, (
            f"Expected 2 toggle calls (__init__ + _setup_async), got {mock_toggle.call_count}"
        )

    @patch("nxbt.backends.bumble.open_transport_or_link")
    @patch("nxbt.backends.bumble.JsonKeyStore")
    @patch("nxbt.backends.bumble.toggle_hci_adapter")
    @patch("nxbt.backends.bumble.get_hci_state")
    @patch("nxbt.backends.bumble.Device")
    def test_setup_skips_toggle_when_adapter_is_down(
        self,
        mock_device,
        mock_get_hci_state,
        mock_toggle,
        _mock_keystore,
        mock_open_transport,
    ):
        """When HCI adapter is already DOWN, _setup_async does NOT call toggle
        — only __init__ calls it, so total is 1."""
        mock_get_hci_state.return_value = False
        mock_device.with_hci.return_value = MagicMock(
            public_address="AA:BB:CC:DD:EE:FF",
            random_address=None,
        )
        mock_open_transport.return_value = MagicMock(
            source=MagicMock(), sink=MagicMock()
        )

        backend = BumbleBackend(adapter_idx="hci-socket:0")
        backend._start_event_loop = MagicMock()
        backend._stop_event_loop = MagicMock()
        backend._run_async = MagicMock(side_effect=lambda coro: coro)
        backend._build_sdp_record = MagicMock(return_value=[])
        backend.setup(PRO_CONTROLLER)

        # Only __init__ calls toggle; _setup_async skips it since adapter is DOWN
        assert mock_toggle.call_count == 1, (
            f"Expected 1 toggle call (__init__ only), got {mock_toggle.call_count}"
        )

    @patch("nxbt.backends.bumble.open_transport_or_link")
    @patch("nxbt.backends.bumble.JsonKeyStore")
    @patch("nxbt.backends.bumble.toggle_hci_adapter")
    @patch("nxbt.backends.bumble.get_hci_state")
    @patch("nxbt.backends.bumble.Device")
    def test_setup_skips_toggle_for_usb_transport(
        self,
        mock_device,
        mock_get_hci_state,
        mock_toggle,
        _mock_keystore,
        mock_open_transport,
    ):
        """For USB transport, get_hci_state and toggle_hci_adapter are NOT called."""
        mock_device.with_hci.return_value = MagicMock(
            public_address="AA:BB:CC:DD:EE:FF",
            random_address=None,
        )
        mock_open_transport.return_value = MagicMock(
            source=MagicMock(), sink=MagicMock()
        )

        backend = BumbleBackend(adapter_idx="usb:0")
        backend._start_event_loop = MagicMock()
        backend._stop_event_loop = MagicMock()
        backend._run_async = MagicMock(side_effect=lambda coro: coro)
        backend._build_sdp_record = MagicMock(return_value=[])
        backend.setup(PRO_CONTROLLER)

        mock_get_hci_state.assert_not_called()
        mock_toggle.assert_not_called()
