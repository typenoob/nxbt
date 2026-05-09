
FROM ghcr.io/astral-sh/uv:debian-slim

RUN mkdir nxbt
WORKDIR /nxbt
COPY . .

# Use mirror for faster download in China; disable SSL verification for mirrors with cert issues
RUN sed -i 's|http://deb.debian.org/|https://mirrors.ustc.edu.cn/|g' /etc/apt/sources.list.d/debian.sources

RUN echo 'Acquire::https::Verify-Peer "false";' > /etc/apt/apt.conf.d/99-no-ssl-verify
RUN apt update

# # Install Make
RUN apt install -y make

# # Install Python
RUN apt install -y python3

RUN make && make install

ENTRYPOINT ["/bin/nxbt"]