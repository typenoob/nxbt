FROM ghcr.io/astral-sh/uv:python3.13-alpine3.23

RUN mkdir nxbt
WORKDIR /nxbt
COPY . .

# Use mirror for faster download in China
RUN sed -i 's#https\?://dl-cdn.alpinelinux.org/alpine#https://mirrors.tuna.tsinghua.edu.cn/alpine#g' /etc/apk/repositories

# Install Make and Bluetooth tools
RUN apk update && apk add make bluez bluez-tools

RUN make && make install

ENTRYPOINT ["/bin/nxbt"]