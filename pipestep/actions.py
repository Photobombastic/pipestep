"""Best-effort local equivalents for common GitHub Actions."""

import re
from typing import Callable, List, Optional, Tuple


def _checkout_equiv(inputs: dict) -> tuple[str, str]:
    return (
        "Clone/checkout repository (already mounted at /workspace)",
        "echo 'Repository is mounted at /workspace via Docker volume'",
    )


def _setup_node_equiv(inputs: dict) -> tuple[str, str]:
    version = inputs.get("node-version", "")
    if version:
        desc = f"Install Node.js {version}"
        cmd = (
            f"apt-get update -qq && apt-get install -y -qq curl > /dev/null 2>&1 && "
            f"curl -fsSL https://deb.nodesource.com/setup_{version}.x | bash - > /dev/null 2>&1 && "
            f"apt-get install -y -qq nodejs > /dev/null 2>&1 && "
            f"node --version && npm --version"
        )
    else:
        desc = "Install Node.js (system default)"
        cmd = "apt-get update -qq && apt-get install -y -qq nodejs npm > /dev/null 2>&1 && node --version && npm --version"
    return desc, cmd


def _setup_python_equiv(inputs: dict) -> tuple[str, str]:
    version = inputs.get("python-version", "")
    if version:
        desc = f"Install Python {version}"
        # Use deadsnakes PPA for specific versions
        cmd = (
            f"apt-get update -qq && apt-get install -y -qq software-properties-common > /dev/null 2>&1 && "
            f"add-apt-repository -y ppa:deadsnakes/ppa > /dev/null 2>&1 && "
            f"apt-get update -qq && "
            f"apt-get install -y -qq python{version} python{version}-venv > /dev/null 2>&1 && "
            f"python{version} --version"
        )
    else:
        desc = "Install Python (system default)"
        cmd = "apt-get update -qq && apt-get install -y -qq python3 python3-pip > /dev/null 2>&1 && python3 --version"
    return desc, cmd


def _setup_go_equiv(inputs: dict) -> tuple[str, str]:
    version = inputs.get("go-version", "")
    if version:
        desc = f"Install Go {version}"
        cmd = (
            f"apt-get update -qq && apt-get install -y -qq curl > /dev/null 2>&1 && "
            f"curl -fsSL https://go.dev/dl/go{version}.linux-amd64.tar.gz | tar -C /usr/local -xzf - && "
            f"export PATH=$PATH:/usr/local/go/bin && "
            f"go version"
        )
    else:
        desc = "Install Go (system default)"
        cmd = "apt-get update -qq && apt-get install -y -qq golang > /dev/null 2>&1 && go version"
    return desc, cmd


def _setup_java_equiv(inputs: dict) -> tuple[str, str]:
    version = inputs.get("java-version", "")
    distribution = inputs.get("distribution", "temurin")
    if version:
        desc = f"Install Java {version} ({distribution})"
    else:
        desc = "Install Java (system default)"
    cmd = "apt-get update -qq && apt-get install -y -qq default-jdk > /dev/null 2>&1 && java --version"
    return desc, cmd


def _noop_equiv(desc: str) -> Callable:
    def _equiv(inputs: dict) -> tuple[str, str]:
        return desc, f"echo '{desc}'"
    return _equiv


# Map action patterns to equivalent-generating functions.
ACTION_HANDLERS: List[Tuple[str, Callable]] = [
    (r"^actions/checkout@", _checkout_equiv),
    (r"^actions/setup-node@", _setup_node_equiv),
    (r"^actions/setup-python@", _setup_python_equiv),
    (r"^actions/setup-go@", _setup_go_equiv),
    (r"^actions/setup-java@", _setup_java_equiv),
    (r"^actions/cache@", _noop_equiv("Cache — no-op locally")),
    (r"^actions/upload-artifact@", _noop_equiv("Upload artifact — no-op locally")),
    (r"^actions/download-artifact@", _noop_equiv("Download artifact — no-op locally")),
]


def get_action_equivalent(action_ref: str, inputs: Optional[dict] = None) -> Optional[Tuple[str, str]]:
    """Return (description, command) for a known action, or None.

    If inputs (from `with:`) are provided, they are used to generate
    a more precise equivalent command (e.g., specific Node.js version).
    """
    if inputs is None:
        inputs = {}
    for pattern, handler in ACTION_HANDLERS:
        if re.match(pattern, action_ref):
            return handler(inputs)
    return None
