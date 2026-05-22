#   Python test originally created or extracted from Hannah's work (https://github.com/hannahbee91/nxbt).
#   Some modifications might have been made to adapt to my own project.

import pytest
import json
from unittest.mock import MagicMock, patch


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
    emitted = []

    def capture(event, *args):
        emitted.append({"name": event, "args": args})

    with patch("nxbt.web.app.emit", capture):
        app_module.on_state()

    assert len(emitted) == 1
    assert emitted[0]["name"] == "state"
    state_data = emitted[0]["args"][0]
    assert 0 in state_data
    assert state_data[0]["state"] == "connected"


def test_controller_creation(app_module, mock_nxbt):
    """Test that on_create_controller creates a controller."""
    emitted = []

    def capture(event, *args):
        emitted.append({"name": event, "args": args})

    # Pre-populate USER_INFO and mock request in the module's namespace
    app_module.USER_INFO["test_sid"] = {}
    mock_request = MagicMock()
    mock_request.sid = "test_sid"

    with (
        patch("nxbt.web.app.emit", capture),
        patch.object(app_module, "request", mock_request, create=True),
    ):
        app_module.on_create_controller()

    mock_nxbt.create_controller.assert_called_once()
    events = [e["name"] for e in emitted]
    assert "create_pro_controller" in events


def test_macro_execution(app_module, mock_nxbt):
    """Test that handle_macro passes the correct args to nxbt.macro."""
    macro_payload = json.dumps([0, "B 0.1s A 0.1s"])
    app_module.handle_macro(macro_payload)

    mock_nxbt.macro.assert_called_once()
    call_args = mock_nxbt.macro.call_args
    assert call_args[0][0] == 0
    assert "B" in call_args[0][1]
    assert "A" in call_args[0][1]
