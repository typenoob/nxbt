FROM debian:oldstable-slim
COPY ./ /nxbt
WORKDIR /nxbt
RUN apt update \
    && apt install python3 python3-dev python3-pip ibdbus-glib-1-dev libdbus-1-dev \
    && python3 -m venv /venv \
    && source /venv/bin/activate \
    && pip install nxbt pyinstaller \
    && pyinstaller ./cli.py \
    && cp ./dist/cli /bin/nxbt \
    && chmod +x /bin/nxbt