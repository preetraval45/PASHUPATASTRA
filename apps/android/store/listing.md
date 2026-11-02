# Google Play listing (RP-85)

Text to paste into the Play Console, and the answers for its forms. Every claim
is one the app keeps: check it against the code before changing it.

## App details

- **App name** (30 max): `Pashupatastra`
- **Short description** (80 max):
  `Incidents, live attacks and Sati AI: security answers with their sources.`
- **Category:** Tools. **Tags:** Security, Productivity.
- **Contact email:** the owner's choice (required; not published here).
- **Privacy policy URL:** https://pashupatastra.vercel.app/privacy

## Full description (4000 max)

```
Four alerts in four tools are often one intrusion. Pashupatastra assembles scattered security signals into a single incident with its causal chain, maps each step to a known technique, and scores a response before anyone runs it. Nothing consequential runs without a person's approval.

IN THE APP
• Home: what is open, what needs your approval, what is critical, at a glance.
• Incidents: filter by severity or state, and open an incident to see how it unfolded and what is proposed.
• Sati AI: ask Sati, the investigation agent, about an attack, a technique, a defence or a CVE. Nine specialist models answer, and every claim links to its source. Sati can propose, never act.
• Live attacks: what public feeds reported in the last hours (exploited vulnerabilities, ransomware, botnet servers, malware addresses), each linked to the source's own record.
• Training: nine levels and hands-on labs (spot a phish, read a log, name the technique), with your progress kept on your phone.
• Alerts: a notification when an incident awaits approval or a critical one opens, and a home-screen widget with the counts.
• Your company: sign in to keep your training record, read and acknowledge your company's security policies, and see the levels it requires. Owners and admins see their team's progress.
• App lock: optionally lock the app with your fingerprint, face or screen lock.

PRIVATE BY DESIGN
Accounts are optional, and there are no ads and no tracking. The app asks for no location, contacts, camera or microphone. Questions to Sati AI are kept anonymously in a public audit trail, so every answer can be explained, which is why you should leave personal details out of them.

The public deployment runs in dry-run mode: approvals describe what would change, and nothing executes.
```

## Data safety form

Accounts are optional (RP-101); everything public works without one. Matches `/privacy`,
which is checked against `services/api/app/accounts.py`.

| Question | Answer | Why |
|---|---|---|
| Does the app collect or share user data? | **Yes, collects; does not share** | Optional accounts, and questions to Sati AI. |
| **Personal info → Name** | Collected, **optional**, linked to the account | The name typed at sign-up. |
| **Personal info → Email address** | Collected, **optional**, linked | Email accounts only; guests give none. |
| **App activity → Other user-generated content** | Collected, **optional** | Questions to Sati AI (not linked to identity: the audit trail never records who asked); company policies an admin writes, and members' acknowledgements (linked). |
| **App activity → Other actions** | Collected, **optional**, linked | Training results (scores, attempts, passed) for a signed-in account. |
| **App info and performance** | **Not collected** | No crash reporting or analytics SDK. |
| Purpose | **App functionality**, **Account management** | Sign-in, training records, company workspaces. |
| Shared with third parties? | **No** | A company's owner and admins see their own members' name, email and training; that is the user joining that company, not sharing with a third party. |
| Encrypted in transit? | **Yes** | HTTPS only (`usesCleartextTraffic=false`). |
| Can users request deletion? | **Yes** | Account → Delete account erases the account, sign-in, memberships and training at once (`DELETE /me`). Questions in the audit trail cannot be deleted, and nothing identifies who asked them. |
| Passwords | Never stored; a one-way scrypt hash. | |
| Account deletion URL (Play requires one for apps with accounts) | https://pashupatastra.vercel.app/account | Signed in, "Delete account". |

Location, contacts, photos, files, health, financial info and device ids: **not collected**.
The app keeps its own preferences and the sign-in token in its private storage on the phone.

## Content rating questionnaire

Category **Utility, Productivity, Communication or Other**. No violence, sexual content, profanity, drugs, gambling or user-to-user communication. The app shares no location and has no purchases. Users' questions go to an AI that answers them; they are not shown to other users, apart from the public audit trail on the website.

## Target audience

**18+.** It is a professional security tool; choosing adult audiences avoids the Families policy.

## Graphics

- **App icon 512×512:** `apps/android/store/icon-512.png` (`scripts/buildbrand.py`).
- **Feature graphic 1024×500:** `apps/android/store/feature-graphic.png` (`scripts/buildbrand.py`): the site's lockup and tagline on the dark ground.
- **Phone screenshots (2–8):** taken by CI on an emulator on every build, attached to the `android` release as `shot-*.png` (`apps/android/screens.sh`).

## What only the owner can do

1. Create the Play Console developer account ($25 once) and verify identity.
2. Make the upload key, and add it as repository secrets: `UPLOAD_KEYSTORE_BASE64` (the .jks, base64), `UPLOAD_STORE_PASSWORD`, `UPLOAD_KEY_ALIAS`, `UPLOAD_KEY_PASSWORD`. CI then builds a signed `.aab` (artifact `Pashupatastra-play-bundle`).
   ```
   keytool -genkeypair -v -keystore upload.jks -alias upload -keyalg RSA -keysize 2048 -validity 10000
   base64 -w0 upload.jks   # paste as UPLOAD_KEYSTORE_BASE64
   ```
   Keep `upload.jks` and its passwords somewhere safe and off GitHub.
3. New personal accounts: run a closed test with 12 testers for 14 days before production.
4. Upload the .aab, paste this listing, and submit the forms.
