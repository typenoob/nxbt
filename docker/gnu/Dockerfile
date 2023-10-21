FROM debian:oldoldstable-slim
COPY ./ /nxbt
WORKDIR /nxbt
RUN apt update \
    && apt install -y python3 python3-dev python3-pip libdbus-glib-1-dev libdbus-1-dev 
RUN python3 -m venv /venv 
RUN source /venv/bin/activate
RUN pip install nxbt pyinstaller \
    && pyinstaller ./cli.py \
    && cp ./dist/cli /bin/nxbt \
    && chmod +x /bin/nxbt \
    && ls
ENTRYPOINT ["nxbt"]