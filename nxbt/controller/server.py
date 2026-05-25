import fcntl
import os
import time
import queue
import logging
import traceback
import atexit
import statistics as stat

from ..backends import BACKENDS

from .controller import ControllerTypes
from .protocol import ControllerProtocol
from .input import InputParser
from .utils import format_msg_controller, format_msg_switch


class ControllerServer:
    def __init__(
        self,
        controller_type,
        backend,
        state=None,
        task_queue=None,
        lock=None,
        colour_body=None,
        colour_buttons=None,
    ):
        self.logger = logging.getLogger("nxbt")
        # Cache logging level to increase performance on checks
        self.logger_level = self.logger.level

        atexit.register(self._on_exit)

        if state:
            self.state = state
        else:
            self.state = {
                "state": "",
                "finished_macros": [],
                "errors": None,
                "direct_input": None,
            }

        self.task_queue = task_queue

        self.controller_type = controller_type
        self.colour_body = colour_body
        self.colour_buttons = colour_buttons

        if lock:
            self.lock = lock

        self.reconnect_counter = 0

        # Initializing Bluetooth
        self.backend = backend

        self.protocol = ControllerProtocol(
            self.controller_type,
            self.backend.address,
            colour_body=self.colour_body,
            colour_buttons=self.colour_buttons,
        )

        self.input = InputParser(self.protocol)

        # Debug timekeeping storage array
        self.times = []

        # Initial reconnection overload protection
        self.tick = 1
        self.cached_msg = ""

    def run(self, reconnect_address=None):
        """Runs the mainloop of the controller server.

        :param reconnect_address: The Bluetooth MAC address of a
        previously connected to Nintendo Switch, defaults to None
        :type reconnect_address: string or list, optional
        """

        self.state["state"] = "initializing"

        try:
            # If we have a lock, prevent other controllers
            # from initializing at the same time and saturating the DBus,
            # potentially causing a kernel panic.
            if self.lock:
                self.lock.acquire()
            try:
                self.backend.setup(self.controller_type)
                if reconnect_address:
                    try:
                        itr, ctrl = self.reconnect(reconnect_address)
                    except OSError:
                        itr, ctrl = self.pair()
                else:
                    itr, ctrl = self.pair()
            finally:
                if self.lock:
                    self.lock.release()
            self.switch_address = itr.getpeername()[0].replace("/P", "")
            self.state["last_connection"] = self.switch_address
            # Clean up stale bonds on other backends so they don't
            # interfere with future connections.
            for name, backend_cls in BACKENDS.items():
                if type(self.backend) is backend_cls:
                    continue
                try:
                    backend_cls().remove_bonded_device(self.switch_address)
                except Exception as e:
                    self.logger.debug(f"Failed to remove bond from {name}: {e}")

            self.state["state"] = "connected"

            self.mainloop(itr, ctrl)

        except KeyboardInterrupt:
            pass
        except Exception:
            try:
                self.state["state"] = "crashed"
                self.state["errors"] = traceback.format_exc()
                return self.state
            except Exception as e:
                self.logger.debug("Error during graceful shutdown:")
                self.logger.debug(traceback.format_exc())

    def mainloop(self, itr, ctrl):
        duration_start = time.perf_counter()
        while True:
            # Start timing command processing
            timer_start = time.perf_counter()

            # Attempt to get output from Switch
            try:
                reply = itr.recv(50)
                if len(reply) > 40:
                    elapsed = (time.perf_counter() - timer_start) * 1000
                    self.logger.debug(f"recv took {elapsed:.1f}ms, len={len(reply)}")
                    self.logger.debug(format_msg_switch(reply))
            except BlockingIOError:
                reply = None

            # Getting any inputs from the task queue
            if self.task_queue:
                try:
                    while True:
                        msg = self.task_queue.get_nowait()
                        if msg and msg["type"] == "macro":
                            self.input.buffer_macro(msg["macro"], msg["macro_id"])
                        elif msg and msg["type"] == "stop":
                            self.input.stop_macro(msg["macro_id"], state=self.state)
                        elif msg and msg["type"] == "clear":
                            self.input.clear_macros()
                except queue.Empty:
                    pass

            # Set Direct Input
            if self.state["direct_input"]:
                self.input.set_controller_input(self.state["direct_input"])

            self.protocol.process_commands(reply)
            self.input.set_protocol_input(state=self.state)

            msg = self.protocol.get_report()

            if self.logger_level <= logging.DEBUG and reply and len(reply) > 45:
                self.logger.debug(format_msg_controller(msg))

            try:
                # Cache the last packet to prevent overloading the switch
                # with packets on the "Change Grip/Order" menu.
                if msg[3:] != self.cached_msg:
                    send_start = time.perf_counter()
                    itr.sendall(msg)
                    send_elapsed = (time.perf_counter() - send_start) * 1000
                    self.logger.debug(
                        f"[send] msg len={len(msg)}, sendall took {send_elapsed:.1f}ms"
                    )
                    self.cached_msg = msg[3:]
                # Send a blank packet every so often to keep the Switch
                # from disconnecting from the controller.
                elif self.tick >= 132:
                    send_start = time.perf_counter()
                    itr.sendall(msg)
                    send_elapsed = (time.perf_counter() - send_start) * 1000
                    self.logger.debug(
                        f"[send] keepalive len={len(msg)}, sendall took {send_elapsed:.1f}ms"
                    )
                    self.tick = 0
            except BlockingIOError:
                continue
            except OSError as e:
                # Attempt to reconnect to the Switch
                itr, ctrl = self.save_connection(e)
            # Figure out how long it took to process commands
            duration_end = time.perf_counter()
            duration_elapsed = duration_end - duration_start
            duration_start = duration_end

            sleep_time = 1 / 132 - duration_elapsed
            if sleep_time >= 0:
                time.sleep(sleep_time)
            self.tick += 1

            if self.logger_level <= logging.DEBUG:
                self.times.append(duration_elapsed)
                if len(self.times) > 100:
                    self.times.pop()
                mean_time = stat.mean(self.times)

                self.logger.debug(f"Tick: {self.tick}, Mean Time: {str(1 / mean_time)}")

    def _run_pairing_handshake(self, itr):
        received_first_message = False
        in_sniff_mode = True
        while True:
            try:
                reply = itr.recv(50)
                if self.logger_level <= logging.DEBUG and len(reply) > 40:
                    self.logger.debug(format_msg_switch(reply))
            except BlockingIOError:
                reply = None

            if reply:
                received_first_message = True

            self.protocol.process_commands(reply)
            msg = self.protocol.get_report()

            if self.logger_level <= logging.DEBUG and reply:
                self.logger.debug(format_msg_controller(msg))

            try:
                itr.sendall(msg)
            except BlockingIOError:
                continue

            if reply and in_sniff_mode:
                # if isinstance(self.backend, BumbleBackend):
                #     self.backend.exit_sniff_mode()
                in_sniff_mode = False

            if (
                reply
                and len(reply) > 45
                and self.protocol.vibration_enabled
                and self.protocol.player_number
            ):
                break

            if not received_first_message:
                time.sleep(1)
            else:
                time.sleep(1 / 15)

    def save_connection(self, error, state=None):  # state kept for API compat
        while self.reconnect_counter < 2:
            try:
                self.logger.debug("Attempting to reconnect")
                self.protocol = ControllerProtocol(
                    self.controller_type,
                    self.backend.address,
                    colour_body=self.colour_body,
                    colour_buttons=self.colour_buttons,
                )
                self.input.reassign_protocol(self.protocol)
                if self.lock:
                    self.lock.acquire()
                try:
                    itr, ctrl = self.reconnect(self.switch_address)
                    self._run_pairing_handshake(itr)
                    self.state["state"] = "connected"
                    return itr, ctrl
                finally:
                    if self.lock:
                        self.lock.release()
            except OSError:
                self.reconnect_counter += 1
                self.logger.debug(error)
                time.sleep(0.5)

        self.logger.debug("Connecting to any Switch")
        self.reconnect_counter = 0
        self.tick = 1

        self.protocol = ControllerProtocol(
            self.controller_type,
            self.backend.address,
            colour_body=self.colour_body,
            colour_buttons=self.colour_buttons,
        )
        self.input.reassign_protocol(self.protocol)

        if self.controller_type == ControllerTypes.PRO_CONTROLLER:
            self.input.current_macro_commands = "L R 0.0s".strip(" ").split(" ")
        elif self.controller_type == ControllerTypes.JOYCON_L:
            self.input.current_macro_commands = "JCL_SL JCL_SR 0.0s".strip(" ").split(
                " "
            )
        elif self.controller_type == ControllerTypes.JOYCON_R:
            self.input.current_macro_commands = "JCR_SL JCR_SR 0.0s".strip(" ").split(
                " "
            )

        if self.lock:
            self.lock.acquire()
        try:
            itr, ctrl = self.pair()
        finally:
            if self.lock:
                self.lock.release()

        self.state["state"] = "connected"
        self.switch_address = itr.getsockname()[0]

        return itr, ctrl

    def pair(self):
        """Listens for and pairs with an incoming Nintendo Switch connection."""
        while True:
            try:
                self.state["state"] = "connecting"
                itr, ctrl = self.backend.accept()
                self.protocol.process_commands(None)
                itr.sendall(self.protocol.get_report())
                fcntl.fcntl(itr, fcntl.F_SETFL, os.O_NONBLOCK)
                self._run_pairing_handshake(itr)
                break
            except OSError as e:
                self.logger.debug(e)

        self.input.exited_grip_order_menu = False
        return itr, ctrl

    def reconnect(self, reconnect_address):
        """Reconnects to a Switch at the given address.

        :param reconnect_address: The Bluetooth MAC address of the Switch
        :type reconnect_address: string or list
        """
        self.state["state"] = "reconnecting"
        itr, ctrl = self.backend.reconnect(reconnect_address)
        fcntl.fcntl(itr, fcntl.F_SETFL, os.O_NONBLOCK)
        self.protocol.process_commands(None)
        itr.sendall(self.protocol.get_report())
        return itr, ctrl

    def _on_exit(self):
        self.logger.debug("on exiting...")
