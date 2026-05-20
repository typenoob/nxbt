#   Python test originally created or extracted from Hannah's work (https://github.com/hannahbee91/nxbt).
#   Some modifications might have been made to adapt to my own project.

import pytest
from unittest.mock import MagicMock, patch
import sys

# Ensure dbus is mocked if not already by conftest
if "dbus" not in sys.modules:
    sys.modules["dbus"] = MagicMock()

from nxbt import Nxbt, PRO_CONTROLLER
from nxbt.nxbt import NxbtCommands


class TestNxbt:
    @pytest.fixture
    def nxbt_instance(self):
        mock_backend = MagicMock()
        mock_backend.get_available_adapters.return_value = ["hci0"]
        mock_backend.get_switch_addresses.return_value = []

        with (
            patch("nxbt.nxbt.Process") as mock_process,
            patch("nxbt.nxbt.Manager") as mock_manager,
            patch("nxbt.nxbt.toggle_clean_bluez"),
        ):
            mock_manager_instance = mock_manager.return_value
            mock_manager_instance.dict.return_value = {}

            nx = Nxbt(debug=True, disable_logging=True, backend=mock_backend)
            yield nx

    def test_init(self, nxbt_instance):
        """Test that Nxbt initializes correctly."""
        assert nxbt_instance.debug is True
        assert nxbt_instance.task_queue is not None
        assert nxbt_instance.controllers.start.called

    def test_create_controller_no_adapters(self):
        """Test create_controller raises error when no adapters available."""
        mock_backend = MagicMock()
        mock_backend.get_available_adapters.return_value = []

        with (
            patch("nxbt.nxbt.Process"),
            patch("nxbt.nxbt.Manager"),
            patch("nxbt.nxbt.toggle_clean_bluez"),
        ):
            nx = Nxbt(disable_logging=True, backend=mock_backend)
            with pytest.raises(ValueError, match="No adapters available"):
                nx.create_controller(PRO_CONTROLLER)

    def test_create_controller_success(self, nxbt_instance):
        """Test creating a controller successfully."""

        def side_effect_sleep(*args):
            nxbt_instance.manager_state[0] = {"state": "connecting"}

        with patch("time.sleep", side_effect=side_effect_sleep):
            idx = nxbt_instance.create_controller(PRO_CONTROLLER)
            assert idx == 0
            msg = nxbt_instance.task_queue.get(timeout=1)
            assert msg["command"] == NxbtCommands.CREATE_CONTROLLER

    def test_macro(self, nxbt_instance):
        """Test inputting a macro."""
        nxbt_instance.manager_state[0] = {"state": "connected", "finished_macros": []}

        macro_string = "B 0.1s\n0.1s"
        macro_id = nxbt_instance.macro(0, macro_string, block=False)

        assert isinstance(macro_id, str)

        msg = nxbt_instance.task_queue.get()
        assert msg["command"] == NxbtCommands.INPUT_MACRO
        assert msg["arguments"]["macro"] == macro_string
        assert msg["arguments"]["controller_index"] == 0

    def test_macro_blocking(self, nxbt_instance):
        """Test blocking macro wait."""
        nxbt_instance.manager_state[0] = {"state": "connected", "finished_macros": []}

        macro_id_holder = []

        original_put = nxbt_instance.task_queue.put

        def side_effect_put(item, *args, **kwargs):
            if item["command"] == NxbtCommands.INPUT_MACRO:
                macro_id_holder.append(item["arguments"]["macro_id"])
            original_put(item, *args, **kwargs)

        def side_effect_sleep(*args):
            if macro_id_holder:
                mid = macro_id_holder[0]
                nxbt_instance.manager_state[0] = {
                    "state": "connected",
                    "finished_macros": [mid],
                }

        with (
            patch.object(nxbt_instance.task_queue, "put", side_effect=side_effect_put),
            patch("time.sleep", side_effect=side_effect_sleep),
        ):
            macro_string = "A 0.1s"
            result_id = nxbt_instance.macro(0, macro_string, block=True)
            assert result_id == macro_id_holder[0]
