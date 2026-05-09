FROM ghcr.io/astral-sh/uv:python3.13-alpine3.23

RUN mkdir nxbt
WORKDIR /nxbt
COPY . .

# Install Make and Bluetooth tools
RUN apk update && apk add make bluez bluez-tools

RUN make && make install

ENTRYPOINT ["/bin/nxbt"]