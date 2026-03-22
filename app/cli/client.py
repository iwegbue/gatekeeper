"""
Thin HTTP client wrapper around the Gatekeeper JSON API.
"""
import httpx


class GatekeeperClient:
    def __init__(self, base_url: str, token: str | None = None):
        self.base_url = base_url
        headers = {"Accept": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        self._client = httpx.Client(base_url=base_url, headers=headers, timeout=30)

    def get(self, path: str, **params) -> dict | list:
        r = self._client.get(path, params={k: v for k, v in params.items() if v is not None})
        r.raise_for_status()
        return r.json()

    def post(self, path: str, json: dict | None = None) -> dict | list:
        r = self._client.post(path, json=json or {})
        r.raise_for_status()
        return r.json()

    def put(self, path: str, json: dict | None = None) -> dict | list:
        r = self._client.put(path, json=json or {})
        r.raise_for_status()
        return r.json()

    def patch(self, path: str, json: dict | None = None) -> dict | list:
        r = self._client.patch(path, json=json or {})
        r.raise_for_status()
        return r.json()

    def close(self) -> None:
        self._client.close()
