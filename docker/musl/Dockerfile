FROM docker.m.daocloud.io/library/alpine:3.21

ARG TARGETARCH

RUN mkdir nxbt
WORKDIR /nxbt
COPY . .

# Use mirror for faster download in China
# RUN sed -i 's#https\?://dl-cdn.alpinelinux.org/alpine#https://mirrors.ustc.edu.cn/alpine#g' /etc/apk/repositories
RUN apk update

# Install patchelf from source to select a version other than 0.18.0 (Nutka complains that version)
RUN apk add make g++
RUN wget https://github.com/NixOS/patchelf/releases/download/0.15.5/patchelf-0.15.5.tar.gz
RUN tar zxf patchelf-0.15.5.tar.gz \
    && cd patchelf-0.15.5 \
    && ./configure \
    && make \
    && make install

# Install Cryptography's dependencies
ENV PYO3_USE_ABI3_FORWARD_COMPATIBILITY=1
RUN if [ "$TARGETARCH" != "amd64" ] && [ "$TARGETARCH" != "arm64" ]; then \
      apk add cargo libffi-dev openssl-dev; \
    fi

# Install UV
RUN apk add pipx
RUN pipx install uv
ENV PATH="/root/.local/bin:$PATH"

# Install Nxbt
RUN if [ "$TARGETARCH" = "386" ]; then \
      apk add util-linux; \
      setarch i386 sh -c 'make && make install'; \
    else \
      make && make install; \
    fi

ENTRYPOINT ["/bin/nxbt"]
