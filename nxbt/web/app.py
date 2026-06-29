import json
import os
import asyncio
from concurrent.futures import ThreadPoolExecutor
from threading import RLock
from socket import gethostname

import socketio
import uvicorn
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .cert import generate_cert
from ..utils import load_file
from ..nxbt import Nxbt, PRO_CONTROLLER
from ..backends import BACKENDS

nxbt = None

# Configuring/retrieving secret key (reserved for future session use)
secrets_path = load_file("web/secrets.txt")
if not os.path.isfile(secrets_path):
    secret_key = os.urandom(24).hex()
    with open(secrets_path, "w", encoding="utf-8") as f:
        f.write(secret_key)
else:
    with open(secrets_path, "r", encoding="utf-8") as f:
        secret_key = f.read()

static_dir = load_file("web/static")
templates_dir = load_file("web/templates")

app = FastAPI()
templates = Jinja2Templates(directory=templates_dir)

sio = socketio.AsyncServer(cors_allowed_origins="*", async_mode="asgi")
asgi_app = socketio.ASGIApp(sio, other_asgi_app=app)

user_info_lock = RLock()
USER_INFO = {}


def _run_async(coro, *, wait=True):
    """Run a coroutine from sync Socket.IO handlers."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    if wait:
        with ThreadPoolExecutor(max_workers=1) as executor:
            return executor.submit(asyncio.run, coro).result()

    async def _runner():
        return await coro

    return loop.create_task(_runner())


def _emit_to(sid, event, data=None):
    _run_async(sio.emit(event, data, to=sid), wait=False)


@app.get("/")
def index(request: Request):
    return templates.TemplateResponse(request, "index.html")


@sio.event
def connect(sid, environ):
    with user_info_lock:
        USER_INFO[sid] = {}


@sio.on("state")
def on_state(sid):
    state_proxy = nxbt.state.copy()
    state = {}
    for controller in state_proxy.keys():
        state[controller] = state_proxy[controller].copy()
    _emit_to(sid, "state", state)


@sio.event
def disconnect(sid):
    print("Disconnected")
    with user_info_lock:
        try:
            index = USER_INFO[sid]["controller_index"]
            nxbt.remove_controller(index)
        except KeyError:
            pass
        except (ValueError, OSError):
            pass
        finally:
            USER_INFO.pop(sid, None)


@sio.on("shutdown")
def on_shutdown(sid, index):
    try:
        nxbt.remove_controller(index)
    except ValueError:
        pass
    with user_info_lock:
        if USER_INFO.get(sid, {}).get("controller_index") == index:
            USER_INFO[sid].pop("controller_index", None)


@sio.on("web_create_pro_controller")
async def on_create_controller(sid):
    print("Create Controller")

    def _create():
        reconnect_addresses = nxbt.get_switch_addresses()
        return nxbt.create_controller(
            PRO_CONTROLLER, reconnect_address=reconnect_addresses
        )

    try:
        # Run blocking BT work off the ASGI event loop (Flask-SocketIO used threads).
        index = await asyncio.to_thread(_create)
        with user_info_lock:
            USER_INFO[sid]["controller_index"] = index

        _emit_to(sid, "create_pro_controller", index)
    except Exception as e:
        _emit_to(sid, "error", str(e))


@sio.on("input")
def handle_input(sid, message):
    message = json.loads(message)
    index = message[0]
    input_packet = message[1]
    try:
        nxbt.set_controller_input(index, input_packet)
    except ValueError:
        pass


@sio.on("macro")
def handle_macro(sid, message):
    message = json.loads(message)
    index = message[0]
    macro = message[1]
    try:
        nxbt.macro(index, macro)
    except ValueError:
        pass


app.mount("/", StaticFiles(directory=static_dir), name="static")


def start_web_app(
    ip="0.0.0.0", port=8000, usessl=False, cert_path=None, debug=False, backend="bumble"
):
    global nxbt
    nxbt = Nxbt(debug=debug, backend=BACKENDS[backend])
    if usessl:
        if cert_path is None:
            cert_path = load_file("web/cert.pem")
            key_path = load_file("web/key.pem")
        else:
            cert_dir = cert_path
            cert_path = os.path.join(cert_dir, "cert.pem")
            key_path = os.path.join(cert_dir, "key.pem")
        if not os.path.isfile(cert_path) or not os.path.isfile(key_path):
            print(
                "\n"
                "-----------------------------------------\n"
                "---------------->WARNING<----------------\n"
                "The NXBT webapp is being run with self-\n"
                "signed SSL certificates for use on your\n"
                "local network.\n"
                "\n"
                "These certificates ARE NOT safe for\n"
                "production use. Please generate valid\n"
                "SSL certificates if you plan on using the\n"
                "NXBT webapp anywhere other than your own\n"
                "network.\n"
                "-----------------------------------------\n"
                "\n"
                "The above warning will only be shown once\n"
                "on certificate generation."
                "\n"
            )
            print("Generating certificates...")
            cert, key = generate_cert(gethostname())
            with open(cert_path, "wb") as f:
                f.write(cert)
            with open(key_path, "wb") as f:
                f.write(key)

        uvicorn.run(
            asgi_app,
            host=ip,
            port=port,
            access_log=debug,
            log_level="debug" if debug else "info",
            ssl_keyfile=key_path,
            ssl_certfile=cert_path,
        )
    else:
        uvicorn.run(
            asgi_app,
            host=ip,
            port=port,
            access_log=debug,
            log_level="debug" if debug else "info",
        )


if __name__ == "__main__":
    start_web_app()
