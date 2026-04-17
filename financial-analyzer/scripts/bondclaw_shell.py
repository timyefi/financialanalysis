#!/usr/bin/env python3
"""
BondClaw native execution adapter.

This module standardizes command construction for the supported runtime
mode:

- native: direct process execution on the host OS
"""

from __future__ import annotations

import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Mapping, Optional, Sequence, Union


ShellArg = Union[str, Path]


@dataclass(frozen=True)
class ShellCommand:
    mode: str
    argv: List[str]
    cwd: Optional[Path] = None
    env: Optional[Dict[str, str]] = None


def current_platform_mode() -> str:
    return "native"


def normalize_shell_mode(mode: Optional[str] = None) -> str:
    requested = (mode or current_platform_mode()).strip().lower()
    if requested in {"native", "windows"}:
        return "native"
    raise ValueError(f"Unsupported shell mode: {requested}")


def normalize_path(path: ShellArg, mode: str = "native") -> str:
    resolved = Path(path).expanduser().resolve()
    normalize_shell_mode(mode)
    return str(resolved)


def render_command(command: Sequence[ShellArg]) -> str:
    return " ".join(shlex.quote(str(part)) for part in command)


def build_shell_command(
    command: Union[str, Sequence[ShellArg]],
    *,
    mode: Optional[str] = None,
    cwd: Optional[ShellArg] = None,
    env: Optional[Mapping[str, str]] = None,
) -> ShellCommand:
    shell_mode = normalize_shell_mode(mode)
    if isinstance(command, str):
        argv = shlex.split(command)
    else:
        argv = [str(part) for part in command]
    if not argv:
        raise ValueError("Command cannot be empty")

    normalized_env = dict(env or {})
    normalized_cwd = Path(cwd).expanduser().resolve() if cwd is not None else None

    return ShellCommand(
        mode=shell_mode,
        argv=argv,
        cwd=normalized_cwd,
        env=normalized_env or None,
    )


def run_shell_command(
    command: Union[str, Sequence[ShellArg]],
    *,
    mode: Optional[str] = None,
    cwd: Optional[ShellArg] = None,
    env: Optional[Mapping[str, str]] = None,
    capture_output: bool = True,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    shell_command = build_shell_command(command, mode=mode, cwd=cwd, env=env)
    return subprocess.run(
        shell_command.argv,
        cwd=shell_command.cwd,
        env=shell_command.env,
        text=True,
        capture_output=capture_output,
        check=check,
        shell=False,
    )


def describe_shell_command(command: Union[str, Sequence[ShellArg]], *, mode: Optional[str] = None) -> Dict[str, str]:
    shell_command = build_shell_command(command, mode=mode)
    return {
        "mode": shell_command.mode,
        "argv": render_command(shell_command.argv),
    }
