# Play Store readiness: privacy, AAB, emulator screenshots

- **Date:** 2026-11-01
- **Phase:** Product (RP-85)
- **Commit(s):** pending

## What changed

- `/privacy` (the site and the app). The Sati AI composer notes that questions are public.
- The upload-key signing config (`-Pplay`) and a CI step that runs only when the secrets exist.
- A `screens` CI job: emulator, `apps/android/screens.sh`, and screenshots uploaded to the `android` release.
- `apps/android/store/listing.md`.

## Why

The owner wants a Play Store launch and their own models only (no Claude). Play needs a privacy policy, a Data safety form, screenshots and an AAB signed with a private upload key.

## Decisions made

- **Data safety says "collects user-generated content, not linked to identity, not deletable"** because `routes._asked` keeps questions in the append-only public trail. If accounts are ever added, both `/privacy` and the form must change first.
- **Screenshots go to the public release** because artifacts need auth to download and `gh` is not logged in here. Public release assets can be fetched and viewed directly.
- **Target audience is 18+,** to stay out of the Families policy.
- **I did not generate the upload key:** the owner must hold it. A key made in this session would pass through it.

## Next session should

- Fetch `shot-*.png` from the release (https://github.com/preetraval45/PASHUPATASTRA/releases/download/android/shot-2-home.png …) and read them to check the UI. Fix what looks wrong.
- Make the feature graphic.
