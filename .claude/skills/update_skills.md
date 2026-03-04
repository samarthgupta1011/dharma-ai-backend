# Skill: Keeping Skills Up to Date

## Purpose
After making changes to the project, check if any skills need updating. Skills are only useful if they reflect the current state of the codebase.

## When to Update Each Skill

### `schema_skill.md`
Update when:
- A field is added, removed, or renamed on any model (`ingredients.py`, `user.py`, `panchang.py`)
- A new `ActivityType` is added or removed
- A new model/collection is introduced
- Field types or defaults change

### `azure_skill.md`
Update when:
- A new Azure resource is created (storage account, Key Vault, etc.)
- A new AKV secret is added
- RBAC roles change
- CI/CD pipeline steps change (`.github/workflows/deploy.yml`)
- A new env var is introduced or an existing one is removed
- Architecture patterns change (new service strategy, new dependency pattern)
- Key files are added or significantly restructured

### `readme_skill.md`
Update when:
- The README structure needs to change (new required section, section removed)
- New rules about what should/shouldn't be in README emerge from experience
- Env var governance rules change

## Rule
When completing a task, ask: "Did this change affect any model, Azure resource, env var, or architecture pattern?" If yes, update the relevant skill in the **same change set** — not as a follow-up.
