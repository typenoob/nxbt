from abc import ABC, abstractmethod


class Backend(ABC):
    """Abstract base class for Bluetooth backends.

    Implementations must provide socket-based connect/reconnect
    that return (interrupt, control) transport handles.
    """

    def __init__(self, adapter_idx=None):
        self._adapter_idx = adapter_idx

    @property
    @abstractmethod
    def address(self) -> str:
        """The Bluetooth MAC address of the adapter."""

    @abstractmethod
    def setup(self, controller_type) -> None:
        """Initialize the backend and configure adapter for the given controller type."""

    @abstractmethod
    def accept(self) -> tuple:
        """Accept an incoming connection. Returns (itr_socket, ctrl_socket)."""

    @abstractmethod
    def reconnect(self, address) -> tuple:
        """Reconnect to a known address. Returns (itr_socket, ctrl_socket)."""

    @abstractmethod
    def remove_bonded_device(self, address):
        """Remove a bonded Nintendo Switch device from the host's Bluetooth bond list.

        This forgets the pairing keys associated with *address*, allowing the
        Switch to re-initiate a fresh bonding handshake on the next connection
        attempt. Use this when the Switch fails to reconnect or reports a
        pairing/bonding error.

        Args:
            address: The Bluetooth MAC address of the Switch to unpair.
        """

    @staticmethod
    def get_available_adapters() -> list:
        """Return a list of available adapter identifiers."""
        raise NotImplementedError

    @staticmethod
    def get_switch_addresses() -> list:
        """Return previously connected Nintendo Switch addresses."""
        raise NotImplementedError

    def shutdown(self) -> None:
        """Release resources. Subclasses should override (e.g. reattach USB drivers)."""
        pass
