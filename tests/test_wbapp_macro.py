#   Python test originally created or extracted from Hannah's work (https://github.com/hannahbee91/nxbt).
#   Some modifications might have been made to adapt to my own project.

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture
def mock_nxbt():
    mock = MagicMock()
    mock.state = {
        0: {
            "state": "connected",
            "finished_macros": [],
            "errors": [],
        }
    }
    mock.get_switch_addresses.return_value = []
    mock.create_controller.return_value = 0
    mock.macro.return_value = "macro_id_123"
    return mock


@pytest.fixture
def app_module(mock_nxbt_web, mock_nxbt):
    """Import web app after Nxbt has been patched."""
    from nxbt.web import app as web_app_module

    web_app_module.nxbt = mock_nxbt
    yield web_app_module


def test_state_emission(app_module):
    """Test that on_state reads state and emits it."""
    mock_emit = AsyncMock()

    with patch.object(app_module.sio, "emit", mock_emit):
        app_module.on_state("test_sid")

    mock_emit.assert_called_once()
    event, state_data = mock_emit.call_args[0]
    assert event == "state"
    assert mock_emit.call_args.kwargs["to"] == "test_sid"
    assert 0 in state_data
    assert state_data[0]["state"] == "connected"


def test_controller_creation(app_module, mock_nxbt):
    """Test that on_create_controller creates a controller."""
    mock_emit = AsyncMock()
    app_module.USER_INFO["test_sid"] = {}

    with patch.object(app_module.sio, "emit", mock_emit):
        asyncio.run(app_module.on_create_controller("test_sid"))

    mock_nxbt.create_controller.assert_called_once()
    events = [call.args[0] for call in mock_emit.await_args_list]
    assert "create_pro_controller" in events


def test_macro_execution(app_module, mock_nxbt):
    """Test that handle_macro passes the correct args to nxbt.macro."""
    macro_payload = json.dumps([0, "B 0.1s A 0.1s"])
    app_module.handle_macro("test_sid", macro_payload)

    mock_nxbt.macro.assert_called_once()
    call_args = mock_nxbt.macro.call_args
    assert call_args[0][0] == 0
    assert "B" in call_args[0][1]
    assert "A" in call_args[0][1]
