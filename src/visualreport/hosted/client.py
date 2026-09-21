"""Explicit-origin API requests with no credential-bearing redirects."""

import json
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def exchange(origin: str, token: str, path: str, payload: dict, method: str) -> dict:
    parsed = urlsplit(origin)
    if (
        parsed.scheme != "https"
        or not parsed.netloc
        or parsed.path
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("An explicit HTTPS origin without path is required")
    request = Request(
        origin + path,
        data=json.dumps(payload).encode(),
        headers={
            "Content-Type": "application/json",
            "Origin": origin,
            "Cookie": f"CF_Authorization={token}",
            "Cf-Access-Jwt-Assertion": token,
        },
        method=method,
    )
    try:
        with build_opener(NoRedirect()).open(request, timeout=60) as response:
            return json.load(response)
    except HTTPError as error:
        raise RuntimeError(
            f"Request failed (HTTP {error.code}); verify Access session and report permission"
        ) from None
