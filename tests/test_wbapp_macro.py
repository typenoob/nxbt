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
def web_app(mock_nxbt):
    from nxbt.web.app import WebApp

    return WebApp(nxbt=mock_nxbt)


def test_state_emission(web_app):
    """Test that on_state reads state and emits it."""
    mock_emit = AsyncMock()

    with patch.object(web_app.sio, "emit", mock_emit):
        web_app.on_state("test_sid")

    mock_emit.assert_awaited_once()
    event, state_data = mock_emit.await_args.args
    assert event == "state"
    assert mock_emit.await_args.kwargs["to"] == "test_sid"
    assert 0 in state_data
    assert state_data[0]["state"] == "connected"


def test_controller_creation(web_app, mock_nxbt):
    """Test that on_create_controller creates a controller."""
    mock_emit = AsyncMock()
    web_app._user_info["test_sid"] = {}

    with patch.object(web_app.sio, "emit", mock_emit):
        asyncio.run(web_app.on_create_controller("test_sid"))

    mock_nxbt.create_controller.assert_called_once()
    events = [call.args[0] for call in mock_emit.await_args_list]
    assert "create_pro_controller" in events


def test_macro_execution(web_app, mock_nxbt):
    """Test that handle_macro passes the correct args to nxbt.macro."""
    macro_payload = json.dumps([0, "B 0.1s A 0.1s"])
    web_app.handle_macro("test_sid", macro_payload)

    mock_nxbt.macro.assert_called_once()
    call_args = mock_nxbt.macro.call_args
    assert call_args[0][0] == 0
    assert "B" in call_args[0][1]
    assert "A" in call_args[0][1]


def test_handle_input_ignores_missing_controller(web_app, mock_nxbt):
    mock_nxbt.set_controller_input.side_effect = ValueError(
        "Specified controller does not exist"
    )
    web_app.handle_input("test_sid", json.dumps([0, {}]))
