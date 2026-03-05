# PUBLIC_RELEASE_CHECKLIST

Generated: 2026-03-05
Repository: atlas-public

## 1. Secret and sensitive pattern scans

Command (broad keyword scan):

```bash
grep -rn "password\|secret\|api_key\|token\|/h[o]me/" \
  --include="*.py" --include="*.js" --include="*.md" \
  --include="*.yml" --include="*.yaml" --include="*.json" .
```

Result: matches exist (expected for variable names/docs/workflows).

Command (high-risk credential patterns):

```bash
rg -n 'AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z-_]{35}|ghp_[0-9A-Za-z]{36}|-----BEGIN (RSA|OPENSSH|EC|DSA) PRIVATE KEY-----|xox[baprs]-' .
```

Result: `0` high-risk credential hits.
Status: PASS

## 2. Absolute personal path scan (tracked files)

Command:

```bash
git grep -n '/h[o]me/\|/U[s]ers/\|C:\\\\Users'
```

Result: `0` matches in tracked files.
Status: PASS

## 3. Large file scan (working tree)

Command:

```bash
find . -type f -size +10M -not -path "./.git/*"
```

Result: `0` files >10MB.
Status: PASS

## 4. Large tracked file scan (git index)

Command:

```bash
python3 - <<'PY'
import os, subprocess
paths = subprocess.check_output(['git', 'ls-files'], text=True).splitlines()
large = [p for p in paths if os.path.exists(p) and os.path.getsize(p) > 10 * 1024 * 1024]
print(len(large))
for p in large[:20]:
    print(p)
PY
```

Result: `0` tracked files >10MB.
Status: PASS

## 5. License check

- `LICENSE` present.
- License type: MIT.
Status: PASS

## 6. Citation metadata check

Command:

```bash
ruby -ryaml -e "YAML.load_file('CITATION.cff'); puts 'CITATION_OK'"
```

Result: `CITATION_OK`.
Status: PASS

## 7. README/metadata placeholder check

Intentional placeholders remain for:

- Zenodo DOI badge/link
- GitHub org/repo URL
- Author metadata in `CITATION.cff`

Status: PASS (expected until final publish metadata is known)

## 8. Data policy check

- No large runtime datasets committed.
- Registry metadata committed under `data/registries/`.
- Sample data committed under `data/sample/`.
Status: PASS

## 9. Smoke validation summary

- `python data/download.py --sample-only`: PASS (uses local bundled sample until Zenodo config is filled).
- API smoke tests (subset): PASS
  - `tests/test_map_router_year_bounds.py`
  - `tests/test_qol_response_contract.py`
  - `tests/test_simulation_invariants.py`
- Frontend build (`npm run build`): PASS

Note: full API integration/e2e suites require full runtime artifacts and/or a running local API server.

## Final status

Blocking failures: `0`

Repository is public-release ready pending final metadata fill-in:

1. Replace Zenodo DOI placeholders.
2. Replace GitHub org/repo placeholders.
3. Final manual read-through of docs/research content.
