# Decisions

- Canonical AI lifecycle and review semantics are inherited from `syllik/ai-workflow`; this repository owns only product-specific invariants.
- Existing repository `AGENTS.md` remains authoritative for YouTube localization behavior and documentation rules.
- The managed routing block is generated workflow infrastructure and must not replace repository-specific instructions.
- Agent workflow roles and authority are vendor-neutral and inherited from `syllik/ai-workflow`. Optional Codex CLI localization is a product feature, not a hard-coded Executor/Reviewer assignment; do not change its authentication, generation, validation, preview or publishing behavior as part of governance wording changes.
