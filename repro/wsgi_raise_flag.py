import httpx


def boom(environ, start_response):
    raise RuntimeError("app exploded before start_response")


def boom_after(environ, start_response):
    start_response("200 OK", [("Content-Length", "2")])
    raise RuntimeError("app exploded after start_response")


def lazy_boom(environ, start_response):
    start_response("200 OK", [("Content-Length", "2")])

    def gen():
        yield b"ok"
        raise RuntimeError("exploded while streaming")

    return gen()


print("=== WSGI, raise_app_exceptions=False (docs promise: 'Inspect 500 error responses') ===")
for label, app in [("raise-before-start_response", boom),
                   ("raise-after-start_response", boom_after),
                   ("raise-while-streaming", lazy_boom)]:
    try:
        with httpx.Client(transport=httpx.WSGITransport(app=app, raise_app_exceptions=False)) as c:
            r = c.get("http://test/")
            print(f"  {label}: status={r.status_code!r} text={r.text!r}")
    except BaseException as exc:
        print(f"  {label}: {type(exc).__module__}.{type(exc).__name__}: {exc}")

print("=== ASGI, raise_app_exceptions=False, same three shapes ===")


async def aboom_before(scope, receive, send):
    raise RuntimeError("app exploded before response.start")


async def aboom_after(scope, receive, send):
    await send({"type": "http.response.start", "status": 200, "headers": []})
    raise RuntimeError("app exploded after response.start")


import anyio


async def go(app, flag):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app, raise_app_exceptions=flag)) as c:
        r = await c.get("http://test/")
        return r.status_code


for label, app in [("raise-before-start", aboom_before), ("raise-after-start", aboom_after)]:
    try:
        print(f"  {label}: status={anyio.run(go, app, False)!r}")
    except BaseException as exc:
        print(f"  {label}: {type(exc).__module__}.{type(exc).__name__}: {exc}")

print("=== and the 'app never completes the response' shapes (both transports) ===")


def no_start(environ, start_response):
    return []


async def anoop(scope, receive, send):
    return


try:
    with httpx.Client(transport=httpx.WSGITransport(app=no_start, raise_app_exceptions=False)) as c:
        print("  wsgi no_start:", c.get("http://test/").status_code)
except BaseException as exc:
    print(f"  wsgi no_start: {type(exc).__module__}.{type(exc).__name__}: {exc!r}")
try:
    print("  asgi noop:", anyio.run(go, anoop, False))
except BaseException as exc:
    print(f"  asgi noop: {type(exc).__module__}.{type(exc).__name__}: {exc!r}")
