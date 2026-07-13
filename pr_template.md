[comment]: # (Title: short imperative summary of what the branch adds/fixes, max 72 chars)

Branch: `branch-name-here`

_2–3 sentences describing what this PR achieves and why._

## Type of change
[Keep only the one that applies, remove the rest]
- [ ] New feature
- [ ] Bug fix
- [ ] Refactor or chore
- [ ] Breaking change

## Breaking changes
[None if nothing applies — otherwise fill each that applies]
**Entity additions/removals/renames**: note any entity key changes; existing unique_ids in HA's entity registry are a permanent contract — migrations must be in `async_setup_entry`
**Storage format (`_save_persistent_state`)**: new fields must have defaults so old stored data loads cleanly; removed fields are silent on load
**Config entry options**: removed keys must be dropped from `OPTION_KEYS` and the options flow

## Checklist
- [ ] Self-review done
- [ ] All modified `.py` files pass `python3 -m py_compile`
- [ ] All modified `.json` files are valid JSON
- [ ] Entity registry migrations added for any renamed or removed entities
- [ ] Translation strings added for every new entity key
- [ ] No credentials, tokens, secrets, or house-specific paths in the diff
- [ ] `workarea/`, `reference-original/`, `CLAUDE.md` not staged
