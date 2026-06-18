WEB_DIRECTORY = "./web"

# ── Utility API routes for the ComfyBIO panel UI ──────────────────────────────
try:
    import asyncio
    import json
    import os
    import sys as _sys
    from pathlib import Path
    from aiohttp import web
    from server import PromptServer

    from llm_core.llm_adapters import get_adapter, list_adapters
    from llm_core.paths import get_comfyui_input_dir, get_comfyui_output_dir
    from llm_core import exec_log, workflow_history

    def _browse_path_payload(path_text):
        requested = Path(path_text or os.path.expanduser("~")).expanduser()
        try:
            current = requested.resolve()
        except Exception:
            current = requested.absolute()

        if not current.exists():
            return {
                "status": "error",
                "error": f"Path does not exist: {current}",
                "path": str(current),
                "parent": "",
                "entries": [],
            }

        if current.is_file():
            current = current.parent

        entries = []
        try:
            for child in current.iterdir():
                try:
                    stat = child.stat()
                    entries.append({
                        "name": child.name,
                        "path": str(child),
                        "kind": "dir" if child.is_dir() else "file",
                        "size": stat.st_size if child.is_file() else None,
                        "mtime": int(stat.st_mtime),
                        "hidden": child.name.startswith("."),
                    })
                except PermissionError:
                    entries.append({
                        "name": child.name,
                        "path": str(child),
                        "kind": "blocked",
                        "size": None,
                        "mtime": None,
                        "hidden": child.name.startswith("."),
                    })
                except OSError:
                    continue
        except PermissionError:
            return {
                "status": "error",
                "error": f"Permission denied: {current}",
                "path": str(current),
                "parent": str(current.parent) if current.parent != current else "",
                "entries": [],
            }

        entries.sort(key=lambda e: (e["kind"] != "dir", e["name"].lower()))
        return {
            "status": "success",
            "error": "",
            "path": str(current),
            "parent": str(current.parent) if current.parent != current else "",
            "entries": entries,
        }

    _GEMINI_INSTALL_SHELL = (
        "curl -fsSL https://antigravity.google/cli/install.cmd -o install.cmd "
        "&& install.cmd && del install.cmd"
        if _sys.platform == "win32"
        else "curl -fsSL https://antigravity.google/cli/install.sh | bash"
    )

    _INSTALL_COMMANDS = {
        "claude": (["npm", "install", "-g", "@anthropic-ai/claude-code"], False),
        "codex":  (["npm", "install", "-g", "@openai/codex"],             False),
        "gemini": ([_GEMINI_INSTALL_SHELL],                                True),
    }

    @PromptServer.instance.routes.get("/comfybio/llm_status")
    async def api_llm_status(request):
        provider = request.rel_url.query.get("provider", "claude")
        try:
            adapter = get_adapter(provider)
            result  = await adapter.status()
            return web.json_response(result)
        except Exception as exc:
            return web.json_response(
                {"installed": False, "authenticated": False, "ready": False,
                 "model": "unknown", "message": str(exc)},
                status=200,
            )

    @PromptServer.instance.routes.get("/comfybio/llm_models")
    async def api_llm_models(request):
        provider = request.rel_url.query.get("provider", "claude")
        try:
            adapter = get_adapter(provider)
            models  = await adapter.list_models()
            return web.json_response({"models": models, "default": models[0] if models else ""})
        except Exception as exc:
            return web.json_response({"models": [], "default": "", "error": str(exc)})

    @PromptServer.instance.routes.post("/comfybio/llm_login")
    async def api_llm_login(request):
        try:
            data     = await request.json()
            provider = data.get("provider", "claude")
            adapter  = get_adapter(provider)
            result   = await adapter.login()
            return web.json_response(result)
        except Exception as exc:
            return web.json_response({"status": "error", "message": str(exc)}, status=400)

    @PromptServer.instance.routes.get("/comfybio/default_paths")
    async def api_default_paths(request):
        return web.json_response({
            "input_dir":  str(get_comfyui_input_dir()),
            "output_dir": str(get_comfyui_output_dir()),
            "home_dir":   str(Path.home()),
        })

    @PromptServer.instance.routes.get("/comfybio/browse_path")
    async def api_browse_path(request):
        path_text = request.rel_url.query.get("path")
        return web.json_response(_browse_path_payload(path_text))

    @PromptServer.instance.routes.post("/comfybio/upload_input")
    async def api_upload_input(request):
        try:
            reader   = await request.multipart()
            field    = await reader.next()
            if field is None:
                return web.json_response({"error": "No file in request"}, status=400)
            filename = field.filename or "upload.bin"
            content  = await field.read()
            input_dir = get_comfyui_input_dir()
            input_dir.mkdir(parents=True, exist_ok=True)
            save_path = input_dir / filename
            save_path.write_bytes(content)
            return web.json_response({
                "saved_path": str(save_path),
                "filename":   filename,
            })
        except Exception as exc:
            return web.json_response({"error": str(exc)}, status=500)

    @PromptServer.instance.routes.get("/comfybio/list_files")
    async def api_list_files(request):
        dir_type   = request.rel_url.query.get("dir", "input")
        target_dir = get_comfyui_input_dir() if dir_type == "input" else get_comfyui_output_dir()
        files: list[str] = []
        if target_dir.exists():
            files = sorted(f.name for f in target_dir.iterdir() if f.is_file())
        return web.json_response({"dir": str(target_dir), "files": files})

    @PromptServer.instance.routes.get("/comfybio/list_dirs")
    async def api_list_dirs(request):
        dir_type   = request.rel_url.query.get("dir", "output")
        target_dir = get_comfyui_input_dir() if dir_type == "input" else get_comfyui_output_dir()
        dirs: list[str] = []
        if target_dir.exists():
            dirs = sorted(d.name for d in target_dir.iterdir() if d.is_dir())
        return web.json_response({"dir": str(target_dir), "dirs": dirs})

    @PromptServer.instance.routes.post("/comfybio/open_dialog")
    async def api_open_dialog(request):
        try:
            data = await request.json()
            mode = data.get("mode", "file")  # "file" | "directory"
            script = (
                "import sys, tkinter as tk\n"
                "from tkinter import filedialog\n"
                "root = tk.Tk(); root.withdraw()\n"
                "root.attributes('-topmost', True)\n"
                "mode = sys.argv[1]\n"
                "path = filedialog.askopenfilename(title='Select Input File') "
                "if mode == 'file' else "
                "filedialog.askdirectory(title='Select Output Directory')\n"
                "print(path or '', end='')\n"
                "root.destroy()"
            )
            proc = await asyncio.create_subprocess_exec(
                _sys.executable, "-c", script, mode,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()
            path = stdout.decode().strip()
            if proc.returncode != 0:
                err_text = stderr.decode().strip()
                no_display = (
                    "no display" in err_text.lower()
                    or "DISPLAY" in err_text
                    or "TclError" in err_text
                )
                error_type = "no_display" if no_display else "error"
                return web.json_response({
                    "path": "", "error_type": error_type,
                    "error": err_text or "Dialog process failed",
                })
            return web.json_response({"path": path})
        except Exception as exc:
            return web.json_response({"path": "", "error_type": "error", "error": str(exc)}, status=500)

    @PromptServer.instance.routes.post("/comfybio/llm_install")
    async def api_llm_install(request):
        try:
            data     = await request.json()
            provider = data.get("provider", "claude")
            entry    = _INSTALL_COMMANDS.get(provider)
            if not entry:
                return web.json_response(
                    {"status": "error", "message": f"No install command for provider: {provider}"},
                    status=400,
                )
            cmd, use_shell = entry
            if use_shell:
                proc = await asyncio.create_subprocess_shell(
                    cmd[0],
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.STDOUT,
                )
            else:
                proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.STDOUT,
                )
            stdout, _ = await proc.communicate()
            output = stdout.decode().strip()
            if proc.returncode == 0:
                return web.json_response({"status": "success", "message": output})
            return web.json_response({"status": "error", "message": output}, status=500)
        except Exception as exc:
            return web.json_response({"status": "error", "message": str(exc)}, status=500)

    @PromptServer.instance.routes.get("/comfybio/providers")
    async def api_providers(request):
        return web.json_response({"providers": list_adapters()})

    @PromptServer.instance.routes.get("/comfybio/execution_log")
    async def api_execution_log(request):
        return web.json_response({"logs": exec_log.snapshot()})

    @PromptServer.instance.routes.get("/comfybio/llm_login_logs")
    async def api_llm_login_logs(request):
        import tempfile
        log_path = os.path.join(tempfile.gettempdir(), "comfybio_login.log")
        if os.path.exists(log_path):
            try:
                with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                return web.json_response({"status": "success", "logs": content})
            except Exception as e:
                return web.json_response({"status": "error", "message": str(e)})
        return web.json_response({"status": "success", "logs": "[System] Waiting for terminal logs..."})

    def _get_login_terminal_cmd(provider: str) -> list[str]:
        """Return the CLI login command for the given provider, resolving the binary path."""
        import shutil

        specs = {
            "claude": ("claude",  ["auth", "login"]),
            "codex":  ("codex",   ["login"]),
            "gemini": ("gemini",  ["auth", "login"]),
        }
        binary_name, args = specs.get(provider, ("claude", ["auth", "login"]))

        binary = shutil.which(binary_name)
        if not binary:
            home = os.path.expanduser("~")
            for candidate in (
                os.path.join(home, ".local", "bin", binary_name),
                os.path.join(home, ".npm-global", "bin", binary_name),
                f"/usr/local/bin/{binary_name}",
                f"/opt/homebrew/bin/{binary_name}",
            ):
                if os.path.exists(candidate):
                    binary = candidate
                    break
            else:
                binary = binary_name

        return [binary] + args

    @PromptServer.instance.routes.get("/comfybio/terminal")
    async def api_terminal_ws(request):
        """WebSocket PTY endpoint — streams a CLI login session into xterm.js."""
        import platform

        ws = web.WebSocketResponse()
        await ws.prepare(request)

        provider = request.rel_url.query.get("provider", "claude")
        cols     = max(20, int(request.rel_url.query.get("cols", "80")))
        rows     = max(4,  int(request.rel_url.query.get("rows", "24")))

        if platform.system() == "Windows":
            await ws.send_str("\r\nPTY is not supported on Windows.\r\n")
            await ws.close()
            return ws

        import pty, fcntl, termios, struct

        cmd = _get_login_terminal_cmd(provider)
        master_fd, slave_fd = pty.openpty()

        fcntl.ioctl(master_fd, termios.TIOCSWINSZ,
                    struct.pack("HHHH", rows, cols, 0, 0))

        env = {**os.environ, "TERM": "xterm-256color", "COLORTERM": "truecolor"}

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=slave_fd, stdout=slave_fd, stderr=slave_fd,
            env=env, preexec_fn=os.setsid, close_fds=True,
        )
        os.close(slave_fd)
        os.set_blocking(master_fd, False)

        loop     = asyncio.get_running_loop()
        pty_q: asyncio.Queue = asyncio.Queue()

        def _on_pty_readable():
            try:
                data = os.read(master_fd, 4096)
                pty_q.put_nowait(data if data else None)
            except (BlockingIOError, OSError):
                pty_q.put_nowait(None)

        loop.add_reader(master_fd, _on_pty_readable)

        async def _pty_to_ws():
            while True:
                data = await pty_q.get()
                if data is None:
                    break
                try:
                    await ws.send_bytes(data)
                except Exception:
                    break

        async def _ws_to_pty():
            async for msg in ws:
                if msg.type == web.WSMsgType.BINARY:
                    try:
                        os.write(master_fd, msg.data)
                    except OSError:
                        break
                elif msg.type == web.WSMsgType.TEXT:
                    try:
                        ev = json.loads(msg.data)
                        if ev.get("type") == "resize":
                            r = max(4,  int(ev.get("rows", rows)))
                            c = max(20, int(ev.get("cols", cols)))
                            fcntl.ioctl(master_fd, termios.TIOCSWINSZ,
                                        struct.pack("HHHH", r, c, 0, 0))
                    except Exception:
                        pass
                elif msg.type in (web.WSMsgType.ERROR, web.WSMsgType.CLOSE):
                    break

        try:
            t_send = asyncio.create_task(_pty_to_ws())
            t_recv = asyncio.create_task(_ws_to_pty())
            done, pending = await asyncio.wait(
                [t_send, t_recv], return_when=asyncio.FIRST_COMPLETED
            )
            for t in pending:
                t.cancel()
                await asyncio.gather(t, return_exceptions=True)
        finally:
            loop.remove_reader(master_fd)
            try:
                os.close(master_fd)
            except OSError:
                pass
            try:
                proc.kill()
                await proc.wait()
            except Exception:
                pass

        return ws

    @PromptServer.instance.routes.post("/comfybio/generate")
    async def api_generate(request: web.Request) -> web.StreamResponse:
        data        = await request.json()
        query       = data.get("query", "").strip()
        input_path  = data.get("input_path", "")
        output_dir  = data.get("output_dir", "./output")
        provider    = data.get("provider", "claude")
        model       = data.get("model", "").strip() or None
        from llm_core.llm_runner import generate_biopython_workflow, normalize_mode

        mode        = normalize_mode(data.get("mode", "hybrid"))
        from llm_core.biopython_comfy_adapter import canonical_to_comfy_json, load_registry

        resp = web.StreamResponse(headers={
            "Content-Type":    "text/event-stream",
            "Cache-Control":   "no-cache",
            "X-Accel-Buffering": "no",
        })
        await resp.prepare(request)

        async def send(event_type: str, msg: str = "", **extra) -> None:
            payload = {"type": event_type, "msg": msg, **extra}
            await resp.write(f"data: {json.dumps(payload, ensure_ascii=False)}\n\n".encode())

        q = exec_log.subscribe()
        gen_task = asyncio.create_task(
            generate_biopython_workflow(provider, query, input_path, output_dir, model=model, mode=mode)
        )

        try:
            # 실시간으로 exec_log 메시지 포워딩
            while not gen_task.done():
                try:
                    entry = await asyncio.wait_for(q.get(), timeout=0.15)
                    level = entry.get("level", "INFO")
                    await send("log", entry["msg"], level=level)
                except asyncio.TimeoutError:
                    pass

            # 큐 잔여 항목 flush
            while not q.empty():
                entry = q.get_nowait()
                await send("log", entry["msg"], level=entry.get("level", "INFO"))

            result = gen_task.result()  # 예외가 있으면 여기서 raise
            final_spec = result["final_spec"]

            await send("status", "워크플로우 JSON 변환 중…")
            registry   = load_registry()
            comfy_json = canonical_to_comfy_json(final_spec, registry, input_path, output_dir)
            n_nodes    = len(final_spec.get("nodes", []))
            n_edges    = len(final_spec.get("edges", []))

            workflow_history.append_record({
                "query":                    query,
                "input_path":               input_path,
                "output_dir":               output_dir,
                "provider":                 provider,
                "model":                    model or "",
                "mode":                     result.get("mode", mode),
                "status":                   "success",
                "workflow_json":            comfy_json,
                "workflow_spec":            final_spec,
                "raw_workflow_spec":        result.get("raw_spec"),
                "normalized_workflow_spec": result.get("normalized_spec"),
                "final_workflow_spec":      final_spec,
                "intent":                   result.get("intent", ""),
                "template_id":              result.get("template_id", ""),
                "equivalence_score":        result.get("equivalence_score", 0.0),
                "repair_applied":           result.get("repair_applied", False),
                "repair_summary":           result.get("repair_summary", []),
                "repair_actions":           result.get("repair_actions", []),
                "node_count":               n_nodes,
                "edge_count":               n_edges,
            })

            await send("done",
                       f"{n_nodes}개 노드, {n_edges}개 엣지 생성 완료",
                       workflow=comfy_json,
                       node_count=n_nodes,
                       intent=result.get("intent", ""),
                       template_id=result.get("template_id", ""),
                       equivalence_score=result.get("equivalence_score", 0.0),
                       repair_applied=result.get("repair_applied", False),
                       mode=result.get("mode", mode))

        except Exception as exc:
            workflow_history.append_record({
                "query":         query,
                "input_path":    input_path,
                "output_dir":    output_dir,
                "provider":      provider,
                "model":         model or "",
                "mode":          mode,
                "status":        "error",
                "error_message": str(exc),
            })
            await send("error", str(exc))

        finally:
            gen_task.cancel()
            await asyncio.gather(gen_task, return_exceptions=True)
            exec_log.unsubscribe(q)
            await resp.write_eof()

        return resp


    @PromptServer.instance.routes.get("/comfybio/workflow_history")
    async def api_workflow_history(request):
        try:
            limit = int(request.rel_url.query.get("limit", "20"))
        except ValueError:
            limit = 20
        include_workflow = request.rel_url.query.get("include_workflow") == "1"
        return web.json_response({
            "history_path": str(workflow_history.history_path()),
            "records": workflow_history.list_recent(limit=limit, include_workflow=include_workflow),
        })

    @PromptServer.instance.routes.get("/comfybio/workflow_history/{record_id}")
    async def api_workflow_history_record(request):
        record = workflow_history.get_record(request.match_info["record_id"])
        if not record:
            return web.json_response({"error": "History record not found"}, status=404)
        return web.json_response(record)

    @PromptServer.instance.routes.post("/comfybio/workflow_history/search")
    async def api_workflow_history_search(request):
        try:
            data = await request.json()
            query = data.get("query", "")
            limit = int(data.get("limit", 3))
            min_score = float(data.get("min_score", 0.42))
            matches = workflow_history.find_similar(query, limit=limit, min_score=min_score)
            return web.json_response({"matches": matches})
        except Exception as exc:
            return web.json_response({"error": str(exc)}, status=400)

except ImportError:
    pass


