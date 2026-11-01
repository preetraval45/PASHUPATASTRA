/**
 * Content for the training games (components/games.tsx), kept as data so a
 * test can check it (games.test.ts): every round has an explanation, every
 * answer is one of its options, no pair repeats.
 *
 * Every suspicious address uses the reserved `.example` domain (RFC 2606), so
 * no game puts a live-looking malicious link on a public page. The organisation
 * in the scenarios is "Northwind" at northwind.example.
 */

export type PhishRound = {
  channel: "Email" | "Text message" | "Push notification" | "Calendar invite";
  from: string;
  subject?: string;
  body: string;
  phish: boolean;
  why: string;
};

export const PHISH_OR_LEGIT: PhishRound[] = [
  {
    channel: "Text message",
    from: "+1 (555) 0143",
    body: "USPS: your parcel is held at the depot. Pay the $1.99 redelivery fee within 24 h: usps-redelivery.example/pay",
    phish: true,
    why: "A small fee, a deadline and a link that is not the carrier's own domain. Carriers do not text you to pay redelivery fees; check tracking on the carrier's site instead.",
  },
  {
    channel: "Email",
    from: "it@northwind.example",
    subject: "Planned maintenance on Saturday",
    body: "The VPN will be unavailable on Saturday from 22:00 to 23:00 for maintenance. No action is needed.",
    phish: false,
    why: "Your own organisation's domain, no link, nothing to enter, no urgency and nothing asked of you. Messages that ask for nothing are rarely phishing.",
  },
  {
    channel: "Email",
    from: "ceo.northwind@mail.example",
    subject: "Quick favour",
    body: "Are you at your desk? I need you to buy six gift cards for a client today. Keep this between us, I'm in meetings all day.",
    phish: true,
    why: "Business email compromise: an executive's name on an outside address, gift cards, secrecy and urgency. Check by calling the person on a number you already know.",
  },
  {
    channel: "Email",
    from: "payroll@northwind.example",
    subject: "October payslip available",
    body: "Your October payslip is in the HR portal. Sign in the usual way from your bookmarks.",
    phish: false,
    why: "Internal sender, no link, and it tells you to go the usual way rather than through the message. That is how a legitimate notice reads.",
  },
  {
    channel: "Email",
    from: "Microsoft 365 <no-reply@m365-alerts.example>",
    subject: "Your password expires today",
    body: "Your password expires in 2 hours. Keep your current password here: m365-verify.example/keep",
    phish: true,
    why: "A brand name on a look-alike domain, a countdown and a sign-in link. Password changes are made from the real portal you already use, never from an emailed link.",
  },
  {
    channel: "Push notification",
    from: "Authenticator app, 03:12",
    body: "Approve sign-in to Northwind? Location: unknown.",
    phish: true,
    why: "MFA fatigue: a sign-in you did not start, in the middle of the night. Someone has your password. Deny it, then report it and change the password.",
  },
  {
    channel: "Email",
    from: "billing@acme-supplies.example",
    subject: "Updated bank details for invoice 4471",
    body: "Please note our new bank account for all future payments, starting with invoice 4471.",
    phish: true,
    why: "A change of bank details is the classic invoice fraud, even from the supplier's real domain, which may be compromised. Confirm by phone using a number from your records, not from the email.",
  },
  {
    channel: "Calendar invite",
    from: "dana@northwind.example",
    subject: "Team retro, Thursday 15:00",
    body: "Retro for the release. The meeting link is in the invite as usual.",
    phish: false,
    why: "A colleague, an expected meeting, nothing to download or sign in to. Ordinary work traffic.",
  },
  {
    channel: "Email",
    from: "docs@share-files.example",
    subject: "Q4 bonus figures",
    body: "A file has been shared with you: Q4_bonus.xlsx.html",
    phish: true,
    why: "A tempting subject and a double extension: .xlsx.html is a web page dressed as a spreadsheet, usually a fake sign-in form. Real shares come from your own document system.",
  },
  {
    channel: "Text message",
    from: "Northwind Bank",
    body: "Your new statement is ready in the app. We will never ask for your PIN or passcode.",
    phish: false,
    why: "No link and nothing to give: it points you to the app you already have. Banks do send notices like this.",
  },
];

export type UrlRound = { url: string; options: string[]; answer: number; why: string };

export const URL_DETECTIVE: UrlRound[] = [
  {
    url: "https://paypal.com.account-verify.example/login",
    options: ["paypal.com", "account-verify.example", "login"],
    answer: 1,
    why: "The domain is read right to left from the first single slash: …account-verify.example. Everything before it, including paypal.com, is just a subdomain the attacker chose.",
  },
  {
    url: "https://login.microsoftonline.com/common/oauth2",
    options: ["microsoftonline.com", "login.com", "common"],
    answer: 0,
    why: "login is a subdomain of microsoftonline.com, Microsoft's real sign-in domain. The path after the slash does not change where you are.",
  },
  {
    url: "https://www.google.com@evil-login.example/",
    options: ["google.com", "evil-login.example", "www.google.com"],
    answer: 1,
    why: "Text before an @ in a web address is a user name, and the browser ignores it. The site is evil-login.example.",
  },
  {
    url: "https://northwind.example.secure-sso.example/auth",
    options: ["northwind.example", "secure-sso.example", "auth"],
    answer: 1,
    why: "Your company's name at the start is a subdomain. The registered domain is the last part before the path: secure-sso.example.",
  },
  {
    url: "https://docs.google.com/forms/d/e/1FAIpQL/viewform",
    options: ["google.com, and the form inside it was made by Google", "google.com, but anyone can make a form there", "forms.com"],
    answer: 1,
    why: "The domain is genuinely Google's, but anyone can build a form on it. A form asking for your work password is phishing wherever it is hosted.",
  },
  {
    url: "https://bit.ly/3Kx9qZt",
    options: ["bit.ly, and it is safe", "Unknown: a shortener hides the destination", "3Kx9qZt.com"],
    answer: 1,
    why: "A link shortener only redirects. You cannot tell where it goes until you expand it with a preview service, so treat it as unknown.",
  },
];

export type PasswordDuel = { a: string; b: string; stronger: "a" | "b"; why: string };

export const PASSWORD_DUELS: PasswordDuel[] = [
  {
    a: "P@ssw0rd!",
    b: "orbit pencil velvet drum",
    stronger: "b",
    why: "Swapping letters for symbols is the first trick cracking tools try. Four random words are far longer and are not in any list of common passwords.",
  },
  {
    a: "dragon",
    b: "dragon-lamp-river-oak",
    stronger: "b",
    why: "Length matters most. One common word falls in seconds; four random words take a guesser vastly longer.",
  },
  {
    a: "123456789012",
    b: "k9#vQ2!mZ",
    stronger: "b",
    why: "A digit run is among the first patterns any guesser tries, however long. Nine random characters from a large set are not.",
  },
  {
    a: "John1985",
    b: "j8$Rw!t2Qp",
    stronger: "b",
    why: "A name and a birth year are easy to guess and often public. Random characters are not tied to anything about you.",
  },
  {
    a: "One strong password used on every site",
    b: "A different password for every site, kept in a password manager",
    stronger: "b",
    why: "Reuse turns one breach into many: attackers try leaked passwords everywhere (credential stuffing). Unique passwords contain the damage.",
  },
  {
    a: "Summer2025!",
    b: "a password manager's 20 random characters",
    stronger: "b",
    why: "Season plus year plus ! is one of the most guessed patterns. Generated passwords have no pattern to guess.",
  },
];

export type MatchPair = { term: string; meaning: string };

export const MATCH_PAIRS: MatchPair[] = [
  { term: "Phishing", meaning: "A fake message that tricks you into giving access" },
  { term: "Ransomware", meaning: "Encrypts files and demands payment" },
  { term: "MFA", meaning: "A second proof of identity besides the password" },
  { term: "Patch", meaning: "A fix for a known software flaw" },
  { term: "Firewall", meaning: "Filters network traffic by rules" },
  { term: "Zero-day", meaning: "A flaw with no fix available yet" },
  { term: "Botnet", meaning: "Many infected devices run by one controller" },
  { term: "Social engineering", meaning: "Manipulating people rather than systems" },
  { term: "Backup", meaning: "A copy kept so data can be restored" },
  { term: "Least privilege", meaning: "Only the access a job actually needs" },
];

/** A shuffled copy, seeded so a round is the same on server and client. */
export function shuffled<T>(items: readonly T[], seed: number): T[] {
  const out = [...items];
  let s = seed >>> 0 || 1;
  for (let i = out.length - 1; i > 0; i--) {
    s = Math.imul(s ^ (s >>> 15), 2246822519) >>> 0;
    s = (s ^ (s >>> 13)) >>> 0;
    const j = s % (i + 1);
    [out[i], out[j]] = [out[j], out[i]];
  }
  return out;
}
