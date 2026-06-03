.PHONY: all install-deps build install docker

all: install-deps build

install-deps:
	@SUDO=; if [ "$$(id -u)" -ne 0 ]; then SUDO=sudo; fi; \
	if [ -f /etc/alpine-release ]; then \
		$$SUDO apk update && \
		$$SUDO apk add ccache make gcc g++ python3 python3-dev py3-pip libusb dbus-dev openssl-dev patchelf procps zstandard bluez; \
	elif [ -f /etc/debian_version ]; then \
		$$SUDO apt update && $$SUDO apt install -y wget ccache make gcc g++ python3 python3-dev python3-pip libusb-1.0-0 libssl-dev libdbus-1-dev patchelf procps zstandard bluez; \
	else \
		echo "Unsupported OS. Only Debian, Ubuntu and Alpine are supported. Skipping dependency installation."; \
	fi

build:
	@uv run --no-managed-python nuitka nxbt

install:
	@SUDO=; if [ "$$(id -u)" -ne 0 ]; then SUDO=sudo; fi; \
		$$SUDO ln -s /nxbt/release/nxbt /bin/nxbt

docker:
	@docker build -t nxbt:gnu -f docker/gnu/Dockerfile .
	@docker build -t nxbt:musl -f docker/musl/Dockerfile .
