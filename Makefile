.PHONY: all install-deps venv pip-deps build build-uv build-pip install docker

BITNESS := $(shell getconf LONG_BIT 2>/dev/null || echo 64)
NUITKA_GIT := nuitka @ git+https://github.com/typenoob/Nuitka.git@mingw-filename

ifdef MSYSTEM
NXBT_OUT := release/nxbt.exe
NXBT_BIN := nxbt.exe
else
NXBT_OUT := release/nxbt
NXBT_BIN := nxbt
endif

PYTHON := .venv/bin/python
PIP    := .venv/bin/pip

all: install-deps build

install-deps:
	@SUDO=; if [ "$$(id -u)" -ne 0 ]; then SUDO=sudo; fi; \
	if [ -f /etc/alpine-release ]; then \
		$$SUDO apk update && \
		$$SUDO apk add --no-cache git ccache make gcc g++ python3 python3-dev libcap-dev libusb-dev dbus-dev patchelf procps bluez; \
	elif [ -f /etc/debian_version ]; then \
		$$SUDO apt update && \
		$$SUDO apt install -y git wget ccache make gcc g++ python3 python3-dev \
			libcap2 libcap-dev libusb-1.0-0-dev libssl-dev libdbus-1-dev patchelf procps bluez; \
	elif [ -f /etc/msystem ]; then \
		case "$$MSYSTEM" in \
			MINGW64|UCRT64) ;; \
			*) echo "error: Got MSYSTEM=$$MSYSTEM"; exit 1 ;; \
		esac; \
		pacman -S --noconfirm --needed \
			make git \
			$$MINGW_PACKAGE_PREFIX-ccache \
			$$MINGW_PACKAGE_PREFIX-gcc \
			$$MINGW_PACKAGE_PREFIX-libusb \
			$$MINGW_PACKAGE_PREFIX-python \
			$$MINGW_PACKAGE_PREFIX-python-setuptools \
			$$MINGW_PACKAGE_PREFIX-python-cryptography \
			$$MINGW_PACKAGE_PREFIX-python-grpcio \
			$$MINGW_PACKAGE_PREFIX-python-zstandard \
			$$MINGW_PACKAGE_PREFIX-python-aiohttp \
			$$MINGW_PACKAGE_PREFIX-python-greenlet \
			$$MINGW_PACKAGE_PREFIX-python-fastapi \
			$$MINGW_PACKAGE_PREFIX-python-markupsafe \
			$$MINGW_PACKAGE_PREFIX-python-psutil; \
	else \
		echo "Unsupported OS. Only Debian, Ubuntu, Alpine and MSYS2 MINGW64/UCRT64 are supported. Skipping dependency installation."; \
	fi

venv:
	@test -d .venv/bin || python -m venv .venv --system-site-packages

pip-deps: venv
	$(PIP) install -e . "$(NUITKA_GIT)"

build-uv:
	uv run --no-managed-python nuitka nxbt

build-pip: pip-deps
	$(PYTHON) -m nuitka nxbt

build:
	# uv is unsupported on MSYS2 MINGW64/UCRT64 Python; use pip instead.
	# https://github.com/astral-sh/uv/issues/3573
	@if [ -f /etc/msystem ]; then \
		$(MAKE) build-pip; \
	elif command -v uv >/dev/null 2>&1; then \
		$(MAKE) build-uv; \
	else \
		$(MAKE) build-pip; \
	fi

install:
	@SUDO=; if [ -z "$$MSYSTEM" ] && [ "$$(id -u)" -ne 0 ]; then SUDO=sudo; fi; \
	$$SUDO install -m 755 $(NXBT_OUT) /usr/bin/$(NXBT_BIN)

docker:
	docker build -t nxbt:gnu -f docker/gnu/Dockerfile .
	docker build -t nxbt:musl -f docker/musl/Dockerfile .
	docker build -t nxbt:mingw64 --build-arg MSYSTEM=MINGW64 -f docker/msys2/Dockerfile .
	docker build -t nxbt:ucrt64 --build-arg MSYSTEM=UCRT64 -f docker/msys2/Dockerfile .