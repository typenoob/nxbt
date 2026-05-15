from abc import ABC, abstractmethod


class Backend(ABC):
    """Abstract base class for Bluetooth backends.

    Implementations must provide socket-based connect/reconnect
    that return (interrupt, control) transport handles.
    """

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
