"""AOP Parser — loads a JSON AOP definition and hydrates the DAG engine."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Union

from core.models import AOPDefinition


def parse_aop_json(raw: dict) -> AOPDefinition:
    return AOPDefinition(**raw)


def load_aop_from_file(filepath: Union[str, Path]) -> AOPDefinition:
    with open(filepath) as f:
        raw = json.load(f)
    return parse_aop_json(raw)
