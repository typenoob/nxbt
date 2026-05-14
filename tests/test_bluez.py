#   Python test originally created or extracted from Hannah's work (https://github.com/hannahbee91/nxbt).
#   Some modifications might have been made to adapt to my own project.

import sys
import importlib.util
import pytest
from unittest.mock import patch, AsyncMock, MagicMock

# Load the real bluez module directly from file, bypassing sys.modules
# This avoids conflicts with conftest.py's global mock of nxbt.bluez
_spec = importlib.util.spec_from_file_location(
    "_real_bluez",
    "/home/coyote/nxbt/nxbt/bluez.py",
)
bluez_mod = importlib.util.module_from_spec(_spec)
sys.modules["_real_bluez"] = bluez_mod
_spec.loader.exec_module(bluez_mod)

# Extract names for convenience
_guess_signature = bluez_mod._guess_signature
find_object_path = bluez_mod.find_object_path
find_objects = bluez_mod.find_objects
find_devices_by_alias = bluez_mod.find_devices_by_alias
get_random_controller_mac = bluez_mod.get_random_controller_mac
DEVICE_INTERFACE = bluez_mod.DEVICE_INTERFACE
ADAPTER_INTERFACE = bluez_mod.ADAPTER_INTERFACE
SERVICE_NAME = bluez_mod.SERVICE_NAME
BlueZ = bluez_mod.BlueZ

PATCH_PREFIX = "_real_bluez"


def _make_managed_objects(**overrides):
    """Build a typical BlueZ ManagedObjects dict."""
    return {
        "/org/bluez/hci0": {
            ADAPTER_INTERFACE: {
                "Address": "AA:BB:CC:DD:EE:00",
                "Name": "hci0",
                "Alias": "linux",
                "Powered": True,
                "Pairable": True,
            },
        },
        "/org/bluez/hci0/dev_11_22_33_44_55_66": {
            DEVICE_INTERFACE: {
                "Address": "11:22:33:44:55:66",
                "Alias": "Test Device",
                "Paired": True,
                "Connected": False,
            },
        },
        "/org/bluez/hci0/dev_AA_BB_CC_DD_EE_FF": {
            DEVICE_INTERFACE: {
                "Address": "AA:BB:CC:DD:EE:FF",
                "Alias": "Nintendo Switch",
                "Paired": True,
                "Connected": True,
            },
        },
        "/org/bluez/hci0/dev_99_99_99_99_99_99": {
            DEVICE_INTERFACE: {
                "Address": "99:99:99:99:99:99",
                "Alias": "Random Phone",
                "Paired": False,
                "Connected": False,
            },
        },
        **overrides,
    }


class TestGuessSignature:
    def test_bool(self):
        assert _guess_signature(True) == "b"

    def test_int(self):
        assert _guess_signature(42) == "u"

    def test_str(self):
        assert _guess_signature("hello") == "s"

    def test_dict(self):
        assert _guess_signature({"key": "val"}) == "a{sv}"

    def test_list(self):
        assert _guess_signature(["a", "b"]) == "as"

    def test_unknown(self):
        assert _guess_signature(None) == "s"


class TestGetRandomControllerMac:
    def test_mac_format(self):
        mac = get_random_controller_mac()
        parts = mac.split(":")
        assert len(parts) == 6
        assert parts[0] == "7C"
        assert parts[1] == "BB"
        assert parts[2] == "8A"
        for part in parts[3:]:
            int(part, 16)

    def test_mac_uniqueness(self):
        assert get_random_controller_mac() != get_random_controller_mac()


class TestFindObjectPath:
    @patch(f"{PATCH_PREFIX}._get_managed_objects", new_callable=AsyncMock)
    def test_find_adapter(self, mock_get):
        mock_get.return_value = _make_managed_objects()
        result = find_object_path(SERVICE_NAME, ADAPTER_INTERFACE)
        assert result == "/org/bluez/hci0"

    @patch(f"{PATCH_PREFIX}._get_managed_objects", new_callable=AsyncMock)
    def test_find_device_by_address(self, mock_get):
        mock_get.return_value = _make_managed_objects()
        result = find_object_path(
            SERVICE_NAME, DEVICE_INTERFACE, object_name="11:22:33:44:55:66"
        )
        assert result == "/org/bluez/hci0/dev_11_22_33_44_55_66"

    @patch(f"{PATCH_PREFIX}._get_managed_objects", new_callable=AsyncMock)
    def test_find_by_path_suffix(self, mock_get):
        mock_get.return_value = _make_managed_objects()
        result = find_object_path(
            SERVICE_NAME, DEVICE_INTERFACE, object_name="dev_11_22_33_44_55_66"
        )
        assert result == "/org/bluez/hci0/dev_11_22_33_44_55_66"

    @patch(f"{PATCH_PREFIX}._get_managed_objects", new_callable=AsyncMock)
    def test_not_found(self, mock_get):
        mock_get.return_value = {}
        result = find_object_path(SERVICE_NAME, "nonexistent.Interface")
        assert result is None


class TestFindObjects:
    @patch(f"{PATCH_PREFIX}._get_managed_objects", new_callable=AsyncMock)
    def test_find_all_devices(self, mock_get):
        mock_get.return_value = _make_managed_objects()
        result = find_objects(SERVICE_NAME, DEVICE_INTERFACE)
        assert len(result) == 3
        assert all(p.startswith("/org/bluez/hci0/dev_") for p in result)

    @patch(f"{PATCH_PREFIX}._get_managed_objects", new_callable=AsyncMock)
    def test_find_adapters(self, mock_get):
        mock_get.return_value = _make_managed_objects()
        result = find_objects(SERVICE_NAME, ADAPTER_INTERFACE)
        assert result == ["/org/bluez/hci0"]


class TestFindDevicesByAlias:
    @patch(f"{PATCH_PREFIX}._get_managed_objects", new_callable=AsyncMock)
    @patch(f"{PATCH_PREFIX}._get_property", new_callable=AsyncMock)
    def test_find_by_alias(self, mock_prop, mock_get):
        mock_get.return_value = _make_managed_objects()

        alias_vals = {
            "/org/bluez/hci0/dev_11_22_33_44_55_66": "Test Device",
            "/org/bluez/hci0/dev_AA_BB_CC_DD_EE_FF": "Nintendo Switch",
            "/org/bluez/hci0/dev_99_99_99_99_99_99": "Random Phone",
        }
        addr_vals = {
            "/org/bluez/hci0/dev_11_22_33_44_55_66": "11:22:33:44:55:66",
            "/org/bluez/hci0/dev_AA_BB_CC_DD_EE_FF": "AA:BB:CC:DD:EE:FF",
            "/org/bluez/hci0/dev_99_99_99_99_99_99": "99:99:99:99:99:99",
        }

        async def prop_side_effect(bus, path, iface, prop):
            if prop == "Alias":
                return alias_vals.get(path, "")
            if prop == "Address":
                return addr_vals.get(path, "")
            return None

        mock_prop.side_effect = prop_side_effect

        addrs, paths = find_devices_by_alias("Test Device", return_path=True)

        assert addrs == ["11:22:33:44:55:66"]
        assert paths == ["/org/bluez/hci0/dev_11_22_33_44_55_66"]

    @patch(f"{PATCH_PREFIX}._get_managed_objects", new_callable=AsyncMock)
    @patch(f"{PATCH_PREFIX}._get_property", new_callable=AsyncMock)
    def test_find_by_alias_case_insensitive(self, mock_prop, mock_get):
        mock_get.return_value = _make_managed_objects()

        async def prop_side_effect(bus, path, iface, prop):
            if prop == "Alias":
                return {
                    "/org/bluez/hci0/dev_11_22_33_44_55_66": "test device",
                }.get(path, "")
            if prop == "Address":
                return {
                    "/org/bluez/hci0/dev_11_22_33_44_55_66": "11:22:33:44:55:66",
                }.get(path, "")
            return None

        mock_prop.side_effect = prop_side_effect

        addrs = find_devices_by_alias("TEST DEVICE")
        assert addrs == ["11:22:33:44:55:66"]

    @patch(f"{PATCH_PREFIX}._get_managed_objects", new_callable=AsyncMock)
    @patch(f"{PATCH_PREFIX}._get_property", new_callable=AsyncMock)
    def test_find_no_match(self, mock_prop, mock_get):
        mock_get.return_value = _make_managed_objects()

        async def prop_side_effect(bus, path, iface, prop):
            if prop == "Alias":
                return "Test Device"
            if prop == "Address":
                return "11:22:33:44:55:66"
            return None

        mock_prop.side_effect = prop_side_effect

        addrs = find_devices_by_alias("Nonexistent")
        assert addrs == []


class TestBlueZClass:
    @patch(f"{PATCH_PREFIX}.find_object_path", return_value="/org/bluez/hci0")
    def test_init(self, _mock):
        bz = BlueZ()
        assert bz.device_path == "/org/bluez/hci0"
        assert bz.device_id == "hci0"

    def test_init_no_adapter(self):
        with patch.object(bluez_mod, "find_object_path", return_value=None):
            with pytest.raises(Exception, match="Unable to find a bluetooth adapter"):
                BlueZ(adapter_path=None)

    def test_address_property(self):
        bz = BlueZ.__new__(BlueZ)
        bz.device_path = "/org/bluez/hci0"
        bz.device_id = "hci0"
        bz._prop = lambda _: "aa:bb:cc:dd:ee:00"
        assert bz.address == "AA:BB:CC:DD:EE:00"

    def test_name_property(self):
        bz = BlueZ.__new__(BlueZ)
        bz.device_path = "/org/bluez/hci0"
        bz.device_id = "hci0"
        bz._prop = lambda _: "linux"
        assert bz.name == "linux"

    def test_pairable_property(self):
        bz = BlueZ.__new__(BlueZ)
        bz.device_path = "/org/bluez/hci0"
        bz.device_id = "hci0"
        bz._prop = lambda _: True
        assert bz.pairable is True

    def test_powered_property(self):
        bz = BlueZ.__new__(BlueZ)
        bz.device_path = "/org/bluez/hci0"
        bz.device_id = "hci0"
        bz._prop = lambda _: True
        assert bz.powered is True


class TestBlueZFindConnectedDevices:
    @patch.object(bluez_mod, "_get_managed_objects", new_callable=AsyncMock)
    def test_find_connected_devices(self, mock_get):
        mock_get.return_value = _make_managed_objects()

        async def prop_side_effect(bus, path, iface, prop):
            if prop == "Connected":
                return path == "/org/bluez/hci0/dev_AA_BB_CC_DD_EE_FF"
            if prop == "Alias":
                return "Nintendo Switch"
            return None

        with patch.object(bluez_mod, "_get_property", new_callable=AsyncMock) as mock_prop:
            mock_prop.side_effect = prop_side_effect
            bz = BlueZ()
            result = bz.find_connected_devices()

        assert result == ["/org/bluez/hci0/dev_AA_BB_CC_DD_EE_FF"]

    @patch.object(bluez_mod, "_get_managed_objects", new_callable=AsyncMock)
    def test_find_connected_devices_with_alias_filter(self, mock_get):
        mock_get.return_value = _make_managed_objects()

        async def prop_side_effect(bus, path, iface, prop):
            if prop == "Connected":
                return path == "/org/bluez/hci0/dev_AA_BB_CC_DD_EE_FF"
            if prop == "Alias":
                return {
                    "/org/bluez/hci0/dev_AA_BB_CC_DD_EE_FF": "Nintendo Switch",
                    "/org/bluez/hci0/dev_11_22_33_44_55_66": "Other Device",
                }.get(path, "")
            return None

        with patch.object(bluez_mod, "_get_property", new_callable=AsyncMock) as mock_prop:
            mock_prop.side_effect = prop_side_effect
            bz = BlueZ()
            result = bz.find_connected_devices(alias_filter="Nintendo Switch")

        assert result == ["/org/bluez/hci0/dev_AA_BB_CC_DD_EE_FF"]

    @patch.object(bluez_mod, "_get_managed_objects", new_callable=AsyncMock)
    def test_find_connected_devices_none(self, mock_get):
        mock_get.return_value = {}

        bz = BlueZ()
        assert bz.find_connected_devices() == []


class TestBlueZFindBondedDevicesByAlias:
    @patch.object(bluez_mod, "_get_managed_objects", new_callable=AsyncMock)
    def test_find_all_bonded(self, mock_get):
        mock_get.return_value = _make_managed_objects()

        async def prop_side_effect(bus, path, iface, prop):
            if prop == "Paired":
                return path in (
                    "/org/bluez/hci0/dev_11_22_33_44_55_66",
                    "/org/bluez/hci0/dev_AA_BB_CC_DD_EE_FF",
                )
            return None

        with patch.object(bluez_mod, "_get_property", new_callable=AsyncMock) as mock_prop:
            mock_prop.side_effect = prop_side_effect
            bz = BlueZ()
            result = bz.find_bonded_devices_by_alias()

        assert len(result) == 2

    @patch.object(bluez_mod, "_get_managed_objects", new_callable=AsyncMock)
    def test_find_bonded_by_alias(self, mock_get):
        mock_get.return_value = _make_managed_objects()

        async def prop_side_effect(bus, path, iface, prop):
            if prop == "Paired":
                return path in (
                    "/org/bluez/hci0/dev_11_22_33_44_55_66",
                    "/org/bluez/hci0/dev_AA_BB_CC_DD_EE_FF",
                )
            if prop == "Alias":
                return {
                    "/org/bluez/hci0/dev_11_22_33_44_55_66": "Test Device",
                    "/org/bluez/hci0/dev_AA_BB_CC_DD_EE_FF": "Nintendo Switch",
                }.get(path, "")
            return None

        with patch.object(bluez_mod, "_get_property", new_callable=AsyncMock) as mock_prop:
            mock_prop.side_effect = prop_side_effect
            bz = BlueZ()
            result = bz.find_bonded_devices_by_alias("Nintendo Switch")

        assert result == ["/org/bluez/hci0/dev_AA_BB_CC_DD_EE_FF"]

    @patch.object(bluez_mod, "_get_managed_objects", new_callable=AsyncMock)
    def test_find_bonded_no_match(self, mock_get):
        mock_get.return_value = _make_managed_objects()

        async def prop_side_effect(bus, path, iface, prop):
            if prop == "Paired":
                return path in (
                    "/org/bluez/hci0/dev_11_22_33_44_55_66",
                    "/org/bluez/hci0/dev_AA_BB_CC_DD_EE_FF",
                )
            if prop == "Alias":
                return {
                    "/org/bluez/hci0/dev_11_22_33_44_55_66": "Test Device",
                    "/org/bluez/hci0/dev_AA_BB_CC_DD_EE_FF": "Nintendo Switch",
                }.get(path, "")
            return None

        with patch.object(bluez_mod, "_get_property", new_callable=AsyncMock) as mock_prop:
            mock_prop.side_effect = prop_side_effect
            bz = BlueZ()
            result = bz.find_bonded_devices_by_alias("Nonexistent")

        assert result == []


class TestBlueZDeviceOperations:
    @patch.object(bluez_mod, "_get_managed_objects", new_callable=AsyncMock)
    @patch.object(bluez_mod, "find_object_path", return_value="/org/bluez/hci0")
    def test_pair_device(self, mock_get, mock_find):
        mock_get.return_value = _make_managed_objects()

        with patch.object(bluez_mod, "_call_method", new_callable=AsyncMock) as mock_call:
            bz = BlueZ()
            bz.pair_device("/org/bluez/hci0/dev_11_22_33_44_55_66")

        mock_call.assert_called_once()

    @patch.object(bluez_mod, "_get_managed_objects", new_callable=AsyncMock)
    def test_connect_device(self, mock_get):
        mock_get.return_value = _make_managed_objects()

        with patch.object(bluez_mod, "_call_method", new_callable=AsyncMock) as mock_call:
            bz = BlueZ()
            bz.connect_device("/org/bluez/hci0/dev_11_22_33_44_55_66")

        mock_call.assert_called_once()

    @patch.object(bluez_mod, "_get_managed_objects", new_callable=AsyncMock)
    def test_remove_device(self, mock_get):
        mock_get.return_value = _make_managed_objects()

        with patch.object(bluez_mod, "_call_method", new_callable=AsyncMock) as mock_call:
            bz = BlueZ()
            bz.remove_device("/org/bluez/hci0/dev_11_22_33_44_55_66")

        mock_call.assert_called_once()


class TestBlueZFindDeviceByAddress:
    @patch.object(bluez_mod, "_get_managed_objects", new_callable=AsyncMock)
    def test_find_by_address(self, mock_get):
        mock_get.return_value = _make_managed_objects()

        async def prop_side_effect(bus, path, iface, prop):
            if prop == "Address":
                return {
                    "/org/bluez/hci0/dev_11_22_33_44_55_66": "11:22:33:44:55:66",
                    "/org/bluez/hci0/dev_AA_BB_CC_DD_EE_FF": "AA:BB:CC:DD:EE:FF",
                    "/org/bluez/hci0/dev_99_99_99_99_99_99": "99:99:99:99:99:99",
                }.get(path, "")
            return None

        with patch.object(bluez_mod, "_get_property", new_callable=AsyncMock) as mock_prop:
            mock_prop.side_effect = prop_side_effect
            bz = BlueZ()
            result = bz.find_device_by_address("AA:BB:CC:DD:EE:FF")

        assert result == "/org/bluez/hci0/dev_AA_BB_CC_DD_EE_FF"

    @patch.object(bluez_mod, "_get_managed_objects", new_callable=AsyncMock)
    def test_find_by_address_not_found(self, mock_get):
        mock_get.return_value = {}

        bz = BlueZ()
        assert bz.find_device_by_address("00:00:00:00:00:00") is None


class TestBlueZGetDiscoveredDevices:
    @patch.object(bluez_mod, "_get_managed_objects", new_callable=AsyncMock)
    def test_get_discovered_devices(self, mock_get):
        mock_get.return_value = _make_managed_objects()

        bz = BlueZ()
        result = bz.get_discovered_devices()

        assert len(result) == 3
        assert "/org/bluez/hci0/dev_11_22_33_44_55_66" in result
        assert "/org/bluez/hci0/dev_AA_BB_CC_DD_EE_FF" in result
