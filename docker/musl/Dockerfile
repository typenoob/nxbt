FROM ghcr.io/astral-sh/uv:alpine3.21

RUN mkdir nxbt
WORKDIR /nxbt
COPY . .

# Use mirror for faster download in China
RUN sed -i 's#https\?://dl-cdn.alpinelinux.org/alpine#https://mirrors.tuna.tsinghua.edu.cn/alpine#g' /etc/apk/repositories

# Install Make & g++
RUN apk update && apk add make g++

# Install patchelf from source to select a version other than 0.18.0 (Nutka complains that version)
RUN wget https://github.com/NixOS/patchelf/releases/download/0.15.5/patchelf-0.15.5.tar.gz
RUN tar zxf patchelf-0.15.5.tar.gz \
    && cd patchelf-0.15.5 \
    && ./configure \
    && make \
    && make install

RUN make && make install

ENTRYPOINT ["/bin/nxbt"]