FROM debian:oldoldstable-slim
COPY ./ /nxbt
WORKDIR /nxbt
RUN apt update \
    && apt install -y python3 python3-dev python3-pip python3-venv libdbus-glib-1-dev libdbus-1-dev \
    && python3 -m venv /venv 
ENV PATH="/venv/bin:$PATH"
RUN pip install nxbt pyinstaller \
    && pyinstaller ./cli.py \
    && cp ./build/cli/cli /bin/nxbt \
    && chmod +x /bin/nxbt
ENTRYPOINT ["nxbt"]