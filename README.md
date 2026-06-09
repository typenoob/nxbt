## Motivation

Since [Brikwerk](https://github.com/Brikwerk) is no longer active on GitHub, I created this branch to maintain and continue development of the project.

Windows support has been preliminarily validated — I will update this section as time allows.

## Plans

I started this as a fork of the original project. Once it reaches sufficient maturity and independence, I plan to establish it as a standalone repository.

- [x] Clean the code
- [x] Use pyproject.toml and uv to manage the package and requirements
- [ ] Fix webapp unexpected behaviors
- [x] Use [bumble](https://github.com/google/bumble) to rewrite the repo
- [x] Add Windows support for generic USB drivers through [zadig](https://zadig.akeo.ie/), such as [WinUSB](https://learn.microsoft.com/en-us/windows-hardware/drivers/usbcon/introduction-to-winusb-for-developers)
- [ ] Add native GUI for webapp using pywebview
- [ ] Add Android support

## Quick Start

```
docker run --rm --network host \
  -v /var/run/dbus:/var/run/dbus \
  --device=/dev/bus/usb --device=/dev/rfkill \
  --security-opt apparmor=unconfined \
  --cap-add=NET_ADMIN --cap-add=NET_BIND_SERVICE \
  -it ghcr.io/typenoob/nxbt:gnu webapp
```

## Bluetooth Backends

NXBT supports multiple Bluetooth backend implementations. The default backend is **Bumble**, but you can switch to **BlueZ** if needed.

| Feature | BlueZ | Bumble (HCI Socket) | Bumble (USB) |
|---|---|---|---|
| **Transport** | BlueZ D-Bus API | Raw HCI socket (`/dev/hciX`) | Direct USB (libusb) |
| **Conflicts with `bluetoothd`** | Yes (shares D-Bus) | No | No |
| **HCI flow control** | Kernel-managed | Kernel-managed | Host-managed |
| **OS** | Linux | Linux | Linux / Windows |
| **Hardware** | Any kernel-supported adapter | Any kernel-supported adapter | Any USB Bluetooth dongle |

**Recommendation:** Use the HCI Socket backend when available — it avoids conflicts with system Bluetooth services and requires no additional hardware setup.

**Note:** Most modern laptops use built-in USB-based Bluetooth adapters, so the Bumble (USB) backend will work out of the box. You can verify this with `lsusb`.

## Permissions

nxbt requires privileged access to interact with Bluetooth hardware. Running the entire process as root is the simplest approach, but it is **strongly discouraged** for security reasons. Below are safer alternatives that grant only the minimum required capabilities.

### Required capabilities

| Backend | Capabilities | Why |
|---|---|---|
| **Bumble (HCI socket)** | `cap_net_admin` | Binding to raw HCI sockets (`HCI_CHANNEL_USER`) |
| **Bumble (USB)** | None (if libusb works) | Direct USB communication, no kernel socket needed |
| **BlueZ** | `cap_net_admin`, `cap_net_bind_service` | Binding to raw HCI sockets (`HCI_CHANNEL_CONTROL`), Binding to L2CAP PSM |

### Option 1: File capabilities (recommended, persistent)

Grant capabilities directly to the NXBT binary. This works across sessions and does not depend on ambient capability inheritance:

```bash
sudo setcap 'cap_net_admin,cap_net_bind_service+eip' $(readlink -f $(which nxbt))
```

Then run normally:

```bash
nxbt demo
```

### Option 2: capsh (temporary, per-session)

Use `capsh` to launch nxbt with the required ambient capabilities:

```bash
# Bumble (HCI socket) backend
sudo capsh --caps="cap_net_admin,cap_net_bind_service+eip cap_setpcap,cap_setuid,cap_setgid+ep" \
  --keep=1 --user=$USER \
  --addamb=cap_net_admin,cap_net_bind_service -- \
  -c "nxbt demo"

# BlueZ backend
sudo capsh --caps="cap_net_admin+eip cap_setpcap,cap_setuid,cap_setgid+ep" \
  --keep=1 --user=$USER \
  --addamb=cap_net_admin -- \
  -c "nxbt -b bluez demo"
```

### BlueZ backend: systemd override

When using the BlueZ backend, nxbt needs to restart `bluetoothd` with all plugins disabled (`--noplugin=*`). This requires writing a systemd drop-in override at `/run/systemd/system/bluetooth.service.d/nxbt.conf`.

You can set this up once as root before running nxbt:

```bash
# Create the override
sudo bash -c '
mkdir -p /run/systemd/system/bluetooth.service.d
cat > /run/systemd/system/bluetooth.service.d/nxbt.conf << "EOF"
[Service]
ExecStart=
ExecStart=bluetoothd --noplugin=*
EOF
systemctl daemon-reload
systemctl restart bluetooth
'
```

Once the override file exists, nxbt will skip writing it on subsequent runs.

## Contributions Welcome

Everyone is welcome to share ideas or contribute through issues and pull requests.

## Thanks

Many thanks to the original author [Brikwerk](https://github.com/Brikwerk).

## More

The original readme can be found [here](https://github.com/typenoob/nxbt/blob/master/README.old.md)
