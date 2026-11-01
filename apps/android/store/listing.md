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

PRIVATE BY DESIGN
No account, no ads, no tracking. The app asks for no location, contacts, camera or microphone. Questions to Sati AI are kept anonymously in a public audit trail, so every answer can be explained, which is why you should leave personal details out of them.

The public deployment runs in dry-run mode: approvals describe what would change, and nothing executes.
```

## Data safety form

| Question | Answer | Why |
|---|---|---|
| Does the app collect or share user data? | **Yes, collects** | Questions typed into Sati AI are stored. |
| Data types collected | **App activity → Other user-generated content** (questions to Sati AI) | `services/api` `routes._asked`, the audit trail. |
| Collected data is | **Not shared**; **processed ephemerally: no**; **required: no** (the user chooses to ask) | It is kept in the audit trail. |
| Purpose | **App functionality** | It lets any answer be explained later. |
| Linked to the user's identity? | **No** | No account, IP or device id is stored with it. |
| Encrypted in transit? | **Yes** | HTTPS only (`usesCleartextTraffic=false`). |
| Can users request deletion? | **No** | The trail is append-only and nothing identifies who asked; say so in the form's explanation. |
| Page counts | Not "user data": a daily count per path with no identifier. | `routes.record_view` |

Location, contacts, photos, files, health, financial info, device ids, crash logs: **not collected**.

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
