import base64
import hashlib
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

import requests
from pywidevine.cdm import Cdm
from pywidevine.device import Device
from pywidevine.pssh import PSSH

# /// script
# dependencies = [
#   "pywidevine",
# ]
# ///

PORT = 9191


class ApiRequestHandler(BaseHTTPRequestHandler):
    def __init__(self, request, client_address, ref_req, api_ref):
        self.api = api_ref
        super().__init__(request, client_address, ref_req)

    def call_api(self, _method, path, args):
        print(api.routing)
        if path in api.routing:
            try:
                result = api.routing[path](args)
                self.send_response(200)
                self.end_headers()
                self.wfile.write(json.dumps(result, indent=4).encode())
            except Exception as e:
                self.send_response(500, "Server Error")
                self.end_headers()
                self.wfile.write(json.dumps({"error": e.args}, indent=4).encode())
        else:
            self.send_response(404, "Not Found")
            self.end_headers()
            self.wfile.write(json.dumps({"error": "not found"}, indent=4).encode())

    def do_GET(self):
        parsed_url = urlparse(self.path)
        path = parsed_url.path
        args = parse_qs(parsed_url.query)

        for k in args.keys():
            if len(args[k]) == 1:
                args[k] = args[k][0]

        self.call_api("GET", path, args)


class API:
    def __init__(self):
        self.routing = {}

    def get(self, path):
        def wrapper(fn):
            self.routing[path] = fn

        return wrapper

    def __call__(self, request, client_address, ref_request):
        api_handler = ApiRequestHandler(
            request, client_address, ref_request, api_ref=self
        )
        return api_handler


api = API()


@api.get("/")
def index(_):
    return {
        "name": "Kagane DRM bypass REST API",
        "summary": "Simple REST API to bypass Kagane's challenge DRM",
        "actions": ["drm"],
        "version": "1.0.0",
    }


def get_pssh(series_id: str, chapter_id: str) -> PSSH:
    seed = hashlib.sha256(f"{series_id}:{chapter_id}".encode("utf-8")).digest()[:16]
    key_id = base64.b64decode("7e+LqXnWSs6jyCfc1R0h7Q==")
    zeroes = b"\x00" * 4
    info = bytes([18, len(seed)]) + seed
    info_size = len(info).to_bytes(4, "big")
    inner = zeroes + key_id + info_size + info
    outer_size = (len(inner) + 8).to_bytes(4, "big")
    return PSSH(outer_size + b"pssh" + inner)


@api.get("/drm")
def drm(args):
    series_id = args.get("sid", None)
    chapter_id = args.get("cid", None)
    pssh = get_pssh(series_id, chapter_id)
    device = Device.load("./device.wvd")
    cdm = Cdm.from_device(device)
    session_id = cdm.open()
    challenge = cdm.get_license_challenge(session_id, pssh)
    res = requests.post(
        f"https://api.kagane.org/api/v1/books/{series_id}/file/{chapter_id}",
        json={"challenge": base64.b64encode(challenge).decode()},
        headers={
            "Origin": "https://kagane.org",
            "Referer": "https://kagane.org/",
            "Content-Type": "application/json",
        },
    )
    cdm.close(session_id)
    return json.loads(res.text)


if __name__ == "__main__":
    httpd = HTTPServer(("", PORT), api)
    httpd.serve_forever()
