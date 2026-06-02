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
