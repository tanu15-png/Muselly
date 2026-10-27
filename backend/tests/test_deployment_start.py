"""Container entrypoint honors platform ports and rejects invalid configuration."""
import importlib.util
from pathlib import Path
from unittest.mock import patch

import pytest

spec = importlib.util.spec_from_file_location("deployment_start", Path(__file__).parents[1] / "start.py")
start = importlib.util.module_from_spec(spec)
spec.loader.exec_module(start)


@pytest.mark.parametrize("environment,port", [({}, "8080"), ({"PORT": "9090"}, "9090")])
def test_platform_port_and_public_bind(environment, port):
    with patch.dict(start.os.environ, environment, clear=True), patch.object(start.os, "execvp") as launch:
        start.main()
    launch.assert_called_once_with(
        "uvicorn", ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", port]
    )


@pytest.mark.parametrize("port", ["0", "65536", "abc", ""])
def test_invalid_port_fails_before_server_launch(port):
    with patch.dict(start.os.environ, {"PORT": port}), patch.object(start.os, "execvp") as launch:
        with pytest.raises(SystemExit, match="PORT must be"):
            start.main()
    launch.assert_not_called()
