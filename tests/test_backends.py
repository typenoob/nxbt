#   Python test originally created or extracted from Hannah's work (https://github.com/hannahbee91/nxbt).
#   Some modifications might have been made to adapt to my own project.

import sys
import pytest
from unittest.mock import MagicMock, patch

# Ensure dbus is mocked if not already by conftest
if "dbus" not in sys.modules:
    sys.modules["dbus"] = MagicMock()

from nxbt import PRO_CONTROLLER, JOYCON_L, JOYCON_R
from nxbt.controller.controller import ControllerTypes
from nxbt.backends import BlueZBackend


class TestBlueZBackendAliases:
    """Verify ALIASES dict keys match ControllerTypes enum values."""

    def test_alias_keys_are_enum_values(self):
        aliases = BlueZBackend.ALIASES
        assert ControllerTypes.JOYCON_L in aliases
        assert ControllerTypes.JOYCON_R in aliases
        assert ControllerTypes.PRO_CONTROLLER in aliases

    @pytest.mark.parametrize(
        "controller_type,expected_alias",
        [
            (JOYCON_L, "Joy-Con (L)"),
            (JOYCON_R, "Joy-Con (R)"),
            (PRO_CONTROLLER, "Pro Controller"),
        ],
    )
    def test_setup_sets_correct_alias(self, controller_type, expected_alias):
        with patch.object(
            BlueZBackend, "__init__", lambda self, adapter_path=None: None
        ):
            backend = BlueZBackend()
            backend._bt = MagicMock()

            backend.setup(controller_type)

            backend._bt.set_alias.assert_called_once_with(expected_alias)


class TestRemoveBondedDeviceFromAll:
    """Verify remove_bonded_device_from_all removes bonds from both backends."""

    def test_remove_bonded_device_from_all(self):
        """Verify that remove_bonded_device_from_all instantiates each backend
        class and calls remove_bonded_device on the instance with the correct
        address."""
        from nxbt.backends.base import Backend

        target_address = "00:11:22:33:44:55"

        mock_bluez_remove = MagicMock()
        mock_bumble_remove = MagicMock()

        # The function does backend_cls().remove_bonded_device(address), so
        # we need to ensure calling the mock class returns something with
        # remove_bonded_device tracked.
        mock_bluez_cls = MagicMock()
        mock_bluez_cls.return_value.remove_bonded_device = mock_bluez_remove

        mock_bumble_cls = MagicMock()
        mock_bumble_cls.return_value.remove_bonded_device = mock_bumble_remove

        mock_backends = {"bluez": mock_bluez_cls, "bumble": mock_bumble_cls}

        with patch("nxbt.backends.BACKENDS", mock_backends):
            Backend.remove_bonded_device_from_all(target_address)

        # Each backend class should have been instantiated
        mock_bluez_cls.assert_called_once()
        mock_bumble_cls.assert_called_once()

        # remove_bonded_device should have been called on the instance
        mock_bluez_remove.assert_called_once_with(target_address)
        mock_bumble_remove.assert_called_once_with(target_address)

    def test_remove_bonded_device_from_all_bluez_addresses_excluded(self):
        """After removing a bond, BlueZ's address list should no longer
        include the removed device."""
        from nxbt.backends.base import Backend
        from nxbt.backends import BlueZBackend

        target_address = "AA:BB:CC:DD:EE:FF"

        # Track bonded state: starts bonded, removed after the call
        bonded_addresses: set[str] = {target_address}

        def mock_find_device_by_address(address):
            if address in bonded_addresses:
                return f"/org/bluez/hci0/dev_{address.replace(':', '_')}"
            return None

        def mock_remove_device(path):
            addr = path.split("dev_")[-1].replace("_", ":").upper()
            bonded_addresses.discard(addr)

        bluez_bt_mock = MagicMock()
        bluez_bt_mock.find_device_by_address.side_effect = mock_find_device_by_address
        bluez_bt_mock.remove_device.side_effect = mock_remove_device

        # Use a real BlueZBackend instance (with mocked _bt) so that
        # the actual remove_bonded_device logic runs.
        with patch.object(BlueZBackend, "__init__", lambda self: None):
            bluez_backend = BlueZBackend()
            bluez_backend._bt = bluez_bt_mock

            # Bumble can be fully mocked since we don't assert on its internal state.
            mock_bumble_instance = MagicMock()
            mock_bumble_instance._device = MagicMock()
            mock_bumble_instance._run_async = MagicMock()
            mock_bumble_cls = MagicMock(return_value=mock_bumble_instance)

            # Use a factory lambda for bluez so backend_cls() returns our instance.
            mock_backends = {"bluez": lambda: bluez_backend, "bumble": mock_bumble_cls}

            with patch("nxbt.backends.BACKENDS", mock_backends):
                # Verify device is bonded before removal
                assert target_address in bonded_addresses

                # Remove from all backends
                Backend.remove_bonded_device_from_all(target_address)

                # Verify BlueZ no longer includes the address
                assert target_address not in bonded_addresses
