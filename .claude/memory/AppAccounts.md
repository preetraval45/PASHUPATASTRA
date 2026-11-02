# Accounts in the native app

- **Date:** 2026-11-02
- **Phase:** Product (RP-96 with RP-101..106)
- **Commit(s):** pending

## What changed

`Session.kt` mirrors the site's session token (`localStorage['pashu.session']`, apps/web/lib/account.ts) into the app's prefs. `MainActivity.syncFromPage` reads it with the theme after every page load; when it changes, Home reloads. Home shows the name and a company card (required levels passed, policies unacknowledged) from `/me` and `/orgs/{id}/policies`. More opens with the account and a Workspace section chosen by role. `listing.md` Data safety now declares the account data.

## Decisions made

- **Sign-in stays on the site's pages** (/login, /signup, /account) rather than native forms. One implementation of passwords, lockout and reset; the app only reads the result.
- **A 401 from `/me` forgets the token natively;** the page's next load is the truth either way.
- **The token sits in app-private prefs,** as it does in browser localStorage. If an encrypted store is wanted later, swap `Session.set`/`token`.

## Next session should

- If the web changes the storage key or the `/me` shape, `Session.kt` must follow.
