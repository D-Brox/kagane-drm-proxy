import base64
import hashlib
import json
import sys
from gettext import Catalog
from http.server import BaseHTTPRequestHandler, HTTPServer
from time import time
from tokenize import Token
from urllib.parse import parse_qs, urlparse

import requests
from bs4 import BeautifulSoup
from pywidevine.cdm import Cdm
from pywidevine.device import Device
from pywidevine.pssh import PSSH
from requests.sessions import cookiejar_from_dict

# /// script
# dependencies = [
#   "pywidevine",
#   "beautifulsoup4"
# ]
# ///

FLARESOLVERR = "http://flaresolverr:8191/v1"
PORT = 9191
COOKIES = {"cf_clearance": None, "expiry": int(time()), "user-agent": None}
TOKEN = {"token": None, "exp": int(time())}
USERAGENT = None


class ApiRequestHandler(BaseHTTPRequestHandler):
    def __init__(self, request, client_address, server, api):
        self.api = api
        super().__init__(request, client_address, server)

    def do_GET(self):
        parsed_url = urlparse(self.path)
        path = parsed_url.path
        args = parse_qs(parsed_url.query)

        for k in args.keys():
            if len(args[k]) == 1:
                args[k] = args[k][0]

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


class API:
    def __init__(self):
        self.routing = {}

    def get(self, path):
        def wrapper(fn):
            self.routing[path] = fn

        return wrapper

    def __call__(self, request, client_address, ref_request):
        api_handler = ApiRequestHandler(request, client_address, ref_request, api=self)
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
    key_id = hashlib.sha256(f":{chapter_id}".encode("utf-8")).digest()[:16]
    seed = base64.b64decode("7e+LqXnWSs6jyCfc1R0h7Q==")
    zeroes = b"\x00" * 4
    info = bytes([18, len(key_id)]) + key_id
    info_size = len(info).to_bytes(4, "big")
    inner = zeroes + seed + info_size + info
    outer_size = (len(inner) + 8).to_bytes(4, "big")
    return PSSH(outer_size + b"pssh" + inner)


def flaresolverr_session():
    sessions = json.loads(
        requests.post(
            FLARESOLVERR,
            headers={
                "accept": "application/json",
                "Content-Type": "application/json",
            },
            json={"cmd": "sessions.list"},
        ).content
    )
    print(sessions)
    if "kagane" not in sessions["sessions"]:
        requests.post(
            FLARESOLVERR,
            headers={"Content-Type": "application/json"},
            json={"cmd": "sessions.create", "session": "kagane"},
        )


def update_cookies():
    if (
        time() > COOKIES["expiry"]
        or COOKIES["cf_clearance"] is None
        or COOKIES["user-agent"] is None
    ):
        res = requests.post(
            FLARESOLVERR,
            json={
                "cmd": "request.get",
                "url": "https://kagane.org",
                "session": "kagane",
            },
        )
        res = json.loads(res.text)
        clearance = next(
            filter(lambda s: s["name"] == "cf_clearance", res["solution"]["cookies"])
        )
        COOKIES["cf_clearance"] = clearance["value"]
        COOKIES["expiry"] = clearance["expiry"]
        COOKIES["user-agent"] = res["solution"]["userAgent"]


def get_integrity(series_id, chapter_id):
    if time() > TOKEN["exp"] or TOKEN["token"] is None:
        res = requests.post(
            FLARESOLVERR,
            json={
                "cmd": "request.post",
                "url": "https://kagane.org/api/integrity",
                "session": "kagane",
                "postData": "",
            },
        )
        res = (
            BeautifulSoup(res.text, features="html.parser")
            .find("pre")
            .text.replace("\\", "")
        )

        res = json.loads(res)
        TOKEN["token"] = res["token"]
        TOKEN["exp"] = res["exp"]


@api.get("/drm")
def drm(args):
    series_id = args.get("sid", None)
    chapter_id = args.get("cid", None)
    pssh = get_pssh(series_id, chapter_id)
    device = Device.load("./device.wvd")
    cdm = Cdm.from_device(device)
    session_id = cdm.open()
    challenge = cdm.get_license_challenge(session_id, pssh)
    print("here")
    update_cookies()
    print("there")
    get_integrity(series_id, chapter_id)
    print(
        TOKEN,
        COOKIES,
        file=sys.stderr,
    )
    res = requests.post(
        f"https://yuzuki.kagane.org/api/v2/books/{chapter_id}",
        json={"challenge": base64.b64encode(challenge).decode()},
        headers={
            "Origin": "https://kagane.org",
            "Host": "yuzuki.kagane.org",
            "Referer": "https://kagane.org/",
            "Content-Type": "application/json",
            "x-integrity-token": TOKEN["token"],
            "User-Agent": COOKIES["user-agent"],
        },
        cookies=cookiejar_from_dict({"cf_clearance": COOKIES["cf_clearance"]}),
    )
    cdm.close(session_id)
    return json.loads(res.text)


if __name__ == "__main__":
    httpd = HTTPServer(("", PORT), api)
    flaresolverr_session()
    httpd.serve_forever()
