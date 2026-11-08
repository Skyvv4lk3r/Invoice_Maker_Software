import dataclasses
import inspect
import subprocess
import sys

import pytest

from invoice_generator.application.contracts import dto


def test_public_dtos_are_frozen():
    models = [
        model
        for _, model in inspect.getmembers(dto, inspect.isclass)
        if model.__module__ == dto.__name__
    ]
    assert models
    for model in models:
        assert dataclasses.is_dataclass(model)
        assert model.__dataclass_params__.frozen


def test_result_has_exactly_one_outcome():
    with pytest.raises(ValueError):
        dto.Result()
    with pytest.raises(ValueError):
        dto.Result(value=True, error=dto.ApplicationError("ERROR", "Invalid"))


def test_backend_can_execute_without_importing_qt(tmp_path):
    script = """
import sys
from pathlib import Path
from invoice_generator.bootstrap import main
assert main(['--demo', '--data-dir', sys.argv[1]]) == 0
assert not any(name.startswith('PySide6') for name in sys.modules)
"""
    result = subprocess.run(
        [sys.executable, "-c", script, str(tmp_path)], capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr
