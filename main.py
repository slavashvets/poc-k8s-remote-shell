from __future__ import annotations

import asyncio
from contextlib import AsyncExitStack
from typing import AsyncContextManager, cast

from aiohttp import ClientWebSocketResponse
from aiohttp.http import WSMsgType
from kubernetes_asyncio import client, config
from kubernetes_asyncio.stream import WsApiClient
from kubernetes_asyncio.stream.ws_client import (
    ERROR_CHANNEL,
    STDERR_CHANNEL,
    STDIN_CHANNEL,
    STDOUT_CHANNEL,
)

NAMESPACE: str = "default"
POD_NAME: str = "sys-report-daily"
SHELL_COMMAND: list[str] = ["/bin/bash"]
_STDIN_MARKER = chr(STDIN_CHANNEL)


class K8sBashSession:
    """Interactive bash session within an existing Kubernetes pod."""

    _exit_stack: AsyncExitStack | None = None
    _websocket: ClientWebSocketResponse | None = None

    async def __aenter__(self) -> "K8sBashSession":
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()

    async def start(self) -> None:
        """Load kube config and open an exec-websocket to the pod."""
        await config.load_kube_config()

        self._exit_stack = AsyncExitStack()
        await self._exit_stack.__aenter__()

        ws_api = await self._exit_stack.enter_async_context(WsApiClient())
        core_api = client.CoreV1Api(api_client=ws_api)

        exec_cm = cast(
            AsyncContextManager[ClientWebSocketResponse],
            await core_api.connect_get_namespaced_pod_exec(
                name=POD_NAME,
                namespace=NAMESPACE,
                command=SHELL_COMMAND,
                stdin=True,
                stdout=True,
                stderr=True,
                tty=False,
                _preload_content=False,
            ),  # type: ignore[reportGeneralTypeIssues]
        )

        self._websocket = await self._exit_stack.enter_async_context(exec_cm)

    async def run(self, command: str, timeout: float = 1.0) -> tuple[str, str]:
        """Execute *command* and return its (stdout, stderr)."""
        if self._websocket is None:
            raise RuntimeError("Shell session is not started.")

        await self._websocket.send_bytes(
            f"{_STDIN_MARKER}{command.rstrip()}\n".encode()
        )

        stdout_buf: list[str] = []
        stderr_buf: list[str] = []
        error_accum = ""

        while True:
            try:
                msg = await self._websocket.receive(timeout=timeout)
            except asyncio.TimeoutError:
                break

            if msg.type in (
                WSMsgType.CLOSE,
                WSMsgType.CLOSING,
                WSMsgType.CLOSED,
            ):
                break

            channel = msg.data[0]
            data = msg.data[1:].decode()

            if channel == STDOUT_CHANNEL:
                stdout_buf.append(data)
            elif channel == STDERR_CHANNEL:
                stderr_buf.append(data)
            elif channel == ERROR_CHANNEL:
                error_accum += data

        if error_accum:
            stderr_buf.append(f"\n<exec-error>: {error_accum}")

        return "".join(stdout_buf), "".join(stderr_buf)

    async def close(self) -> None:
        """Close websocket and clean up resources (idempotent)."""
        if self._exit_stack:
            await self._exit_stack.aclose()
            self._exit_stack = None
            self._websocket = None


async def demo() -> None:
    """Minimal usage example."""
    async with K8sBashSession() as sh:
        out, err = await sh.run("echo hello from $(hostname)")
        print("STDOUT:", out)
        print("STDERR:", err)

        out, err = await sh.run("ls /")
        print("STDOUT:", out)
        print("STDERR:", err)


if __name__ == "__main__":
    asyncio.run(demo())
