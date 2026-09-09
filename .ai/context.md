# YouTube metadata translator context

- Repository: `syllik/youtube-metadata-translator`.
- Purpose: local Streamlit tooling for safe YouTube title/description localization management.
- Integration branch: `main`.
- Repository-specific product and workflow invariants live in `AGENTS.md` and current `docs/`.
- Canonical AI lifecycle, publication, reviewer roles, and Luna executor boundaries belong to `syllik/ai-workflow`.
- The application has one primary Translate workflow plus the supporting LLM Translation prompt page.
- The checked-in metadata-language snapshot is the only valid localization language-code source.
- Preview is read-only; Publish and Reset languages retain their repository-defined safety checks.
- Credentials, OAuth files, tokens, and provider secrets must never be committed.
- Use repository documentation to determine current validation commands for a task.
