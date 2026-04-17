#!/usr/bin/env python3
"""
BondClaw V1 smoke test.

This script checks the current workspace-level data contracts and the unified
runtime outputs that the desktop shell depends on. It is intentionally small
and deterministic so it can be run before every release candidate.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, List, Sequence, Tuple

import bondclaw_runtime


@dataclass(frozen=True)
class SmokeCheck:
    name: str
    check: Callable[[], Tuple[bool, str]]


def _ok(message: str) -> Tuple[bool, str]:
    return True, message


def _fail(message: str) -> Tuple[bool, str]:
    return False, message


def _expect(condition: bool, success: str, failure: str) -> Tuple[bool, str]:
    return (_ok(success) if condition else _fail(failure))


def build_checks() -> List[SmokeCheck]:
    runtime = bondclaw_runtime.build_runtime()

    def check_validation() -> Tuple[bool, str]:
        errors = runtime.validate()
        return _expect(not errors, "runtime assets validation passed", "; ".join(errors) if errors else "")

    def check_template_center() -> Tuple[bool, str]:
        panel = runtime.prompt_center_panel()
        header = panel.get("header", {})
        role_count = int(header.get("role_count", 0))
        workflow_count = int(header.get("workflow_count", 0))
        sample_count = int(header.get("sample_count", 0))
        default_context = panel.get("default_context", {})
        selected_role = panel.get("selected_role", {})
        selected_prompt = panel.get("selected_prompt", {})
        selected_role_manifest_wrapper = selected_role.get("manifest", {})
        canonical_skill = ""
        if isinstance(selected_role_manifest_wrapper, dict):
            selected_role_manifest = selected_role_manifest_wrapper.get("manifest", {})
            if isinstance(selected_role_manifest, dict):
                canonical_skill = str(selected_role_manifest.get("canonical_skill", ""))
        conditions = [
            role_count >= 7,
            workflow_count >= 20,
            sample_count >= 20,
            bool(default_context.get("default_role_id")),
            bool(default_context.get("default_prompt_name")),
            bool(default_context.get("default_provider_id")),
            bool(selected_role.get("display_name")),
            bool(canonical_skill),
            bool(selected_prompt.get("prompt_name")),
        ]
        return _expect(
            all(conditions),
            f"template center ready: roles={role_count}, workflows={workflow_count}, samples={sample_count}",
            "template center missing required counts or default context",
        )

    def check_research_brain() -> Tuple[bool, str]:
        summary = runtime.research_brain()
        case_count = int(summary.get("case_count", 0))
        source_count = int(summary.get("source_count", 0))
        source_group_count = int(summary.get("source_group_count", 0))
        source_card_count = int(summary.get("source_card_count", 0))
        theme_overview_count = int(summary.get("theme_overview_count", 0))
        case_highlight_count = int(summary.get("case_highlight_count", 0))
        case_detail_card_count = int(summary.get("case_detail_card_count", 0))
        cases = runtime.research_brain_cases(role="macro", topic="policy")
        details = runtime.research_brain_case_details(role="macro", topic="policy")
        conditions = [
            source_count >= 2,
            source_group_count >= 3,
            source_card_count >= 3,
            theme_overview_count >= 7,
            case_count >= 20,
            case_highlight_count >= 3,
            case_detail_card_count >= 20,
            len(cases) >= 1,
            len(details) >= 1,
        ]
        return _expect(
            all(conditions),
            f"research brain ready: cases={case_count}, sources={source_count}, highlights={case_highlight_count}",
            "research brain missing required counts or filtered case access",
        )

    def check_contact_queue() -> Tuple[bool, str]:
        summary = runtime.lead_capture()
        queue_count = int(summary.get("queue_count", 0))
        pending_count = len([item for item in summary.get("submission_summaries", []) if item.get("delivery_status") != "delivered"])
        submission_count = len(summary.get("submission_summaries", []) or [])
        if not submission_count:
            submission_count = len(summary.get("submission_summaries", []) or [])
        delivery_order = summary.get("delivery_order") or []
        conditions = [
            queue_count >= 2,
            submission_count >= 1,
            isinstance(delivery_order, list) and len(delivery_order) >= 3,
        ]
        return _expect(
            all(conditions),
            f"contact queue ready: queue={queue_count}, pending={pending_count}, submissions={submission_count}",
            "contact queue missing required counts or delivery order",
        )

    def check_branding_and_settings() -> Tuple[bool, str]:
        settings = runtime.settings_snapshot()
        branding = runtime.branding()
        shell = runtime.shell_config()
        conditions = [
            settings.get("app_name") == branding.get("app_name"),
            settings.get("team_label") == branding.get("team_label"),
            settings.get("default_role_id") == "macro",
            bool(settings.get("default_prompt_name")),
            bool(settings.get("default_provider_id")),
            shell.get("mode") == "native",
            shell.get("shell_family") == "windows",
        ]
        return _expect(
            all(conditions),
            f"settings ready: app={settings.get('app_name')}, mode={shell.get('mode')}",
            "settings snapshot or execution config missing required values",
        )

    def check_working_command() -> Tuple[bool, str]:
        descriptor = runtime.describe_shell_command([sys.executable, "--version"])
        command = descriptor.get("argv", descriptor.get("command", ""))
        mode = descriptor.get("mode", "")
        conditions = [
            bool(command),
            mode == "native",
            "legacy" not in command.lower(),
        ]
        return _expect(
            all(conditions),
            f"execution command ready: mode={mode}",
            "execution command description is invalid or references a legacy terminal marker",
        )

    return [
        SmokeCheck("runtime validation", check_validation),
        SmokeCheck("template center", check_template_center),
        SmokeCheck("research brain", check_research_brain),
        SmokeCheck("contact queue", check_contact_queue),
        SmokeCheck("branding and settings", check_branding_and_settings),
        SmokeCheck("execution command", check_working_command),
    ]


def print_report(results: Sequence[Tuple[str, bool, str]]) -> None:
    for name, passed, message in results:
        status = "PASS" if passed else "FAIL"
        print(f"[{status}] {name}: {message}")


def main() -> int:
    checks = build_checks()
    results: List[Tuple[str, bool, str]] = []
    passed = True
    for check in checks:
        ok, message = check.check()
        results.append((check.name, ok, message))
        passed = passed and ok
    print_report(results)
    if passed:
        print("BondClaw smoke test passed.")
        return 0
    print("BondClaw smoke test failed.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
