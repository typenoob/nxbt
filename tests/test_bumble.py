#   Python test originally created or extracted from Hannah's work (https://github.com/hannahbee91/nxbt).
#   Some modifications might have been made to adapt to my own project.

import asyncio
import sys
import pytest
from unittest.mock import MagicMock, patch

# Ensure dbus is mocked if not already by conftest
if "dbus" not in sys.modules:
    sys.modules["dbus"] = MagicMock()

from nxbt.backends import BumbleBackend


def _run_async_mock(coro):
    """Mimics BumbleBackend._run_async: await a coroutine and return result."""
    if asyncio.iscoroutine(coro):
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()
    # For mocked async methods (MagicMock), return directly
    return coro


class TestBumbleBackendAliases:
    """Verify ALIASES dict keys match ControllerTypes enum values."""

    def test_alias_keys_are_enum_values(self):
        aliases = BumbleBackend.ALIASES
        from nxbt.controller.controller import ControllerTypes

        assert ControllerTypes.JOYCON_L in aliases
        assert ControllerTypes.JOYCON_R in aliases
        assert ControllerTypes.PRO_CONTROLLER in aliases
