
FROM docker.m.daocloud.io/library/debian:stable-slim

ARG TARGETARCH

RUN mkdir nxbt
WORKDIR /nxbt
COPY . .

# Use mirror for faster download in China; disable SSL verification for mirrors with cert issues
# RUN sed -i 's|http://deb.debian.org/|https://mirrors.ustc.edu.cn/|g' /etc/apt/sources.list.d/debian.sources
# RUN echo 'Acquire::https::Verify-Peer "false";' > /etc/apt/apt.conf.d/99-no-ssl-verify
RUN apt update

# Install Cryptography's dependencies
ENV PYO3_USE_ABI3_FORWARD_COMPATIBILITY=1
RUN if [ "$TARGETARCH" != "amd64" ] && [ "$TARGETARCH" != "arm64" ]; then \
      apt install -y cargo libffi-dev libssl-dev; \
    fi

# Install UV
RUN apt install -y pipx
RUN pipx install uv
ENV PATH="/root/.local/bin:$PATH"

# Install Make
RUN apt install make

# Install Nxbt
RUN if [ "$TARGETARCH" = "386" ]; then \
      apk add util-linux; \
      setarch i386 sh -c 'make && make install'; \
    else \
      make && make install; \
    fi

ENTRYPOINT ["/bin/nxbt"]
