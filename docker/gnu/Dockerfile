FROM debian:oldoldstable-slim
RUN mkdir nxbt
WORKDIR /nxbt
COPY . .
RUN apt update \
    && apt install -y wget python3 python3-dev python3-pip libssl-dev libdbus-glib-1-dev libdbus-1-dev patchelf procps zip
RUN wget -qO- https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:$PATH"
RUN uv run --no-managed-python nuitka nxbt \
    && zip -r nxbt.zip ./release