FROM debian:oldoldstable-slim
RUN mkdir nxbt
WORKDIR /nxbt
COPY ./docker ./docker
COPY ./nxbt ./docker/nxbt
RUN apt update \
    && apt install -y python3 python3-dev python3-pip python3-venv libssl-dev libdbus-glib-1-dev libdbus-1-dev procps\
    && python3 -m venv /venv 
ENV PATH="/venv/bin:$PATH"
RUN pip install pyinstaller \
    && pip install -r ./docker/requirements.txt \
    && pyinstaller ./docker/entrypoint.spec \
    && cp ./dist/entrypoint /bin/nxbt \
    && chmod +x /bin/nxbt