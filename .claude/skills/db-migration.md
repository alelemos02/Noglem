---
description: Generate and apply an Alembic migration for PATEC or Conhecimento microservice
---

Generate an Alembic migration for the specified microservice. Ask the user:
1. Which service: `patec-backend` or `conhecimento-backend`
2. What changed (describe the model change)

Then:

1. Navigate to `services/<service>/`
2. Verify the SQLAlchemy model change in `app/models/`
3. Run:
   ```bash
   cd services/<service>
   alembic revision --autogenerate -m "<description>"
   ```
4. Review the generated migration file in `alembic/versions/` — check for:
   - Correct `upgrade()` and `downgrade()` functions
   - No accidental drops of existing columns/tables
   - Proper handling of nullable fields and defaults
5. Apply the migration:
   ```bash
   alembic upgrade head
   ```
6. Confirm the migration applied successfully (`alembic current`)

**Rules:**
- Never modify the database directly — always via Alembic
- If changing embedding-related columns in `conhecimento-backend`, document the impact on already-indexed documents
- After migration, commit the new version file with `git commit` and push
