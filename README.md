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
docker run --rm --privileged --network host \
  -v /var/run/dbus:/var/run/dbus \
  -v /var/lib/bluetooth:/var/lib/bluetooth \
  -v /sys:/sys \
  -v /dev:/dev \
  nxbt:gnu -b bluez demo
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

## Welcoming Contributions

Everyone is welcome to share ideas or contribute through issues and pull requests.

## Thanks

Many thanks to the original author [Brikwerk](https://github.com/Brikwerk).

## Getting Started

The original readme can be found [here](https://github.com/typenoob/nxbt/blob/master/README.old.md)
