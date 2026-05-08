#   Python test originally created or extracted from Hannah's work (https://github.com/hannahbee91/nxbt).
#   Some modifications might have been made to adapt to my own project.

import unittest
from unittest.mock import MagicMock, patch
from nxbt.tui import LoadingSpinner, ControllerTUI, InputTUI


class TestLoadingSpinner:
    @patch("time.perf_counter", return_value=1000.0)
    def test_initialization(self, _):
        spinner = LoadingSpinner()
        assert spinner.current_char_index == 0
        assert spinner.creation_time == spinner.last_update_time

    @patch("time.perf_counter", return_value=1000.0)
    def test_get_spinner_char_cycles(self, _):
        spinner = LoadingSpinner()
        first_char = spinner.get_spinner_char()
        assert first_char in LoadingSpinner.SPINNER_CHARS

    @patch("time.perf_counter", return_value=1000.0)
    def test_spinner_update_logic(self, mock_time):
        spinner = LoadingSpinner()
        assert spinner.current_char_index == 0

        # Advance 0.02s (less than 0.07s threshold) — should not update
        mock_time.return_value = 1000.02
        spinner.get_spinner_char()
        assert spinner.current_char_index == 0, "Should not update if < 0.07s passed"

        # Advance 0.1s (more than 0.07s) — should increment
        mock_time.return_value = 1000.1
        spinner.get_spinner_char()
        assert spinner.current_char_index == 1, "Should increment index"


class TestControllerTUI(unittest.TestCase):
    def setUp(self):
        self.mock_term = MagicMock()
        # Mocking terminal attributes usually used
        self.mock_term.width = 80
        self.mock_term.height = 24
        self.mock_term.move_xy = MagicMock(return_value="")
        self.mock_term.white = MagicMock(return_value="")
        self.mock_term.on_black = MagicMock(return_value="")
        self.mock_term.bold_black_on_white = MagicMock(side_effect=lambda x: f"[[{x}]]")

        self.controller = ControllerTUI(self.mock_term)

    def test_init(self):
        self.assertEqual(self.controller.term, self.mock_term)
        self.assertFalse(self.controller.remote_connection)

    def test_remote_connection_status(self):
        self.controller.set_remote_connection_status(True)
        self.assertTrue(self.controller.remote_connection)

        self.controller.set_remote_connection_status(False)
        self.assertFalse(self.controller.remote_connection)

    def test_toggle_auto_keypress_deactivation(self):
        self.assertTrue(self.controller.auto_keypress_deactivation)  # Default check

        self.controller.toggle_auto_keypress_deactivation(False)
        self.assertFalse(self.controller.auto_keypress_deactivation)

        self.controller.toggle_auto_keypress_deactivation(True)
        self.assertTrue(self.controller.auto_keypress_deactivation)

    def test_activate_control(self):
        # Initial state
        original_val = self.controller.CONTROLS["A"]

        self.controller.activate_control("A")
        self.assertNotEqual(self.controller.CONTROLS["A"], original_val)
        self.assertEqual(self.controller.CONTROLS["A"], f"[[{original_val}]]")

        # Test activating with text
        self.controller.activate_control("B", "Pressed")
        self.assertEqual(self.controller.CONTROLS["B"], "Pressed")

    def test_deactivate_control(self):
        original_val = self.controller.DEFAULT_CONTROLS["A"]
        self.controller.activate_control("A")

        self.controller.deactivate_control("A")
        self.assertEqual(self.controller.CONTROLS["A"], original_val)

    def test_render_controller(self):
        with patch("builtins.print") as mock_print:
            self.controller.render_controller()
            self.assertTrue(mock_print.called)

    @patch("time.perf_counter")
    def test_check_auto_deactivate(self, mock_perf_counter):
        # Setup
        mock_perf_counter.return_value = 100.0
        self.controller.activate_control("A")
        # Validate active
        self.assertNotEqual(
            self.controller.CONTROLS["A"], self.controller.DEFAULT_CONTROLS["A"]
        )

        # Advance time < 0.25 (threshold is 0.25s)
        mock_perf_counter.return_value = 100.2
        self.controller.render_controller()  # this triggers check
        self.assertNotEqual(
            self.controller.CONTROLS["A"], self.controller.DEFAULT_CONTROLS["A"]
        )

        # Advance time > 0.25
        mock_perf_counter.return_value = 100.3
        self.controller.render_controller()
        self.assertEqual(
            self.controller.CONTROLS["A"], self.controller.DEFAULT_CONTROLS["A"]
        )


class TestInputTUI(unittest.TestCase):
    @patch("nxbt.tui.Nxbt")
    def setUp(self, MockNxbt):
        # Mock pynput to prevent SystemExit on import failure in CI/headless envs
        self.pynput_patcher = patch.dict(
            "sys.modules", {"pynput": MagicMock(), "pynput.keyboard": MagicMock()}
        )
        self.pynput_patcher.start()

        self.mock_nxbt = MockNxbt.return_value
        self.mock_nxbt.create_controller.return_value = 0

        # Patch detect_remote_connection to avoid system calls during init
        self.patcher = patch(
            "nxbt.tui.InputTUI.detect_remote_connection", return_value=False
        )
        self.mock_detect = self.patcher.start()

        self.input_tui = InputTUI(
            reconnect_target=None, debug=False, logfile=False, force_remote=False
        )

    def tearDown(self):
        self.patcher.stop()
        self.pynput_patcher.stop()

    def test_initialization(self):
        self.assertIsNone(self.input_tui.reconnect_target)
        self.assertFalse(self.input_tui.debug)

    def test_render_start_screen(self):
        mock_term = MagicMock()
        mock_term.width = 80
        mock_term.height = 24
        mock_term.move_xy.return_value = ""
        mock_term.center.return_value = ""
        mock_term.bold = MagicMock(return_value="")

        with patch("builtins.print") as mock_print:
            self.input_tui.render_start_screen(mock_term, "Loading...")
            self.assertTrue(mock_print.called)

    def test_render_top_bar(self):
        mock_term = MagicMock()
        mock_term.width = 80
        mock_term.move_xy.return_value = ""
        mock_term.on_white = MagicMock(return_value="")
        mock_term.black = MagicMock(return_value="")

        with patch("builtins.print") as mock_print:
            self.input_tui.render_top_bar(mock_term)
            self.assertTrue(mock_print.called)

    def test_check_for_disconnect(self):
        mock_term = MagicMock()
        # Manually set attributes typically set in mainloop
        self.input_tui.nx = self.mock_nxbt
        self.input_tui.controller_index = 0

        self.mock_nxbt.state = {0: {"state": "connected"}}

        # Should return normally if connected
        self.input_tui.check_for_disconnect(mock_term)

        # If crashed, should raise ConnectionError (but it prints errors first)
        self.mock_nxbt.state = {0: {"state": "crashed", "errors": "Some error"}}
        # It also sleeps and clears, mock those
        with (
            patch("time.sleep"),
            patch.object(mock_term, "clear", return_value=""),
            patch("builtins.print"),
        ):
            with self.assertRaises(ConnectionError):
                self.input_tui.check_for_disconnect(mock_term)


class TestRemoteDetection(unittest.TestCase):
    @patch("nxbt.tui.Nxbt")
    @patch("psutil.Process")
    @patch("os.getppid")
    def test_detect_remote_connection(self, mock_getppid, mock_process_cls, mock_nxbt):
        # Setup mocks
        mock_getppid.return_value = 100

        # Case 1: No remote process found
        # Hierarchy: 100 -> 50 -> 0
        def side_effect_process(pid):
            p = MagicMock()
            if pid == 100:
                p.name.return_value = "python"
                p.ppid.return_value = 50
            elif pid == 50:
                p.name.return_value = "bash"
                p.ppid.return_value = 0
            else:
                p.ppid.return_value = 0
            return p

        mock_process_cls.side_effect = side_effect_process

        # Instantiate InputTUI without patching detect_remote_connection,
        # but we need to prevent pynput import check failure if possible?
        # No, if not remote_connection, it tries import pynput.
        # Assuming pynput is installed in env or mocked.
        # But we are mocking os/psutil, so pynput import might happen.
        # We can simulate force_remote=False

        with patch(
            "nxbt.tui.InputTUI.detect_remote_connection",
            side_effect=InputTUI.detect_remote_connection,
            autospec=True,
        ):
            # We need to call the UNBOUND method or bound?
            # Actually, if we want to test detect_remote_connection logic isolated, we don't need to instantiate InputTUI fully.
            # We can just call InputTUI.detect_remote_connection(None) if it doesn't use self.
            # Looking at code: it does NOT use self!
            # def detect_remote_connection(self): ...
            # It acts like a static method but is an instance method.

            is_remote = InputTUI.detect_remote_connection(None)
            self.assertFalse(is_remote)

        # Case 2: sshd found
        # Hierarchy: 100 -> 50 -> 0. 50 is sshd.
        def side_effect_process_ssh(pid):
            p = MagicMock()
            if pid == 100:
                p.name.return_value = "python"
                p.ppid.return_value = 50
            elif pid == 50:
                p.name.return_value = "sshd"
                p.ppid.return_value = 0  # stop loop
            else:
                p.ppid.return_value = 0
            return p

        mock_process_cls.side_effect = side_effect_process_ssh

        is_remote = InputTUI.detect_remote_connection(None)
        self.assertTrue(is_remote)


if __name__ == "__main__":
    unittest.main()
