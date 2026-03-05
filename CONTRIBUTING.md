# Contributing to Atlas

Thanks for contributing to Atlas. This repository supports research-grade causal discovery and simulation workflows, so reproducibility and evidentiary rigor are mandatory.

## 1. Reporting Bugs

Use `.github/ISSUE_TEMPLATE/bug_report.md` and include:

- exact steps to reproduce
- expected vs actual behavior
- environment details (OS, Python, Node versions)
- relevant logs/tracebacks

## 2. Requesting Features

Use `.github/ISSUE_TEMPLATE/feature_request.md` with a clear use case and proposed behavior.

## 3. Research Questions

Use `.github/ISSUE_TEMPLATE/research_question.md` for findings/methodology questions. Include the finding ID or section reference, your research context, and what you already checked.

## 4. Pull Requests

- Fork and create a branch from `main`.
- Keep changes scoped and documented.
- Add tests for behavior changes.
- Update docs for any interface or contract change.
- Ensure CI passes.

## 5. Code Style

- Python: follow PEP 8 and keep types/docstrings for public interfaces.
- TypeScript/React: follow existing lint rules and component patterns.
- Avoid introducing absolute local paths or private infrastructure details.

## 6. Research Integrity Rules

For contributions affecting published findings, registries, or reproducibility:

- claim-level evidence links must be preserved
- uncertainty and caveat language must not be weakened without evidence
- changes should include reproducibility impact notes

Maintainers may request additional review for finding-affecting changes.
