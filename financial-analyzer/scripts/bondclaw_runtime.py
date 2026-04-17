#!/usr/bin/env python3
"""
BondClaw unified runtime facade.

This is the single entry point future UI and automation layers should prefer.
It wraps:

- bondclaw_assets: catalog / validation / prompt loading
- bondclaw_shell: command construction and execution
- bondclaw_providers: provider registry queries and wizard presets
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Union
import sys

import bondclaw_assets
import bondclaw_providers
import bondclaw_shell


ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = Path(__file__).resolve().parents[3]
DESKTOP_SHELL_DIR = REPO_ROOT / "desktop-shell"
for candidate in [
    DESKTOP_SHELL_DIR,
    DESKTOP_SHELL_DIR / "bridge",
    DESKTOP_SHELL_DIR / "home",
    DESKTOP_SHELL_DIR / "pages",
    DESKTOP_SHELL_DIR / "settings",
    DESKTOP_SHELL_DIR / "prompt_center",
    DESKTOP_SHELL_DIR / "research_brain",
    DESKTOP_SHELL_DIR / "lead_capture",
    DESKTOP_SHELL_DIR / "brand_upgrade",
]:
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))


ShellArg = Union[str, Path]


@dataclass(frozen=True)
class BondClawRuntime:
    shell_mode: str = "native"

    def branding(self) -> Dict[str, Any]:
        return bondclaw_assets.load_branding_config()

    def shell_config(self) -> Dict[str, Any]:
        return bondclaw_assets.load_execution_shell_config()

    def provider_matrix(self) -> List[Dict[str, Any]]:
        return bondclaw_providers.build_provider_matrix()

    def provider_wizard(self, provider_id: str) -> Dict[str, Any]:
        return bondclaw_providers.key_only_provider_wizard(provider_id)

    def provider_profile(self, provider_id: str) -> bondclaw_providers.ProviderAdapterProfile:
        return bondclaw_providers.get_provider_profile(provider_id)

    def role_ids(self) -> List[str]:
        return bondclaw_assets.list_role_ids()

    def roles(self) -> List[Dict[str, Any]]:
        return [summary.__dict__ for summary in bondclaw_assets.load_prompt_pack_summary()]

    def prompt_pack_names(self, role: Optional[str] = None) -> List[str]:
        return bondclaw_assets.list_prompt_pack_names(role=role)

    def prompt_manifest(self, role: str) -> Dict[str, Any]:
        return bondclaw_assets.load_prompt_pack_manifest(role)

    def prompt_pack(self, role: str, prompt_name: str) -> Dict[str, Any]:
        return bondclaw_assets.load_prompt_pack(role, prompt_name)

    def settings_snapshot(self) -> Dict[str, Any]:
        branding = self.branding()
        provider_matrix = self.provider_matrix()
        default_provider_id = provider_matrix[0].get("provider_id", "zai") if provider_matrix else "zai"
        return {
            "app_name": branding.get("app_name", "BondClaw"),
            "team_label": branding.get("team_label", "国投固收 张亮/叶青"),
            "shell_mode": self.shell_mode,
            "execution_mode": self.shell_mode,
            "execution_family": "windows-native",
            "default_provider_id": default_provider_id,
            "default_role_id": "macro",
            "default_prompt_name": "daily-brief",
            "lead_capture_enabled": True,
            "support_banner_enabled": True,
            "notification_level": "normal",
            "api_key_storage": "local-keychain",
        }

    def prompt_center_panel(self, role: Optional[str] = None, prompt_name: Optional[str] = None) -> Dict[str, Any]:
        import prompt_center.prompt_center_model

        return prompt_center.prompt_center_model.build_prompt_center_panel_model(
            self,
            role=role,
            prompt_name=prompt_name,
        ).to_dict()

    def catalog(self) -> Dict[str, Any]:
        return bondclaw_assets.build_catalog()

    def summary(self) -> Dict[str, Any]:
        return bondclaw_assets.build_summary()

    def research_brain(self) -> Dict[str, Any]:
        return self.summary().get("research_brain", {})

    def lead_capture(self) -> Dict[str, Any]:
        return self.summary().get("lead_capture", {})

    def research_brain_cases(self, role: Optional[str] = None, topic: Optional[str] = None) -> List[Dict[str, Any]]:
        import bondclaw_research_brain

        return [
            summary.__dict__
            for summary in bondclaw_research_brain.filter_case_summaries(role=role, topic=topic)
        ]

    def research_brain_case_details(self, role: Optional[str] = None, topic: Optional[str] = None) -> List[Dict[str, Any]]:
        import bondclaw_research_brain

        cases = bondclaw_research_brain.load_case_detail_cards()
        filtered: List[Dict[str, Any]] = []
        for case in cases:
            if role and role != case.prompt_role and role not in case.role_tags:
                continue
            if topic and topic not in case.topic_tags:
                continue
            filtered.append(case.to_dict())
        return filtered

    def research_brain_case_detail(self, case_id: str) -> Dict[str, Any]:
        import bondclaw_research_brain

        case = bondclaw_research_brain.get_case_detail(case_id)
        prompt_role = str(case.get("prompt_role", ""))
        prompt_workflow = str(case.get("recommended_prompt", case.get("prompt_workflow", "")))
        prompt_pack: Optional[Dict[str, Any]] = None
        prompt_pack_error: Optional[str] = None
        if prompt_role and prompt_workflow:
            try:
                prompt_pack = self.prompt_pack(prompt_role, prompt_workflow)
            except Exception as exc:  # pragma: no cover - defensive bridge
                prompt_pack_error = str(exc)
        merged = dict(case)
        if prompt_pack is not None:
            merged["prompt_pack"] = prompt_pack
        if prompt_pack_error:
            merged["prompt_pack_error"] = prompt_pack_error
        return merged

    def validate(self) -> List[str]:
        return bondclaw_assets.validate_all()

    def describe_shell_command(self, command: Union[str, Sequence[ShellArg]]) -> Dict[str, str]:
        return bondclaw_shell.describe_shell_command(command, mode=self.shell_mode)

    def run_shell_command(
        self,
        command: Union[str, Sequence[ShellArg]],
        *,
        cwd: Optional[ShellArg] = None,
        env: Optional[Dict[str, str]] = None,
        capture_output: bool = True,
        check: bool = True,
    ):
        return bondclaw_shell.run_shell_command(
            command,
            mode=self.shell_mode,
            cwd=cwd,
            env=env,
            capture_output=capture_output,
            check=check,
        )


def build_runtime(shell_mode: Optional[str] = None) -> BondClawRuntime:
    config = bondclaw_assets.load_execution_shell_config()
    config_mode = str(config.get("mode", "native"))
    mode = shell_mode or config_mode or bondclaw_shell.current_platform_mode()
    return BondClawRuntime(shell_mode=bondclaw_shell.normalize_shell_mode(mode))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="BondClaw unified runtime facade")
    parser.add_argument("--shell-mode", choices=["native"], help="Override execution mode")
    parser.add_argument("--summary", action="store_true", help="Print runtime summary")
    parser.add_argument("--catalog", action="store_true", help="Print full runtime catalog")
    parser.add_argument("--validate", action="store_true", help="Validate runtime assets")
    parser.add_argument("--providers", action="store_true", help="Print provider matrix")
    parser.add_argument("--roles", action="store_true", help="Print role summaries")
    parser.add_argument("--prompt-center-panel", action="store_true", help="Print the template center panel model")
    parser.add_argument("--prompt-role", help="Select a template center role")
    parser.add_argument("--prompt-name", help="Select a template center prompt")
    parser.add_argument("--research-brain", action="store_true", help="Print subscriptions and cases summary")
    parser.add_argument("--research-cases", action="store_true", help="Print subscriptions and case cards")
    parser.add_argument("--research-role", help="Filter subscription entries by role")
    parser.add_argument("--research-topic", help="Filter subscription entries by topic")
    parser.add_argument("--research-case-id", help="Print a single subscriptions-and-cases detail")
    parser.add_argument("--lead-capture", action="store_true", help="Print contact summary")
    parser.add_argument("--role", help="Print a role manifest")
    parser.add_argument("--prompt", help="Print a prompt pack (requires --role)")
    parser.add_argument("--command", nargs=argparse.REMAINDER, help="Describe a command")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    runtime = build_runtime(shell_mode=args.shell_mode)

    if args.validate:
        errors = runtime.validate()
        if errors:
            for error in errors:
                print(f"ERROR: {error}")
            return 1
        print("BondClaw runtime validation passed.")
        return 0

    if args.providers:
        print(json.dumps(runtime.provider_matrix(), ensure_ascii=False, indent=2))
        return 0

    if args.roles:
        print(json.dumps([summary.__dict__ for summary in bondclaw_assets.load_prompt_pack_summary()], ensure_ascii=False, indent=2))
        return 0

    if args.prompt_center_panel:
        print(json.dumps(runtime.prompt_center_panel(role=args.prompt_role, prompt_name=args.prompt_name), ensure_ascii=False, indent=2))
        return 0

    if args.research_brain:
        print(json.dumps(runtime.research_brain(), ensure_ascii=False, indent=2))
        return 0

    if args.research_cases:
        print(json.dumps(runtime.research_brain_cases(role=args.research_role, topic=args.research_topic), ensure_ascii=False, indent=2))
        return 0

    if args.research_case_id:
        print(json.dumps(runtime.research_brain_case_detail(args.research_case_id), ensure_ascii=False, indent=2))
        return 0

    if args.lead_capture:
        print(json.dumps(runtime.lead_capture(), ensure_ascii=False, indent=2))
        return 0

    if args.role and args.prompt:
        print(json.dumps(runtime.prompt_pack(args.role, args.prompt), ensure_ascii=False, indent=2))
        return 0

    if args.role:
        print(json.dumps(runtime.prompt_manifest(args.role), ensure_ascii=False, indent=2))
        return 0

    if args.prompt and not args.role:
        raise SystemExit("--prompt requires --role")

    if args.command:
        print(json.dumps(runtime.describe_shell_command(args.command), ensure_ascii=False, indent=2))
        return 0

    if args.catalog:
        print(json.dumps(runtime.catalog(), ensure_ascii=False, indent=2))
        return 0

    if args.summary:
        print(json.dumps(runtime.summary(), ensure_ascii=False, indent=2))
        return 0

    print("Use --summary, --catalog, --validate, --providers, --roles, --prompt-center-panel, --research-brain, --research-cases, --research-case-id, --lead-capture, --role, --prompt, or --command.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
