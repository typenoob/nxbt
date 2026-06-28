FROM ghcr.io/msys2/msys2-docker-experimental

ARG MSYSTEM
ENV MSYSTEM=$MSYSTEM

SHELL ["msys2", "-c"]

ARG TARGETARCH

RUN mkdir nxbt
WORKDIR /nxbt
COPY . .

# Use mirror for faster download in China
# RUN sed -i "s#https\?://repo.msys2.org/#https://mirrors.ustc.edu.cn/msys2/#g" /etc/pacman.d/mirrorlist*

# Install Make
RUN pacman -S --noconfirm make

# Install Nxbt
RUN make && make install

ENTRYPOINT ["wine", "/root/.wine/drive_c/msys64/usr/bin/nxbt.exe"]
