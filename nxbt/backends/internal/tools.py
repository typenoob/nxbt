import subprocess
from shutil import which


def has_tool(name):
    """Check whether a CLI tool is available on PATH.

    :param name: The executable name (e.g. ``"hciconfig"``)
    :return: ``True`` if the tool can be found
    :rtype: bool
    """
    return which(name) is not None


def require_tool(name):
    """Raise an ``Exception`` if a CLI tool is not on PATH.

    :param name: The executable name
    :raises Exception: If the tool is not found
    """
    if not has_tool(name):
        raise Exception(
            f"{name} is not available on this system."
            "If you can, please install this tool."
        )


def run_command(command):
    """Run a subprocess command and raise on stderr output.

    :param command: A list of command arguments
    :return: The completed ``CompletedProcess`` instance
    :raises Exception: If the command wrote anything to stderr
    """
    result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    cmd_err = result.stderr.decode("utf-8").replace("\n", "")
    if cmd_err != "":
        raise Exception(cmd_err)

    return result


def get_blocked_hci_indices():
    """Return indices of HCI adapters that are rfkill-blocked.

    Runs ``rfkill list`` and parses the output.

    :return: A set of blocked HCI adapter indices (e.g. ``{0, 2}``)
    :rtype: set
    """
    blocked = set()
    if not has_tool("rfkill"):
        return blocked

    try:
        result = subprocess.run(
            ["rfkill", "list"], stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
    except Exception:
        return blocked

    current_idx = None
    is_bluetooth = False
    soft_blocked = False
    hard_blocked = False

    for line in result.stdout.decode("utf-8").splitlines():
        line = line.strip()
        # Header line like "0: hci0: Bluetooth"
        if ":" in line and not line.startswith("Soft") and not line.startswith("Hard"):
            # Emit previous entry if applicable
            if (
                current_idx is not None
                and is_bluetooth
                and (soft_blocked or hard_blocked)
            ):
                blocked.add(current_idx)

            # Parse index and type
            parts = line.split(":", 2)
            try:
                current_idx = int(parts[0].strip())
            except (ValueError, IndexError):
                current_idx = None
            is_bluetooth = len(parts) > 2 and "bluetooth" in parts[2].lower()
            soft_blocked = False
            hard_blocked = False
        elif line.lower().startswith("soft blocked:"):
            soft_blocked = "yes" in line.lower()
        elif line.lower().startswith("hard blocked:"):
            hard_blocked = "yes" in line.lower()

    # Don't forget the last entry
    if current_idx is not None and is_bluetooth and (soft_blocked or hard_blocked):
        blocked.add(current_idx)

    return blocked
