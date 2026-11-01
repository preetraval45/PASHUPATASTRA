# Accounts, companies, team dashboard

- **Date:** 2026-11-01
- **Phase:** Phase 0 — Foundation (product)
- **Commit(s):** pending

## What changed

- **Optional accounts:** guest, email and Google sign-in, implemented in `services/api/app/accounts.py` with routes in `api/accountroutes.py`.
- **Company workspaces:** roles, invite codes and a team dashboard at `/team/[id]`.
- **Account page:** `/account`, plus a sign-in page at `/signin`.
- **Training sync:** progress is saved to the account and merged with the browser's copy (`components/course.tsx` `merge()`).

## Why

The owner wants to sell the product as a service, with companies tracking their employees' training. Their constraints:
- no domain yet, so no Apple sign-in;
- Sati's own AI only;
- no payments yet; the Play Store fee waits.

## Decisions made

- **No new dependencies:**
  - passwords use `hashlib.scrypt`;
  - sessions use HMAC tokens, with the key in `PASHU_AUTH_SECRET` or created once and kept in the store at `META/AUTHKEY`;
  - Google ID tokens are verified through Google's tokeninfo endpoint, so only the public client ID is needed.
- **Storage:** generic document methods (`get_doc`, `put_doc`, `delete_doc`, `docs`) on `DynamoStore`, with an in-memory fallback. Postgres has none yet.
- **Audit:** records say what happened, never who, because `/audit` is public.
- **CORS:** API Gateway answers preflight itself. CI now runs `deployapigateway.py`, which only warns on failure, to allow the `Authorization` header and PUT/PATCH/DELETE. If sign-in fails from the site, check this first.
- **Git hygiene:** another session leaves uncommitted edits, such as `chatconsole.tsx`'s privacy line. Stage only your own paths.

## Next session should

- **After deploy:** preflight check that `OPTIONS` on `/api/v1/me` with `Access-Control-Request-Headers: authorization` returns the header. Then register on the live site.
- **When the owner sets `vars.GOOGLE_CLIENT_ID`:** confirm `/auth/config` returns it, and that the Google button shows.

## Cross-session hazard (1 Nov)

`git rm` stages the deletion immediately. The Android session committed its own work while that deletion was staged, so 5e357ec removed `components/signin.tsx` while `/signin` still imported it, and Vercel failed. 4d94b6e repaired it.

**Rule:** don't leave anything staged between commands. Run `git rm` or `git add` only in the same command as `git commit`. Otherwise use plain `rm` and stage it at commit time.
