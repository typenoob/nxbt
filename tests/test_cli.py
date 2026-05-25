#   Python test originally created or extracted from Hannah's work (https://github.com/hannahbee91/nxbt).
#   Some modifications might have been made to adapt to my own project.

import pytest
from unittest.mock import patch, MagicMock
from nxbt.cli import main
from nxbt import __version__


@pytest.fixture
def mock_nxbt():
    with patch("nxbt.cli.Nxbt") as mock:
        yield mock


@pytest.fixture
def mock_find_devices():
    with patch("nxbt.backends.BumbleBackend.get_switch_addresses") as mock:
        mock.return_value = []
        yield mock


@pytest.fixture
def mock_input_tui():
    with patch("nxbt.cli.InputTUI") as mock:
        yield mock


@pytest.fixture
def mock_start_web_app():
    with patch("nxbt.web.start_web_app") as mock:
        yield mock


def test_version_flag(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    captured = capsys.readouterr()
    assert __version__ in captured.out


def test_help(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--help"])
    assert exc.value.code == 0
    captured = capsys.readouterr()
    assert "Control your Nintendo Switch" in captured.out


def test_webapp_command(mock_start_web_app):
    main(["webapp", "-i", "127.0.0.1", "-p", "5000", "--usessl"])
    mock_start_web_app.assert_called_once_with(
        ip="127.0.0.1", port=5000, usessl=True, cert_path=None, debug=False
    )


def test_demo_command(mock_nxbt, capsys):
    instance = mock_nxbt.return_value
    instance.get_available_adapters.return_value = ["/org/bluez/hci0"]
    instance.create_controller.return_value = 0
    instance.macro.return_value = "macro_id"
    instance.state = {
        0: {"state": "connected", "finished_macros": ["macro_id", "other"]}
    }

    main(["demo"])
    captured = capsys.readouterr()
    assert "Running Demo..." in captured.out
    assert "Finished!" in captured.out


def test_macro_command_no_args_fails(capsys):
    main(["macro"])
    captured = capsys.readouterr()
    assert "No macro commands were specified" in captured.out


def test_macro_command_string(mock_nxbt, capsys):
    instance = mock_nxbt.return_value
    instance.create_controller.return_value = 0
    instance.wait_for_connection.return_value = None
    instance.macro.return_value = "mid"
    instance.state = {
        0: {"state": "connected", "finished_macros": ["mid"], "errors": []}
    }

    main(["macro", "-c", "A 0.1s"])
    captured = capsys.readouterr()
    assert "Running macro..." in captured.out
    instance.macro.assert_called()


def test_addresses_command(mock_find_devices, capsys):
    mock_find_devices.return_value = ["XX:XX:XX:XX:XX:XX"]
    main(["addresses", "-b", "bumble"])
    captured = capsys.readouterr()
    assert "num" in captured.out.lower()
    assert "XX:XX:XX:XX:XX:XX" in captured.out


def test_tui_command(mock_input_tui):
    main(["tui"])
    mock_input_tui.assert_called_once()
    mock_input_tui.return_value.start.assert_called_once()


def test_test_command_timeout(mock_nxbt, capsys):
    instance = mock_nxbt.return_value
    instance.get_available_adapters.return_value = ["hci0"]
    instance.create_controller.return_value = 0
    instance.state = {0: {"state": "connected"}}

    with patch("nxbt.cli.sleep"), patch("nxbt.cli.input", return_value=""):
        main(["test", "--timeout", "50"])

    captured = capsys.readouterr()
    assert "Connection timeout is 50 seconds" in captured.out


def test_logging_flags_default(mock_nxbt):
    instance = mock_nxbt.return_value
    instance.get_available_adapters.return_value = ["hci0"]
    instance.create_controller.return_value = 0
    instance.state = {
        0: {"state": "connected", "finished_macros": ["mid"], "errors": []}
    }
    instance.macro.return_value = "mid"

    main(["demo", "-l"])
    call_kwargs = mock_nxbt.call_args[1]
    assert call_kwargs["log_to_file"] is True


def test_logging_flags_custom(mock_nxbt):
    instance = mock_nxbt.return_value
    instance.get_available_adapters.return_value = ["hci0"]
    instance.create_controller.return_value = 0
    instance.state = {
        0: {"state": "connected", "finished_macros": ["mid"], "errors": []}
    }
    instance.macro.return_value = "mid"

    main(["demo", "--logfile", "custom.log"])
    call_kwargs = mock_nxbt.call_args[1]
    assert call_kwargs["log_to_file"] == "custom.log"
