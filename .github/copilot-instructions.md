# Copilot Workspace Instructions

## Read first

- [AGENTS.md](../AGENTS.md)
- [README.md](../README.md)
- [docs/README.md](../docs/README.md)
- [docs/quickstart.md](../docs/quickstart.md)
- [docs/architecture.md](../docs/architecture.md)
- [docs/contracts.md](../docs/contracts.md)
- [docs/troubleshooting.md](../docs/troubleshooting.md)

## Canonical sources

- [automation_blueprint.md](../automation_blueprint.md)
- [codex_execution_runbook.md](../codex_execution_runbook.md)
- [codex_review_and_finalization_runbook.md](../codex_review_and_finalization_runbook.md)
- [knowledge_adoption_delta_contract.md](../knowledge_adoption_delta_contract.md)
- [runtime_external_data_layer_spec.md](../runtime_external_data_layer_spec.md)
- [financial-analyzer/SKILL.md](../financial-analyzer/SKILL.md)
- [chinamoney/SKILL.md](../chinamoney/SKILL.md)
- [mineru/SKILL.md](../mineru/SKILL.md)

## Working rules

- Link to the source docs instead of duplicating long explanations here.
- Treat scaffold outputs as intermediates, not final outputs.
- Keep runtime data out of skill directories.
- Keep changes small and file-local unless the task clearly needs a broader update.
- If a change affects workflow, state, or contracts, update the canonical docs above first.

## Commands and validation

- Use the execution and validation guidance in [AGENTS.md](../AGENTS.md).
- Prefer the existing project runbooks and sample cases over inventing new ad hoc flows.

## Suggested follow-up prompts

- "请先读 README、AGENTS 和 docs，然后总结这个仓库的核心工作流和最容易踩坑的地方。"
- "如果我要改 financial-analyzer 的分析逻辑，先帮我定位应当阅读的 runbook 和契约文档。"
- "请按这个仓库的约定，帮我检查某次改动会不会碰到 scaffold、runtime 和正式产物边界。"

## Related next customizations

- `/create-instruction ...` for a frontend/backend-specific workspace note if you later split out UI or service code.
- `/create-prompt ...` for a reusable repo-onboarding prompt that points to AGENTS and the runbooks.
- `/create-hook ...` for an auto-reminder hook that enforces "read AGENTS first" before larger tasks.
