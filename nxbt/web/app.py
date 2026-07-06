import json
import os
import asyncio
from concurrent.futures import ThreadPoolExecutor
from threading import RLock
from socket import gethostname

import socketio
import uvicorn
from engineio.payload import Payload
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles
from starlette.templating import Jinja2Templates

from .cert import generate_cert
from .. import __version__
from ..utils import load_file
from ..nxbt import Nxbt, PRO_CONTROLLER
from ..backends import BACKENDS
from ..setcap import GRANT_CAPS_HINT

# Polling payloads can batch many input packets; default limit (16) is too low.
Payload.max_decode_packets = 64

NO_ADAPTERS_MESSAGE = (
    "No Bluetooth adapters were detected. "
    "Please ensure your system has Bluetooth capability and try again."
)

PERMISSIONS_REQUIRED_MESSAGE = (
    "Bluetooth adapters were found on your system, but none are available "
    "because NXBT does not have the required permissions.\n\n" + GRANT_CAPS_HINT
)


class WebApp:
    def __init__(self, nxbt=None, *, debug=False, backend="bumble"):
        self.nxbt = nxbt
        self._debug = debug
        self._backend = backend
        self._user_info = {}
        self._user_info_lock = RLock()
        self._load_secret_key()

        static_dir = load_file("web/static")
        templates_dir = load_file("web/templates")

        self.templates = Jinja2Templates(directory=templates_dir)
        self.app = self._create_app(static_dir)
        self.sio = socketio.AsyncServer(
            cors_allowed_origins="*",
            async_mode="asgi",
            ping_timeout=60,
            ping_interval=25,
        )
        self.asgi_app = socketio.ASGIApp(self.sio, other_asgi_app=self.app)
        self._register_socketio_handlers()

    def _load_secret_key(self):
        secrets_path = load_file("web/secrets.txt")
        if not os.path.isfile(secrets_path):
            secret_key = os.urandom(24).hex()
            with open(secrets_path, "w", encoding="utf-8") as f:
                f.write(secret_key)
        else:
            with open(secrets_path, "r", encoding="utf-8") as f:
                secret_key = f.read()
        self.secret_key = secret_key

    def _create_app(self, static_dir):
        async def index(request: Request):
            return self.templates.TemplateResponse(
                request, "index.html", {"version": __version__}
            )

        return Starlette(
            routes=[
                Route("/", index),
                Mount("/", StaticFiles(directory=static_dir), name="static"),
            ]
        )

    def _register_socketio_handlers(self):
        self.sio.event(self.connect)
        self.sio.on("state")(self.on_state)
        self.sio.event(self.disconnect)
        self.sio.on("shutdown")(self.on_shutdown)
        self.sio.on("web_create_pro_controller")(self.on_create_controller)
        self.sio.on("input")(self.handle_input)
        self.sio.on("macro")(self.handle_macro)

    def _run_async(self, coro, *, wait=True):
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

    def _emit_to(self, sid, event, data=None):
        self._run_async(self.sio.emit(event, data, to=sid), wait=False)

    def _get_adapter_availability(self):
        return BACKENDS[self._backend].get_available_adapters()

    def _no_adapters_payload(self, availability) -> dict:
        if not availability["has_permissions"]:
            return {
                "title": "Permissions Required",
                "message": PERMISSIONS_REQUIRED_MESSAGE,
            }
        return {
            "title": "No Adapters Available",
            "message": NO_ADAPTERS_MESSAGE,
        }

    def connect(self, sid, environ):
        with self._user_info_lock:
            self._user_info[sid] = {}
        availability = self._get_adapter_availability()
        payload = {"available": len(availability["adapters"]) > 0}
        if not availability["adapters"]:
            payload.update(self._no_adapters_payload(availability))
        self._emit_to(sid, "adapters", payload)

    def on_state(self, sid):
        state_proxy = self.nxbt.state.copy()
        state = {}
        for controller in state_proxy.keys():
            state[controller] = state_proxy[controller].copy()
        self._emit_to(sid, "state", state)

    async def disconnect(self, sid):
        print("Disconnected")
        asyncio.create_task(self._cleanup_session(sid))

    async def _cleanup_session(self, sid):
        index = None
        with self._user_info_lock:
            session = self._user_info.pop(sid, None)
            if session:
                index = session.get("controller_index")
        if index is None:
            return
        try:
            await asyncio.to_thread(self.nxbt.remove_controller, index)
        except (ValueError, OSError):
            pass

    def on_shutdown(self, sid, index):
        try:
            self.nxbt.remove_controller(index)
        except ValueError:
            pass
        with self._user_info_lock:
            if self._user_info.get(sid, {}).get("controller_index") == index:
                self._user_info[sid].pop("controller_index", None)

    async def on_create_controller(self, sid):
        print("Create Controller")

        availability = self._get_adapter_availability()
        if not availability["adapters"]:
            self._emit_to(sid, "no_adapters", self._no_adapters_payload(availability))
            return

        def _create():
            reconnect_addresses = self.nxbt.get_switch_addresses()
            return self.nxbt.create_controller(
                PRO_CONTROLLER, reconnect_address=reconnect_addresses
            )

        try:
            index = await asyncio.to_thread(_create)
            with self._user_info_lock:
                self._user_info[sid]["controller_index"] = index

            self._emit_to(sid, "create_pro_controller", index)
        except ValueError as e:
            if "No adapters available" in str(e):
                availability = self._get_adapter_availability()
                self._emit_to(
                    sid, "no_adapters", self._no_adapters_payload(availability)
                )
            else:
                self._emit_to(sid, "error", str(e))
        except Exception as e:
            self._emit_to(sid, "error", str(e))

    def handle_input(self, sid, message):
        message = json.loads(message)
        index = message[0]
        input_packet = message[1]
        try:
            self.nxbt.set_controller_input(index, input_packet)
        except ValueError:
            pass

    def handle_macro(self, sid, message):
        message = json.loads(message)
        index = message[0]
        macro = message[1]
        try:
            self.nxbt.macro(index, macro)
        except ValueError:
            pass

    def run(
        self,
        ip="0.0.0.0",
        port=8000,
        usessl=False,
        cert_path=None,
        debug=None,
    ):
        if self.nxbt is None:
            self.nxbt = Nxbt(
                debug=self._debug if debug is None else debug,
                backend=BACKENDS[self._backend],
            )
        if debug is not None:
            self._debug = debug

        uvicorn_kwargs = {
            "host": ip,
            "port": port,
            "access_log": self._debug,
            "log_level": "debug" if self._debug else "info",
        }

        if usessl:
            cert_path, key_path = self._resolve_ssl_paths(cert_path)
            if not os.path.isfile(cert_path) or not os.path.isfile(key_path):
                self._print_ssl_warning()
                print("Generating certificates...")
                cert, key = generate_cert(gethostname())
                with open(cert_path, "wb") as f:
                    f.write(cert)
                with open(key_path, "wb") as f:
                    f.write(key)
            uvicorn_kwargs["ssl_keyfile"] = key_path
            uvicorn_kwargs["ssl_certfile"] = cert_path

        uvicorn.run(self.asgi_app, **uvicorn_kwargs)

    def _resolve_ssl_paths(self, cert_path):
        if cert_path is None:
            return load_file("web/cert.pem"), load_file("web/key.pem")
        cert_dir = cert_path
        return (
            os.path.join(cert_dir, "cert.pem"),
            os.path.join(cert_dir, "key.pem"),
        )

    @staticmethod
    def _print_ssl_warning():
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


def start_web_app(
    ip="0.0.0.0", port=8000, usessl=False, cert_path=None, debug=False, backend="bumble"
):
    WebApp(debug=debug, backend=backend).run(
        ip=ip, port=port, usessl=usessl, cert_path=cert_path, debug=debug
    )


if __name__ == "__main__":
    start_web_app()
