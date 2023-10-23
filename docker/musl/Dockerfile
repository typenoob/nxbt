FROM alpine:3.15
RUN mkdir nxbt
WORKDIR /nxbt
COPY ./docker ./docker
COPY ./nxbt ./nxbt
RUN apk update \
    && apk add python3 python3-dev py3-pip py3-virtualenv py3-dbus dbus-glib-dev make gcc g++ musl-dev libffi-dev openssl-dev \
    && python3 -m venv /venv
ENV PATH="/venv/bin:$PATH"
RUN pip install pyinstaller \
    && pip install -r ./docker/requirements.txt \
    && pyinstaller ./docker/entrypoint.spec \
    && cp ./dist/entrypoint /bin/nxbt \
    && chmod +x /bin/nxbt