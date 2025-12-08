FROM debian:oldoldstable-slim
RUN mkdir nxbt
WORKDIR /nxbt
COPY ./pyproject.toml ./pyproject.toml
COPY ./nxbt ./nxbt
RUN apt update \
    && apt install -y python3 python3-dev python3-pip python3-venv libssl-dev libdbus-glib-1-dev libdbus-1-dev procps
RUN wget -qO- https://astral.sh/uv/install.sh | sh
RUN uv sync \
    && uv run nuitka nxbt \
    && zip -r nxbt.zip ./release