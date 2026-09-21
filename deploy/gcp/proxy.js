const PUBLIC_ORIGIN = "https://artefacts.saunois.xyz";

function privateResponse(response) {
  const result = new Response(response.body, response);
  result.headers.set("Cache-Control", "private, no-store");
  result.headers.set("Cloudflare-CDN-Cache-Control", "no-store");
  result.headers.set("CDN-Cache-Control", "no-store");
  return result;
}

function backendRequest(request, backendOrigin) {
  const url = new URL(request.url);
  const target = new URL(backendOrigin);
  target.pathname = url.pathname;
  target.search = url.search;
  const upstream = new Request(target, request);
  upstream.headers.set("Host", target.host);
  upstream.headers.delete("Forwarded");
  upstream.headers.set("X-Forwarded-Host", new URL(PUBLIC_ORIGIN).host);
  upstream.headers.set("X-Forwarded-Proto", "https");
  return upstream;
}

function clientResponse(response, backendOrigin) {
  const result = privateResponse(response);
  const location = result.headers.get("Location");
  if (location) {
    const redirect = new URL(location, backendOrigin);
    if (redirect.origin === backendOrigin) {
      result.headers.set("Location", PUBLIC_ORIGIN + redirect.pathname + redirect.search + redirect.hash);
    }
  }
  return result;
}

export default {
  async fetch(request, env) {
    if (new URL(request.url).origin !== PUBLIC_ORIGIN) {
      return privateResponse(new Response("Not found", { status: 404 }));
    }
    if (!request.headers.get("Cf-Access-Jwt-Assertion")) {
      return privateResponse(new Response("Cloudflare Access authentication required", { status: 401 }));
    }
    // The backend verifies the JWT signature, issuer, audience and report ACL.
    const response = await fetch(backendRequest(request, env.BACKEND_ORIGIN), {
      redirect: "manual",
      cache: "no-store",
    });
    return clientResponse(response, env.BACKEND_ORIGIN);
  },
};
