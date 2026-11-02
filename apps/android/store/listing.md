# Google Play listing (RP-85)

Text to paste into the Play Console, and the answers for its forms. Every claim
is one the app keeps: check it against the code before changing it.

## App details

- **App name** (30 max): `Pashupatastra`
- **Short description** (80 max):
  `Incidents, live attacks and Sati AI: security answers with their sources.`
- **Category:** Tools. **Tags:** Security, Productivity.
- **Contact email:** preetraval45@gmail.com (owner, 2 Nov 2026; also the in-app Contact support address).
- **Privacy policy URL:** https://pashupatastra.vercel.app/privacy

## Distribution (owner, 2 Nov 2026: "ready for USA and India, publish for now")

- **Countries:** United States and India only (Play Console › Production › Countries/regions). Add others later.
- **Default language:** English (United States), `en-US`.
- **Translated listings:** Hindi (`hi-IN`) and Spanish (United States, `es-US`), below. The app itself is in
  English, Hindi and Spanish (values, values-hi, values-es), and follows the phone's language or the per-app
  language in Android 13+ settings. Sati's answers and the site's pages stay English: their sources are English.
- **Price:** free. No ads, no in-app purchases.
- **India:** data is stored in the United States (AWS us-east-1); `/privacy` says so, names the grievance
  contact (preetraval45@gmail.com) and that the product is not directed at anyone under 18 (DPDP Act 2023).
- **United States:** nothing is sold or shared; access, correction and deletion are on the Account page (`/privacy`, "Your rights").

## Full description (4000 max)

```
Four alerts in four tools are often one intrusion. Pashupatastra assembles scattered security signals into a single incident with its causal chain, maps each step to a known technique, and scores a response before anyone runs it. Nothing consequential runs without a person's approval.

Its incidents are built from live public sources: vulnerabilities CISA lists as exploited, critical new CVEs, malware command-and-control activity, ransomware campaigns and published breaches. Each one cites the records it rests on.

IN THE APP
• Home: what is open, what needs your approval, what is critical, at a glance.
• Incidents: filter by severity or state, and open an incident to see how it unfolded and what is proposed.
• Sati AI: ask Sati, the investigation agent, about an attack, a technique, a defence or a CVE. Nine specialist models answer, and every claim links to its source. Sati can propose, never act.
• Live attacks: what public feeds reported in the last hours (exploited vulnerabilities, ransomware, botnet servers, malware addresses), each linked to the source's own record.
• Training: nine levels and hands-on labs (spot a phish, read a log, name the technique), with your progress kept on your phone.
• Alerts: a notification when an incident awaits approval or a critical one opens, and a home-screen widget with the counts.
• Your company: sign in to keep your training record, read and acknowledge your company's security policies, and see the levels it requires. Owners and admins see their team's progress, and can connect their own systems so their alerts arrive in the workspace.
• App lock: optionally lock the app with your fingerprint, face or screen lock.
• In English, Hindi and Spanish. Sati's answers are in English.

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

## Hindi listing (hi-IN)

- **Short description:** `घटनाएँ, लाइव हमले और Sati AI: स्रोतों के साथ साइबर सुरक्षा जवाब।`

```
चार टूल में चार अलर्ट अक्सर एक ही घुसपैठ होते हैं। Pashupatastra बिखरे सुरक्षा संकेतों को उनकी कारण-शृंखला के साथ एक घटना में जोड़ता है, हर कदम को किसी ज्ञात तकनीक से जोड़ता है, और किसी के कुछ चलाने से पहले जवाब का आकलन करता है। किसी व्यक्ति की मंज़ूरी के बिना कोई महत्वपूर्ण कार्रवाई नहीं होती।

इसकी घटनाएँ लाइव सार्वजनिक स्रोतों से बनती हैं: CISA की शोषित कमज़ोरियाँ, नए गंभीर CVE, मैलवेयर गतिविधि, रैनसमवेयर अभियान और सार्वजनिक डेटा उल्लंघन। हर घटना अपने रिकॉर्ड का हवाला देती है।

ऐप में
• होम: क्या खुला है, किसे आपकी मंज़ूरी चाहिए, क्या गंभीर है, एक नज़र में।
• घटनाएँ: गंभीरता या स्थिति से फ़िल्टर करें, और देखें कि घटना कैसे घटी और क्या प्रस्तावित है।
• Sati AI: Sati, जाँच एजेंट, से किसी हमले, तकनीक, बचाव या CVE के बारे में पूछें। नौ विशेषज्ञ मॉडल जवाब देते हैं, और हर दावा अपने स्रोत से जुड़ा होता है। Sati सुझाव दे सकता है, कभी कार्रवाई नहीं करता। जवाब अंग्रेज़ी में आते हैं।
• लाइव हमले: पिछले कुछ घंटों में सार्वजनिक फ़ीड ने क्या बताया, हर रिपोर्ट अपने मूल रिकॉर्ड से जुड़ी।
• प्रशिक्षण: नौ स्तर और व्यावहारिक लैब, आपकी प्रगति के साथ।
• अलर्ट: जब किसी घटना को आपकी मंज़ूरी चाहिए या कोई गंभीर घटना शुरू हो, सूचना; और होम-स्क्रीन विजेट।
• आपकी कंपनी: अपना प्रशिक्षण रिकॉर्ड रखें, कंपनी की सुरक्षा नीतियाँ पढ़ें और स्वीकार करें। मालिक और एडमिन अपनी टीम की प्रगति देखते हैं और अपने सिस्टम जोड़ सकते हैं।
• ऐप लॉक: फ़िंगरप्रिंट, चेहरे या स्क्रीन लॉक से।
• अंग्रेज़ी, हिंदी और स्पेनिश में।

निजता
खाते वैकल्पिक हैं; कोई विज्ञापन नहीं, कोई ट्रैकिंग नहीं। ऐप स्थान, संपर्क, कैमरा या माइक्रोफ़ोन नहीं माँगता। Sati AI से पूछे गए सवाल बिना पहचान के एक सार्वजनिक ऑडिट ट्रेल में रखे जाते हैं, इसलिए उनमें निजी जानकारी न लिखें। डेटा अमेरिका में रखा जाता है।
```

## Spanish listing (es-US)

- **Short description:** `Incidentes, ataques en vivo y Sati AI: respuestas de seguridad con sus fuentes.`

```
Cuatro alertas en cuatro herramientas suelen ser una sola intrusión. Pashupatastra reúne señales de seguridad dispersas en un solo incidente con su cadena causal, relaciona cada paso con una técnica conocida y evalúa la respuesta antes de que nadie la ejecute. Nada importante se ejecuta sin la aprobación de una persona.

Sus incidentes se construyen a partir de fuentes públicas en vivo: vulnerabilidades que CISA cataloga como explotadas, CVE críticas nuevas, actividad de malware, campañas de ransomware y filtraciones publicadas. Cada uno cita los registros en los que se basa.

EN LA APP
• Inicio: lo abierto, lo que necesita tu aprobación y lo crítico, de un vistazo.
• Incidentes: filtra por gravedad o estado, y abre un incidente para ver cómo ocurrió y qué se propone.
• Sati AI: pregúntale a Sati, el agente de investigación, sobre un ataque, una técnica, una defensa o una CVE. Nueve modelos especialistas responden y cada afirmación enlaza a su fuente. Sati puede proponer, nunca actuar. Las respuestas están en inglés.
• Ataques en vivo: lo que informaron las fuentes públicas en las últimas horas, cada informe enlazado a su registro original.
• Capacitación: nueve niveles y laboratorios prácticos, con tu progreso.
• Alertas: un aviso cuando un incidente espera tu aprobación o se abre uno crítico, y un widget para la pantalla de inicio.
• Tu empresa: guarda tu capacitación, lee y acepta las políticas de seguridad de tu empresa. Propietarios y administradores ven el progreso de su equipo y pueden conectar sus propios sistemas.
• Bloqueo de la app: con tu huella, tu rostro o el bloqueo de pantalla.
• En inglés, hindi y español.

PRIVACIDAD
Las cuentas son opcionales; sin anuncios ni seguimiento. La app no pide ubicación, contactos, cámara ni micrófono. Las preguntas a Sati AI se guardan de forma anónima en un registro de auditoría público, así que no incluyas datos personales. Los datos se guardan en Estados Unidos.
```

