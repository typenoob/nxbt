import asyncio
import logging
import os
import random
import subprocess
import threading
import time
from pathlib import Path
from shutil import which

from dbus_fast import BusType, Message, Variant
from dbus_fast.aio.message_bus import MessageBus

AGENT_PATH = "/nxbt/agent"


SERVICE_NAME = "org.bluez"
BLUEZ_OBJECT_PATH = "/org/bluez"
ADAPTER_INTERFACE = SERVICE_NAME + ".Adapter1"
PROFILEMANAGER_INTERFACE = SERVICE_NAME + ".ProfileManager1"
DEVICE_INTERFACE = SERVICE_NAME + ".Device1"

OM_IFACE = "org.freedesktop.DBus.ObjectManager"
PROPS_IFACE = "org.freedesktop.DBus.Properties"


def _run_async(coro):
    """Run an async dbus call synchronously."""
    return asyncio.run(coro)


async def _get_managed_objects(bus, service_name=SERVICE_NAME):
    """Fetch managed objects from a D-Bus service."""
    msg = Message(
        destination=service_name,
        path="/",
        interface=OM_IFACE,
        member="GetManagedObjects",
    )
    reply = await bus.call(msg)
    return reply.body[0]


async def _get_property(bus, path, interface, prop):
    """Get a D-Bus property, unwrapping the Variant."""
    msg = Message(
        destination=SERVICE_NAME,
        path=path,
        interface=PROPS_IFACE,
        member="Get",
        signature="ss",
        body=[interface, prop],
    )
    reply = await bus.call(msg)
    variant = reply.body[0]
    return variant.value if hasattr(variant, "value") else variant


async def _set_property(bus, path, interface, prop, value):
    """Set a D-Bus property."""
    sig = _guess_signature(value)
    msg = Message(
        destination=SERVICE_NAME,
        path=path,
        interface=PROPS_IFACE,
        member="Set",
        signature="ssv",
        body=[interface, prop, Variant(sig, value)],
    )
    await bus.call(msg)


async def _call_method(bus, path, interface, member, signature="", body=None):
    """Call a D-Bus method."""
    msg = Message(
        destination=SERVICE_NAME,
        path=path,
        interface=interface,
        member=member,
        signature=signature,
        body=body or [],
    )
    return await bus.call(msg)


def _guess_signature(value):
    """Guess the D-Bus signature for a Python value."""
    if isinstance(value, bool):
        return "b"
    if isinstance(value, int):
        return "u"
    if isinstance(value, str):
        return "s"
    if isinstance(value, dict):
        return "a{sv}"
    if isinstance(value, list):
        return "as"
    return "s"


def find_object_path(service_name, interface_name, object_name=None):
    """Searches for a D-Bus object path that contains a specified interface
    under a specified service.

    :param bus: A DBus object used to access the DBus.
    :type bus: DBus
    :param service_name: The name of a D-Bus service to search for the
    object path under.
    :type service_name: string
    :param interface_name: The name of a D-Bus interface to search for
    within objects under the specified service.
    :type interface_name: string
    :param object_name: The name or ending of the object path,
    defaults to None
    :type object_name: string, optional
    :return: The D-Bus object path or None, if no matching object
    can be found
    :rtype: string
    """

    async def _find():
        conn = await MessageBus(bus_type=BusType.SYSTEM).connect()
        objects = await _get_managed_objects(conn, service_name)
        conn.disconnect()

        for path, ifaces in objects.items():
            managed_interface = ifaces.get(interface_name)
            if managed_interface is None:
                continue
            elif (
                not object_name
                or object_name == managed_interface.get("Address")
                or path.endswith(object_name)
            ):
                return str(path)
        return None

    return _run_async(_find())


def find_objects(service_name, interface_name):
    """Searches for D-Bus objects that contain a specified interface
    under a specified service.

    :param bus: A DBus object used to access the DBus.
    :type bus: DBus
    :param service_name: The name of a D-Bus service to search for the
    object path under.
    :type service_name: string
    :param interface_name: The name of a D-Bus interface to search for
    within objects under the specified service.
    :type interface_name: string
    :return: The D-Bus object paths matching the arguments
    :rtype: array
    """

    async def _find():
        conn = await MessageBus(bus_type=BusType.SYSTEM).connect()
        objects = await _get_managed_objects(conn, service_name)
        conn.disconnect()

        paths = []
        for path, ifaces in objects.items():
            if interface_name in ifaces:
                paths.append(str(path))
        return paths

    return _run_async(_find())


def toggle_clean_bluez(toggle):
    """Enables or disables all BlueZ plugins,
    BlueZ compatibility mode, and removes all extraneous
    SDP Services offered.
    Requires root user to be run. The units and Bluetooth
    service will not be restarted if the input plugin
    already matches the toggle.

    :param toggle: A boolean element indicating if BlueZ
    should be cleaned (True) or not (False)
    :type toggle: boolean
    :raises PermissionError: If the user is not root
    :raises Exception: If the units can't be reloaded
    :raises Exception: If sdptool, hciconfig, or hcitool are not available.
    """
    logger = logging.getLogger("nxbt")

    # Check systemd is present
    res = _run_command(["ps", "--no-headers", "-o", "comm", "1"])
    if res.stdout.decode("utf-8").strip() != "systemd":
        logger.debug("systemd not found")
        return
    service_path = "/lib/systemd/system/bluetooth.service"
    override_dir = Path("/run/systemd/system/bluetooth.service.d")
    override_path = override_dir / "nxbt.conf"

    if toggle:
        if override_path.is_file():
            # Override exist, no need to restart bluetooth
            return

        with open(service_path, encoding="utf-8") as f:
            for line in f:
                if line.startswith("ExecStart="):
                    exec_start = line.strip() + " --compat --noplugin=*"
                    break
            else:
                raise Exception("systemd service file doesn't have a ExecStart line")

        override = f"[Service]\nExecStart=\n{exec_start}"

        override_dir.mkdir(parents=True, exist_ok=True)
        with override_path.open("w") as f:
            f.write(override)
    else:
        try:
            os.remove(override_path)
        except FileNotFoundError:
            # Override doesn't exist, no need to restart bluetooth
            return

    # Reload units
    _run_command(["systemctl", "daemon-reload"])

    # Reload the bluetooth service with input disabled
    _run_command(["systemctl", "restart", "bluetooth"])

    # Kill a bit of time here to ensure all services have restarted
    time.sleep(0.5)
    logger.debug("systemd found and bluetooth reloaded")


def clean_sdp_records():
    """Cleans all SDP Records from BlueZ with sdptool

    :raises Exception: On CLI error or sdptool missing
    """
    # TODO: sdptool is deprecated in BlueZ 5. This should ideally
    # use the DBus API, however, bugs seemingly exist with the
    # UnregisterProfile interface.

    # Check if sdptool is available for use
    if which("sdptool") is None:
        raise Exception(
            "sdptool is not available on this system."
            + "If you can, please install this tool, as "
            + "it is required for proper functionality."
        )

    # Enable Read/Write to the SDP server. This is a remedy for a
    # compatibility mode bug introduced in later versions of BlueZ 5
    _run_command(["chmod", "777", "/var/run/sdp"])

    # Identify/List all SDP services available with sdptool
    result = _run_command(["sdptool", "browse", "local"]).stdout.decode("utf-8")
    if result is None or len(result.split("\n\n")) < 1:
        return

    # Record all service record handles
    exceptions = ["PnP Information"]
    service_rec_handles = []
    for rec in result.split("\n\n"):
        # Skip if exception is in record
        exception_found = False
        for exception in exceptions:
            if exception in rec:
                exception_found = True
                break
        if exception_found:
            continue

        # Read lines and add Record Handles to the list
        for line in rec.split("\n"):
            if "Service RecHandle" in line:
                service_rec_handles.append(line.split(" ")[2])

    # Delete all found service records
    if len(service_rec_handles) > 0:
        for record_handle in service_rec_handles:
            _run_command(["sdptool", "del", record_handle])


def _run_command(command):
    """Runs a specified command on the shell of the system.
    If the command is run unsuccessfully, an error is raised.
    The command must be in the form of an array with each term
    individually listed. Eg: ["which", "bash"]

    :param command: A list of command terms
    :type command: list
    :raises Exception: On command failure or error
    """
    result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    cmd_err = result.stderr.decode("utf-8").replace("\n", "")
    if cmd_err != "":
        raise Exception(cmd_err)

    return result


def get_random_controller_mac():
    """Generates a random Switch-compliant MAC address"""

    def seg():
        random_number = random.randint(0, 255)
        hex_number = str(hex(random_number))
        hex_number = hex_number[2:].upper()
        return str(hex_number)

    return f"7C:BB:8A:{seg()}:{seg()}:{seg()}"


def replace_mac_addresses(adapter_paths, addresses):
    """Replaces a list of adapter's Bluetooth MAC addresses
    with Switch-compliant Controller MAC addresses. If the
    addresses argument is specified, the adapter path's
    MAC addresses will be reset to respective (index-wise)
    address in the list.

    :param adapter_paths: A list of Bluetooth adapter paths
    :type adapter_paths: list
    :param addresses: A list of Bluetooth MAC addresses,
    defaults to False
    :type addresses: bool, optional
    """
    if which("hcitool") is None:
        raise Exception(
            "hcitool is not available on this system."
            + "If you can, please install this tool, as "
            + "it is required for proper functionality."
        )
    if which("hciconfig") is None:
        raise Exception(
            "hciconfig is not available on this system."
            + "If you can, please install this tool, as "
            + "it is required for proper functionality."
        )

    if addresses:
        assert len(addresses) == len(adapter_paths)

    for i in range(len(adapter_paths)):
        adapter_id = adapter_paths[i].split("/")[-1]
        mac = addresses[i].split(":")
        cmds = [
            "hcitool",
            "-i",
            adapter_id,
            "cmd",
            "0x3f",
            "0x001",
            f"0x{mac[5]}",
            f"0x{mac[4]}",
            f"0x{mac[3]}",
            f"0x{mac[2]}",
            f"0x{mac[1]}",
            f"0x{mac[0]}",
        ]
        _run_command(cmds)
        _run_command(["hciconfig", adapter_id, "reset"])


def find_devices_by_alias(alias, return_path=False, created_bus=None):
    """Finds the Bluetooth addresses of devices
    that have a specified Bluetooth alias. Aliases
    are converted to uppercase before comparison
    as BlueZ usually converts aliases to uppercase.

    :param address: The Bluetooth MAC address
    :type address: string
    :return: The path to the D-Bus object or None
    :rtype: string or None
    """

    async def _find():
        own_bus = created_bus is None
        if own_bus:
            bus = await MessageBus(bus_type=BusType.SYSTEM).connect()
        else:
            bus = created_bus
        objects = await _get_managed_objects(bus)

        addresses = []
        matching_paths = []
        for path, ifaces in objects.items():
            if DEVICE_INTERFACE not in ifaces:
                continue
            device_alias = (
                await _get_property(bus, path, DEVICE_INTERFACE, "Alias")
            ).upper()
            device_addr = (
                await _get_property(bus, path, DEVICE_INTERFACE, "Address")
            ).upper()

            if device_alias.upper() == alias.upper():
                addresses.append(device_addr)
                matching_paths.append(path)

        if own_bus:
            bus.disconnect()
        return addresses, matching_paths

    addresses, matching_paths = _run_async(_find())

    if return_path:
        return addresses, matching_paths
    else:
        return addresses


def disconnect_devices_by_alias(alias, created_bus=None):
    """Disconnects all devices matching an alias.

    :param alias: The device's alias
    :type alias: string
    """

    async def _disconnect():
        own_bus = created_bus is None
        if own_bus:
            bus = await MessageBus(bus_type=BusType.SYSTEM).connect()
        else:
            bus = created_bus
        objects = await _get_managed_objects(bus)

        for path, ifaces in objects.items():
            if DEVICE_INTERFACE not in ifaces:
                continue
            device_alias = (
                await _get_property(bus, path, DEVICE_INTERFACE, "Alias")
            ).upper()

            if device_alias.upper() == alias.upper():
                try:
                    await _call_method(bus, path, DEVICE_INTERFACE, "Disconnect")
                except Exception as e:
                    print(e)

        if own_bus:
            bus.disconnect()

    _run_async(_disconnect())


class BlueZ:
    """Exposes the BlueZ D-Bus API as a Python object."""

    def __init__(self, adapter_path="/org/bluez/hci0"):
        self.logger = logging.getLogger("nxbt")

        self.device_path = adapter_path

        # If we weren't able to find an adapter with the specified ID,
        # try to find any usable Bluetooth adapter
        if self.device_path is None:
            self.device_path = find_object_path(SERVICE_NAME, ADAPTER_INTERFACE)

        # If we aren't able to find an adapter still
        if self.device_path is None:
            raise Exception("Unable to find a bluetooth adapter")

        # Load the adapter's interface
        self.logger.debug(f"Using adapter under object path: {self.device_path}")

        self.device_id = self.device_path.split("/")[-1]

    def _prop(self, prop):
        """Get a property on the adapter."""

        async def _do():
            bus = await MessageBus(bus_type=BusType.SYSTEM).connect()
            val = await _get_property(bus, self.device_path, ADAPTER_INTERFACE, prop)
            bus.disconnect()
            return val

        return _run_async(_do())

    def _set_prop(self, prop, value):
        """Set a property on the adapter."""

        async def _do():
            bus = await MessageBus(bus_type=BusType.SYSTEM).connect()
            await _set_property(bus, self.device_path, ADAPTER_INTERFACE, prop, value)
            bus.disconnect()

        _run_async(_do())

    def _call_adapter(self, member, signature="", body=None):
        """Call a method on the adapter interface."""

        async def _do():
            bus = await MessageBus(bus_type=BusType.SYSTEM).connect()
            await _call_method(
                bus, self.device_path, ADAPTER_INTERFACE, member, signature, body
            )
            bus.disconnect()

        _run_async(_do())

    @property
    def address(self):
        """Gets the Bluetooth MAC address of the Bluetooth adapter.

        :return: The Bluetooth Adapter's MAC address
        :rtype: string
        """

        return self._prop("Address").upper()

    def set_address(self, mac):
        """Sets the Bluetooth MAC address of the Bluetooth adapter.
        The hciconfig CLI is required for setting the address.
        For changes to apply, the Bluetooth interface needs to be
        restarted.

        :param mac: A Bluetooth MAC address in
        the form of "XX:XX:XX:XX:XX:XX
        :type mac: str
        :raises PermissionError: On run as non-root user
        :raises Exception: On CLI errors
        """
        if which("hcitool") is None:
            raise Exception(
                "hcitool is not available on this system."
                + "If you can, please install this tool, as "
                + "it is required for proper functionality."
            )
        # Reverse MAC (element position-wise) for use with hcitool
        mac = mac.split(":")
        cmds = [
            "hcitool",
            "-i",
            self.device_id,
            "cmd",
            "0x3f",
            "0x001",
            f"0x{mac[5]}",
            f"0x{mac[4]}",
            f"0x{mac[3]}",
            f"0x{mac[2]}",
            f"0x{mac[1]}",
            f"0x{mac[0]}",
        ]
        _run_command(cmds)
        _run_command(["hciconfig", self.device_id, "reset"])

    def set_class(self, device_class):
        if which("hciconfig") is None:
            raise Exception(
                "hciconfig is not available on this system."
                + "If you can, please install this tool, as "
                + "it is required for proper functionality."
            )
        _run_command(["hciconfig", self.device_id, "class", device_class])

    def reset_adapter(self):
        if which("hciconfig") is None:
            raise Exception(
                "hciconfig is not available on this system."
                + "If you can, please install this tool, as "
                + "it is required for proper functionality."
            )
        _run_command(["hciconfig", self.device_id, "reset"])

    @property
    def name(self):
        """Gets the name of the Bluetooth adapter.

        :return: The name of the Bluetooth adapter.
        :rtype: string
        """

        return self._prop("Name")

    @property
    def alias(self):
        """Gets the alias of the Bluetooth adapter. This value is used
        as the "friendly" name of the adapter when communicating over
        Bluetooth.

        :return: The adapter's alias
        :rtype: string
        """

        return self._prop("Alias")

    def set_alias(self, value):
        """Asynchronously sets the alias of the Bluetooth adapter.
        If you wish to check the set value, a time delay is needed
        before the alias getter is run.

        :param value: The new value to be set as the adapter's alias
        :type value: string
        """

        self._set_prop("Alias", value)

    @property
    def pairable(self):
        """Gets the pairable status of the Bluetooth adapter.

        :return: A boolean value representing if the adapter is set as
        pairable or not
        :rtype: boolean
        """

        return bool(self._prop("Pairable"))

    def set_pairable(self, value):
        """Sets the pariable boolean status of the Bluetooth adapter.

        :param value: A boolean value representing if the adapter is
        pairable or not.
        :type value: boolean
        """

        self._set_prop("Pairable", value)

    def setup_auto_accept_pairing(self):
        """Registers a NoInputNoOutput agent via dbus_fast to auto-accept
        all incoming pairing requests without user interaction.
        """

        if getattr(self, "_agent_thread", None) is not None:
            return  # already running

        async def _run_agent():
            bus = await MessageBus(bus_type=BusType.SYSTEM).connect()
            msg = Message(
                destination=SERVICE_NAME,
                path=BLUEZ_OBJECT_PATH,
                interface=f"{SERVICE_NAME}.AgentManager1",
                member="RegisterAgent",
                signature="os",
                body=[AGENT_PATH, "NoInputNoOutput"],
            )
            await bus.call(msg)
            msg = Message(
                destination=SERVICE_NAME,
                path=BLUEZ_OBJECT_PATH,
                interface=f"{SERVICE_NAME}.AgentManager1",
                member="RequestDefaultAgent",
                signature="o",
                body=[AGENT_PATH],
            )
            await bus.call(msg)
            await asyncio.Event().wait()  # keep agent alive forever

        self._agent_thread = threading.Thread(
            target=lambda: asyncio.run(_run_agent()), daemon=True, name="nxbt-bt-agent"
        )
        self._agent_thread.start()
        self.logger.debug("Auto-accept agent registered")

    @property
    def pairable_timeout(self):
        """Gets the timeout time (in seconds) for how long the adapter
        should remain as pairable. Defaults to 0 (no timeout).

        :return: The pairable timeout in seconds
        :rtype: int
        """

        return self._prop("PairableTimeout")

    def set_pairable_timeout(self, value):
        """Sets the timeout time (in seconds) for the pairable property.

        :param value: The pairable timeout value in seconds
        :type value: int
        """

        self._set_prop("PairableTimeout", value)

    @property
    def discoverable(self):
        """Gets the discoverable status of the Bluetooth adapter

        :return: The boolean status of the discoverable status
        :rtype: boolean
        """

        return bool(self._prop("Discoverable"))

    def set_discoverable(self, value):
        """Sets the discoverable boolean status of the Bluetooth adapter.

        :param value: A boolean value representing if the Bluetooth adapter
        is discoverable or not.
        :type value: boolean
        """

        self._set_prop("Discoverable", value)

    @property
    def discoverable_timeout(self):
        """Gets the timeout time (in seconds) for how long the adapter
        should remain as discoverable. Defaults to 180 (3 minutes).

        :return: The discoverable timeout in seconds
        :rtype: int
        """

        return self._prop("DiscoverableTimeout")

    def set_discoverable_timeout(self, value):
        """Sets the discoverable time (in seconds) for the discoverable
        property. Setting this property to 0 results in an infinite
        discoverable timeout.

        :param value: The discoverable timeout value in seconds
        :type value: int
        """

        self._set_prop("DiscoverableTimeout", value)

    @property
    def device_class(self):
        """Gets the Bluetooth class of the device. This represents what type
        of device this reporting as (Ex: Gamepad, Headphones, etc).

        :return: A 32-bit hexadecimal Integer representing the
        Bluetooth Code for a given device type.
        :rtype: string
        """

        # This is another hacky bit. We're using hciconfig here instead
        # of the D-Bus API so that results match the setter. See the
        # setter for further justification on using hciconfig.
        result = subprocess.run(
            ["hciconfig", self.device_id, "class"], stdout=subprocess.PIPE
        )
        device_class = result.stdout.decode("utf-8").split("Class: ")[1][0:8]

        return device_class

    def set_device_class(self, device_class):
        """Sets the Bluetooth class of the device. This represents what type
        of device this reporting as (Ex: Gamepad, Headphones, etc).
        Note: To work this function *MUST* be run as the super user. An
        exception is returned if this function is run without elevation.

        :param device_class: A 32-bit Hexadecimal integer
        :type device_class: string
        :raises PermissionError: If user is not root
        :raises ValueError: If the device class is not length 8
        :raises Exception: On inability to set class
        """

        if os.geteuid() != 0:
            raise PermissionError("The device class must be set as root")

        if len(device_class) != 8:
            raise ValueError("Device class must be length 8")

        # This is a bit of a hack. BlueZ allows you to set this value, however,
        # a config file needs to filled and the BT daemon restarted. This is a
        # good compromise but requires super user privileges. Not ideal.
        result = subprocess.run(
            ["hciconfig", self.device_id, "class", device_class], stderr=subprocess.PIPE
        )

        # Checking if there was a problem setting the device class
        cmd_err = result.stderr.decode("utf-8").replace("\n", "")
        if cmd_err != "":
            raise Exception(cmd_err)

    @property
    def powered(self):
        """The powered state of the adapter (on/off) as a boolean value.

        :return: A boolean representing the powered state of the adapter.
        :rtype: boolean
        """

        return bool(self._prop("Powered"))

    def set_powered(self, value):
        """Switches the adapter on or off.

        :param value: A boolean value switching the adapter on or off
        :type value: boolean
        """

        self._set_prop("Powered", value)

    def register_profile(self, profile_path, uuid, opts):
        """Registers an SDP record on the BlueZ SDP server.

        Options (non-exhaustive, refer to BlueZ docs for
        the complete list):

        - Name: Human readable name of the profile

        - Role: Specifies precise local role. Either "client"
        or "servier".

        - RequireAuthentication: A boolean value indicating if
        pairing is required before connection.

        - RequireAuthorization: A boolean value indiciating if
        authorization is needed before connection.

        - AutoConnect: A boolean value indicating whether a
        connection can be forced if a client UUID is present.

        - ServiceRecord: An XML SDP record as a string.

        :param profile_path: The path for the SDP record
        :type profile_path: string
        :param uuid: The UUID for the SDP record
        :type uuid: string
        :param opts: The options for the SDP server
        :type opts: dict
        """

        async def _do():
            bus = await MessageBus(bus_type=BusType.SYSTEM).connect()
            # Wrap dict values in Variant objects for a{sv}
            variant_opts = {
                k: Variant("b", v) if isinstance(v, bool) else Variant("s", v)
                for k, v in opts.items()
            }
            reply = await _call_method(
                bus,
                BLUEZ_OBJECT_PATH,
                PROFILEMANAGER_INTERFACE,
                "RegisterProfile",
                "osa{sv}",
                [profile_path, uuid, variant_opts],
            )
            bus.disconnect()
            return reply

        return _run_async(_do())

    def unregister_profile(self, profile):
        """Unregisters a given SDP record from the BlueZ SDP server.

        :param profile: A SDP record profile object
        :type profile: Profile
        """

        async def _do():
            bus = await MessageBus(bus_type=BusType.SYSTEM).connect()
            await _call_method(
                bus,
                BLUEZ_OBJECT_PATH,
                PROFILEMANAGER_INTERFACE,
                "UnregisterProfile",
                "o",
                [profile],
            )
            bus.disconnect()

        _run_async(_do())

    def reset(self):
        """Restarts the Bluetooth Service

        :raises Exception: If the bluetooth service can't be restarted
        """

        result = subprocess.run(
            ["systemctl", "restart", "bluetooth"], stderr=subprocess.PIPE
        )

        cmd_err = result.stderr.decode("utf-8").replace("\n", "")
        if cmd_err != "":
            raise Exception(cmd_err)

    def get_discovered_devices(self):
        """Gets a dict of all discovered (or previously discovered
        and connected) devices. The key is the device's dbus object
        path and the values are the device's properties.

        The following is a non-exhaustive list of the properties a
        device dictionary can contain:
        - "Address": The Bluetooth address
        - "Alias": The friendly name of the device
        - "Paired": Whether the device is paired
        - "Connected": Whether the device is presently connected
        - "UUIDs": The services a device provides

        :return: A dictionary of all discovered devices
        :rtype: dictionary
        """

        async def _get():
            bus = await MessageBus(bus_type=BusType.SYSTEM).connect()
            objects = await _get_managed_objects(bus)
            bus.disconnect()

            devices = {}
            for path, interfaces in list(objects.items()):
                if DEVICE_INTERFACE in interfaces:
                    devices[str(path)] = interfaces[DEVICE_INTERFACE]
            return devices

        return _run_async(_get())

    def discover_devices(self, alias=None, timeout=10, callback=None):
        """Runs a device discovery of the timeout length (in seconds)
        on the adapter. If specified, a callback is run, every second,
        and passed an updated list of discovered devices. An alias
        can be specified to filter discovered devices.

        The following is a non-exhaustive list of the properties a
        device dictionary can contain:
        - "Address": The Bluetooth address
        - "Alias": The friendly name of the device
        - "Paired": Whether the device is paired
        - "Connected": Whether the device is presently connected
        - "UUIDs": The services a device provides

        :param alias: The alias of a bluetooth device, defaults to None
        :type alias: string, optional
        :param timeout: The discovery timeout in seconds, defaults to 10
        :type timeout: int, optional
        :param callback: A callback function, defaults to None
        :type callback: function, optional
        :return: A dictionary of discovered devices with the object path
        as the key and the device properties as the dictionary properties
        :rtype: dictionary
        """

        # TODO: Device discovery still needs work. Currently, devices
        # are added as DBus objects while device discovery runs, however,
        # added devices linger after discovery stops. This means a device
        # can become unpairable, still show up on a new discovery session,
        # and throw an error when an attempt is made to pair it. Using DBus
        # signals ("interface added"/"property changed") does not solve
        # this issue.

        # Get all devices that have been previously discovered
        devices = self.get_discovered_devices()

        # Start discovering new devices and loop
        self.set_powered(True)
        self.set_pairable(True)
        self._call_adapter("StartDiscovery")
        try:
            for i in range(0, timeout):
                time.sleep(1)

                new_devices = self.get_discovered_devices()
                # Shallowly merging dictionaries. Latter dictionary
                # overrides the former. Requires Python 3.5
                devices = {**devices, **new_devices}

                if callback:
                    callback(devices)
        finally:
            self._call_adapter("StopDiscovery")
            time.sleep(1)

        # Filter out paired devices or devices that don't
        # match a specified alias.
        filtered_devices = {}
        for key in devices.keys():
            # Filter for devices matching alias, if specified
            if "Alias" not in devices[key].keys():
                continue
            if alias and not alias == devices[key]["Alias"]:
                continue

            # Filter for paired devices
            if "Paired" not in devices[key].keys():
                continue
            if devices[key]["Paired"]:
                continue

            filtered_devices[key] = devices[key]

        return filtered_devices

    def pair_device(self, device_path):
        """Pairs a discovered device at a given DBus object path.

        :param device_path: The D-Bus object path to the device
        :type device_path: string
        """

        async def _do():
            bus = await MessageBus(bus_type=BusType.SYSTEM).connect()
            await _call_method(bus, device_path, DEVICE_INTERFACE, "Pair")
            bus.disconnect()

        _run_async(_do())

    def connect_device(self, device_path):
        async def _connect():
            bus = await MessageBus(bus_type=BusType.SYSTEM).connect()
            try:
                await _call_method(bus, device_path, DEVICE_INTERFACE, "Connect")
            except Exception as e:
                self.logger.exception(e)
            finally:
                bus.disconnect()

        _run_async(_connect())

    def remove_device(self, path):
        """Removes a device that's been either discovered, paired,
        connected, etc.

        :param path: The D-Bus path to the object
        :type path: string
        """

        self._call_adapter("RemoveDevice", "o", [path])

    def find_device_by_address(self, address):
        """Finds the D-Bus path to a device that contains the
        specified address.

        :param address: The Bluetooth MAC address
        :type address: string
        :return: The path to the D-Bus object or None
        :rtype: string or None
        """

        async def _find():
            bus = await MessageBus(bus_type=BusType.SYSTEM).connect()
            objects = await _get_managed_objects(bus)

            for path, ifaces in objects.items():
                if DEVICE_INTERFACE not in ifaces:
                    continue
                device_addr = (
                    await _get_property(bus, path, DEVICE_INTERFACE, "Address")
                ).upper()

                if device_addr == address.upper():
                    bus.disconnect()
                    return path
            bus.disconnect()
            return None

        return _run_async(_find())

    def find_bonded_devices_by_alias(self, alias=None):
        """Finds bonded (paired) devices, optionally filtered by alias.

        :param alias: Device alias to filter by, defaults to None (all bonded)
        :type alias: string, optional
        :return: List of D-Bus paths to bonded devices
        :rtype: list
        """

        async def _find():
            bus = await MessageBus(bus_type=BusType.SYSTEM).connect()
            objects = await _get_managed_objects(bus)

            result = []
            for path, ifaces in objects.items():
                if DEVICE_INTERFACE not in ifaces:
                    continue
                if not await _get_property(bus, path, DEVICE_INTERFACE, "Paired"):
                    continue
                if alias:
                    device_alias = (
                        await _get_property(bus, path, DEVICE_INTERFACE, "Alias")
                    ).upper()
                    if device_alias != alias.upper():
                        continue
                result.append(path)

            bus.disconnect()
            return result

        return _run_async(_find())

    def find_connected_devices(self, alias_filter=False):
        """Finds the D-Bus path to a device that contains the
        specified address.

        :param address: The Bluetooth MAC address
        :type address: string
        :return: The path to the D-Bus object or None
        :rtype: string or None
        """

        async def _find():
            bus = await MessageBus(bus_type=BusType.SYSTEM).connect()
            objects = await _get_managed_objects(bus)

            conn_devices = []
            for path, ifaces in objects.items():
                if DEVICE_INTERFACE not in ifaces:
                    continue
                device_conn_status = await _get_property(
                    bus, path, DEVICE_INTERFACE, "Connected"
                )
                device_alias = (
                    await _get_property(bus, path, DEVICE_INTERFACE, "Alias")
                ).upper()

                if device_conn_status:
                    if alias_filter and device_alias == alias_filter.upper():
                        conn_devices.append(path)
                    else:
                        conn_devices.append(path)

            bus.disconnect()
            return conn_devices

        return _run_async(_find())
