#   Python test originally created or extracted from Hannah's work (https://github.com/hannahbee91/nxbt).
#   Some modifications might have been made to adapt to my own project.

import pytest
from unittest.mock import patch, MagicMock
from nxbt.cli import (
    DEMO_MACRO_DEFAULT,
    FirmwareVersion,
    demo_macro_for_firmware,
    main,
)
from nxbt import __version__


@pytest.fixture
def mock_nxbt():
    with patch("nxbt.cli.Nxbt") as mock:
        yield mock


@pytest.fixture(autouse=True)
def mock_bluetooth_adapters():
    """Machines without Bluetooth still need adapter discovery mocked."""
    with patch(
        "nxbt.backends.BumbleBackend.get_available_adapters",
        return_value={"adapters": ["hci-socket:0"], "has_permissions": True},
    ):
        yield


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
        ip="127.0.0.1",
        port=5000,
        usessl=True,
        cert_path=None,
        debug=False,
        backend="bumble",
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


def demo_macro_sent(mock_nxbt, firmware):
    """Run the demo against a firmware and return the macro handed to Nxbt."""
    instance = mock_nxbt.return_value
    instance.create_controller.return_value = 0
    instance.macro.return_value = "macro_id"
    instance.state = {
        0: {"state": "connected", "finished_macros": ["macro_id"], "errors": []}
    }

    main(["demo", "-f", firmware])
    return instance.macro.call_args[0][1]


def test_demo_firmware_version(mock_nxbt):
    switch2_macro = demo_macro_for_firmware(FirmwareVersion("23.0.1"))
    assert switch2_macro != DEMO_MACRO_DEFAULT

    # Inside the verified range: >=23.0.1,<24.0, ordered numerically.
    for firmware in ("23.0.1", "23.0.10", "23.2.0", "23.5.0"):
        assert demo_macro_sent(mock_nxbt, firmware) == switch2_macro
    # Outside it, on either side: the pre-Switch 2 layout.
    assert demo_macro_sent(mock_nxbt, "23.0.0") == DEMO_MACRO_DEFAULT
    assert demo_macro_sent(mock_nxbt, "24.0.0") == DEMO_MACRO_DEFAULT
    assert demo_macro_sent(mock_nxbt, "12.0.0") == DEMO_MACRO_DEFAULT


def test_firmware_comparison_is_numeric_not_lexicographic():
    """A string sort would rank "9.0.0" above "23.0.1" and match the range."""
    for firmware in ("2.0.0", "9.0.0", "10.2.0", "13.0.0", "19.0.1", "24.0.0"):
        assert demo_macro_for_firmware(FirmwareVersion(firmware)) is DEMO_MACRO_DEFAULT


def test_demo_rejects_an_unparsable_firmware():
    with pytest.raises(SystemExit) as exc:
        main(["demo", "-f", "switch-2"])
    assert exc.value.code == 2


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
