FROM debian:oldoldstable-slim
COPY ./ /nxbt
WORKDIR /nxbt
RUN apt update \
    && apt install -y python3 python3-dev python3-pip python3-venv libdbus-glib-1-dev libdbus-1-dev 
RUN python3 -m venv /venv 
ENV PATH="/venv/bin:$PATH"
RUN pip install nxbt pyinstaller \
    && pyinstaller ./cli.py
RUN ls ./build/cli
RUN cp ./build/cli/cli /bin/nxbt
RUN chmod +x /bin/nxbt
RUN ls
ENTRYPOINT ["nxbt"]