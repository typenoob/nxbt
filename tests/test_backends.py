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
