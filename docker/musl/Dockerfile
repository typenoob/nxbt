FROM alpine:3.15
RUN mkdir nxbt
WORKDIR /nxbt
COPY . .
RUN apk update \
    && apk add python3 python3-dev py3-pip glib-dev dbus dbus-dev make gcc g++ musl-dev libffi-dev openssl-dev patchelf procps
RUN wget -qO- https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:$PATH"
RUN uv run --no-managed-python nuitka nxbt \
    && zip -r nxbt.zip ./release