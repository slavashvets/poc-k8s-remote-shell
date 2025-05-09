# k8s-shell — Proof-of-concept remote shell for a Kubernetes pod

An example that opens an interactive Bash session inside an existing Kubernetes pod.
It uses **kubernetes-asyncio** to connect via the Kubernetes _exec_ WebSocket API and streams standard input, output, and error channels concurrently.

## Overview

- Loads the active kube-config (the same configuration used by `kubectl`).
- Upgrades the connection to a WebSocket for `/exec`.
- Sends commands programmatically and returns their standard output and error.

```python
async with K8sBashSession() as sh:
    stdout, stderr = await sh.run("echo hello from $(hostname)")
```

## Requirements

- Python **3.10 or later** (tested with 3.13).
- [`uv`](https://github.com/astral-sh/uv) installed and available on your path.
- A valid `~/.kube/config` pointing to a running cluster.
- A running pod in the target namespace (default constants can be modified at the top of `main.py`).

## Quick start

```bash
uv run main.py
```

Typical output:

```text
STDOUT: hello from sys-report-daily-a1b2c3
STDERR:
```

## Configuration

Edit the constants in **main.py** to change the target pod, namespace, or shell command:

```python
NAMESPACE = "my-namespace"
POD_NAME = "my-pod"
SHELL_COMMAND = ["/bin/sh"]
```

## Caveats

- This is a proof-of-concept; reconnection logic, advanced authentication handling, and input sanitisation are not implemented.
- It assumes the container image contains the specified shell (default `/bin/bash`).
