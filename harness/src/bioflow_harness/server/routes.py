from __future__ import annotations

from bioflow_harness.server.handlers import compile_spec, generate_workflow


def register_routes(server) -> None:
    from aiohttp import web

    routes = server.routes

    @routes.post("/comfybio/compile")
    async def _compile(request):
        payload = await request.json()
        return web.json_response(compile_spec(payload))

    @routes.post("/comfybio/generate")
    async def _generate(request):
        payload = await request.json()
        return web.json_response(generate_workflow(payload))

    @routes.get("/comfybio/health")
    async def _health(request):
        return web.json_response({"status": "ok"})
