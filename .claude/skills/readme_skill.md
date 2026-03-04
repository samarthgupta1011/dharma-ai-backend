# Skill: README Governance

## Purpose
Keep `README.md` minimal, scannable, and always accurate. Every edit should be the smallest change that keeps the file correct.

## README Must Include (in this order)
1. **Project one-liner** — 2-3 sentences max, no philosophy essays
2. **Quick start** — clone → `docker-compose up` → seed → open docs (copy-pasteable)
3. **Health & Swagger URLs** — `GET /health`, Swagger at `/docs`, ReDoc at `/redoc`
4. **Database seeding** — the `docker-compose exec api python -m scripts.seed_data` command + what it inserts
5. **GitHub Actions pipeline** — brief: "push to `main` triggers build → ACR push → Container App deploy with health check". Link to `.github/workflows/deploy.yml` for details
6. **Environment variables table** — this is critical, see rules below
7. **Link to `docs/AZURE_DEPLOYMENT.md`** — for full Azure setup commands

## README Must NOT Include
- AI engine architecture diagrams or strategy pattern explanations
- OpenAI integration details (prompt templates, mock vs real service)
- Azure CLI commands (those go in `docs/AZURE_DEPLOYMENT.md`)
- Security model deep-dives (JWT internals, auth flow diagrams)
- Code snippets showing internal implementation (config loading, validators)
- Configuration architecture ASCII diagrams

## Environment Variables Table Rules
This table is the #1 source of production bugs when not updated. Follow these rules strictly:

- **Every** env var used by the app MUST appear in the table
- Table columns: `Variable` | `Where Set` | `Purpose` | `Manual AKV?`
- `Where Set` values: `.env` (local), `prod.env`, `AKV` (Azure Key Vault), `deploy-time` (set during `az containerapp` command)
- `Manual AKV?`: Yes = someone must manually `az keyvault secret set` this. No = auto-populated or not a secret
- When adding a new feature that introduces an env var, update this table in the **same PR**

## Editing Rules
1. **Minimal diffs** — edit only the section affected by the change. Do not rewrite unrelated sections
2. **No inflation** — if a feature needs more than 3 lines of explanation in README, it belongs in a separate doc under `docs/`
3. **No duplication** — if something is already in `docs/AZURE_DEPLOYMENT.md` or in a skill, don't repeat it in README
4. **Env var additions** — always ask: "Does this need manual AKV setup?" and mark it in the table
5. **Keep quick start working** — after any edit, mentally verify the quick-start steps still work end-to-end

## Touchpoints
When editing README, also check if `docs/AZURE_DEPLOYMENT.md` needs a corresponding update (e.g., new Azure resource, new AKV secret, new deploy step).
