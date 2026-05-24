---
description: Commit all pending changes and push to GitHub to trigger automatic Railway/Vercel deploy
---

Review all staged and unstaged changes in the current git repository.

1. Run `git status` to see what changed
2. Run `git diff` to review the changes
3. Run `git log --oneline -5` to see recent commit style
4. Stage only the modified project files (never .env, credentials, or secrets)
5. Write a concise commit message following the project convention:
   - `feat:` for new features
   - `fix:` for bug fixes  
   - `refactor:` for refactoring
   - `chore:` for tooling/config
6. Commit with `Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>` trailer
7. Push to `origin main`
8. Confirm the push succeeded and report which services will auto-deploy (Vercel for frontend, Railway for backends)
