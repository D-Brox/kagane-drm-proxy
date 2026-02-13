# Kagane DRM Proxy server

This is a server to proxy drm challenge requests to the Kagane API.
Requires FlareSolverr to be running on port 8191 to pass the CloudFlare challenge.

## Usage

Clone the repository and navigate to it:

```
git clone https://github.com/D-Brox/kagane-drm-proxy.git
cd kagane-drm-proxy
```

The server expects a Widevine Device file to be placed in the folder with the name `device.wvd`.

The easiest way to use this server is to run it with [uv](https://docs.astral.sh/uv/getting-started/installation/):
```
uv run main.py
```

Or, if you prefer using docker, you can use the docker compose file in the repository instead:
```
docker compose up -d
```


You can send a GET request to `http://localhost:9191/drm?cid=${client_id}&ds=false` to get the Kagane challenge response for a chapter, with data saver disabled.

## Disclaimer

This project requires a valid Google-provisioned Private Key (`.pem`) and Client Identification blob (`.bin`) which are not provided by this project.
There are multiple methods of dumping them from DRM-enabled devices.

You can convert those files into a `.wvd` file using [unshackle](https://github.com/unshackle-dl/unshackle/wiki/Provisioning-a-device).
