from bioflow_harness.server.routes import register_routes


class _FakeRoutes:
    def __init__(self):
        self.registered = []

    def post(self, path):
        def deco(fn):
            self.registered.append(("POST", path))
            return fn

        return deco

    def get(self, path):
        def deco(fn):
            self.registered.append(("GET", path))
            return fn

        return deco


class _FakeServer:
    def __init__(self):
        self.routes = _FakeRoutes()


def test_register_routes_attaches_three_endpoints():
    server = _FakeServer()
    register_routes(server)
    assert ("POST", "/comfybio/compile") in server.routes.registered
    assert ("POST", "/comfybio/generate") in server.routes.registered
    assert ("GET", "/comfybio/health") in server.routes.registered
