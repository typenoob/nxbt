FROM debian:oldoldstable-slim
COPY ./ /nxbt
WORKDIR /nxbt
RUN apt update \
    && apt install -y python3 python3-dev python3-pip python3-venv libdbus-glib-1-dev libdbus-1-dev 
RUN sudo python3 -m venv /venv 
RUN source /venv/bin/activate
RUN pip install nxbt pyinstaller \
    && pyinstaller ./cli.py \
    && cp ./dist/cli /bin/nxbt \
    && chmod +x /bin/nxbt \
    && ls
ENTRYPOINT ["nxbt"]