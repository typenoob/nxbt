.PHONY: all install-deps build install docker

all: install-deps build

install-deps:
	@SUDO=; if [ "$$(id -u)" -ne 0 ]; then SUDO=sudo; fi; \
	if [ -f /etc/alpine-release ]; then \
		$$SUDO apk update && \
		$$SUDO apk add python3 python3-dev py3-pip glib-dev dbus dbus-dev make gcc g++ musl-dev libffi-dev openssl-dev patchelf procps bluez; \
	elif grep -qi ubuntu /etc/os-release 2>/dev/null; then \
		$$SUDO apt update && $$SUDO apt install -y wget python3 python3-pip libssl-dev libdbus-glib-1-dev libdbus-1-dev patchelf procps bluez; \
	elif [ -f /etc/debian_version ]; then \
		$$SUDO apt update && $$SUDO apt install -y wget python3 python3-pip libssl-dev libdbus-glib-1-dev libdbus-1-dev patchelf procps bluez; \
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
