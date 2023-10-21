FROM alpine:3.15
COPY ./ /nxbt
WORKDIR /nxbt
RUN apk update \
    && apk add python3 python3-dev py3-pip py3-dbus dbus-glib-dev make gcc g++ musl-dev libffi-dev openssl-dev \
    && python3 -m venv /venv \
    && source /venv/bin/activate \
    && pip install nxbt pyinstaller \
    && pyinstaller ./cli.py \
    && cp ./dist/cli /bin/nxbt \
    && chmod +x /bin/nxbt