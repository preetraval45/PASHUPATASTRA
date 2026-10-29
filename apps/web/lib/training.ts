/**
 * The cyber defence course behind /training.
 *
 * Every module teaches one skill a defender uses in real life, then tests it.
 * Content rules, the same as the rest of the site: facts are stated the way
 * the source states them (NIST SP 800-61, MITRE ATT&CK, CISA), technique ids
 * are real ids, and every quiz answer comes with the reason it is right — a
 * test that only says "wrong" teaches nothing.
 */

export type Question = {
  q: string;
  options: string[];
  answer: number;
  why: string;
};

export type Lesson = { heading: string; body: string[] };

export type Module = {
  slug: string;
  /** Awareness level 1–9, one per Navadurga form (adr/Navadurga). */
  level: number;
  form: string;
  title: string;
  summary: string;
  minutes: number;
  tier: "Foundation" | "Practitioner" | "Mastery";
  lessons: Lesson[];
  realLife: string[];
  attack?: { id: string; name: string }[];
  drill?: { href: string; label: string };
  quiz: Question[];
};

/** Share of questions to answer correctly to pass a module. */
export const PASS_MARK = 0.8;

export const MODULES: Module[] = [
  {
    slug: "incident-response",
    level: 1,
    form: "Shailaputri",
    title: "The incident response lifecycle",
    summary: "What a defender does, in order, from the first alert to the lesson learned.",
    minutes: 12,
    tier: "Foundation",
    lessons: [
      {
        heading: "Four phases",
        body: [
          "NIST SP 800-61 Rev. 2, the most widely used incident handling guide, describes four phases: Preparation; Detection and Analysis; Containment, Eradication and Recovery; and Post-Incident Activity.",
          "They loop. What you learn after one incident becomes preparation for the next. Rev. 3 (2025) reorganises this around the NIST Cybersecurity Framework 2.0 functions, but the work is the same.",
        ],
      },
      {
        heading: "Detection is not diagnosis",
        body: [
          "An alert tells you something looked unusual. Analysis decides whether it is an incident, what caused it and how far it reached. Most of the time spent in an incident is here, because signals arrive in different tools at different times.",
          "Write down what you know and how you know it. An unsupported conclusion is the most expensive mistake in incident response, because everything after it acts on it.",
        ],
      },
      {
        heading: "Contain before you clean",
        body: [
          "Containment limits the damage: isolate a host, disable an account, block an address. Eradication removes the cause, and recovery restores normal service.",
          "Every containment action should say how to undo it and what 'fixed' will look like, before it runs. That is how you avoid an outage you caused yourself.",
        ],
      },
    ],
    realLife: [
      "Keep a running timeline: time, what was observed, where, and who saw it.",
      "Separate facts (log lines, alerts) from conclusions, and link each conclusion to its facts.",
      "Before any containment step, write down the rollback and the expected state afterwards.",
      "After closing, write what would have caught it sooner. That is next incident's preparation.",
    ],
    drill: { href: "/blue-team/INC-2026-0903", label: "Work an intrusion from first alert to response" },
    quiz: [
      { q: "In NIST SP 800-61 Rev. 2, which phase comes directly after Detection and Analysis?", options: ["Preparation", "Containment, Eradication and Recovery", "Post-Incident Activity", "Threat hunting"], answer: 1, why: "The four phases run Preparation → Detection and Analysis → Containment, Eradication and Recovery → Post-Incident Activity." },
      { q: "An alert fires for unusual sign-ins. What is the next step?", options: ["Reset every password in the company", "Analyse whether it is an incident and what caused it", "Close it if nobody complains", "Reimage the server"], answer: 1, why: "An alert is a signal, not a diagnosis. Analysis decides whether it is an incident and what the proportionate response is." },
      { q: "Why decide the rollback before running a containment action?", options: ["It is a legal requirement", "So a wrong or harmful action can be undone safely", "It makes the action faster", "Attackers cannot see it"], answer: 1, why: "Containment changes production. If it was wrong, or broke something, you need a known way back." },
      { q: "What is the main output of Post-Incident Activity?", options: ["A new firewall", "Lessons that improve preparation and detection", "Blame for the person on call", "Deleting the logs"], answer: 1, why: "The lifecycle loops: lessons learned feed the next round of preparation." },
      { q: "Which is the most dangerous mistake during analysis?", options: ["Taking notes", "Acting on a conclusion no evidence supports", "Asking a colleague", "Checking a second log source"], answer: 1, why: "Everything after the conclusion acts on it. An unsupported conclusion sends the whole response in the wrong direction." },
    ],
  },
  {
    slug: "phishing",
    level: 3,
    form: "Chandraghanta",
    title: "Phishing and look-alike domains",
    summary: "How phishing works, how to recognise a forged sender, and what to do when someone clicks.",
    minutes: 10,
    tier: "Foundation",
    attack: [
      { id: "T1566", name: "Phishing" },
      { id: "T1566.002", name: "Spearphishing Link" },
    ],
    lessons: [
      {
        heading: "The trick is trust",
        body: [
          "Phishing (MITRE ATT&CK T1566) gets a person to act: click a link, open an attachment, enter a password, approve a payment. It works because the message looks like it comes from someone the person already trusts.",
          "Look-alike domains are the most common disguise. 'rn' reads as 'm' at a glance, so rn1crosoft-billing.com passes for microsoft. Other tricks are a swapped letter, an extra word like -billing or -secure, or a different top-level domain.",
        ],
      },
      {
        heading: "Check what you can verify",
        body: [
          "The display name is chosen by the sender and proves nothing. The actual sending address and its domain are what to check. On a link, the real destination is what the browser shows when you hover, not the link text.",
          "Email authentication (SPF, DKIM and DMARC) lets a receiving server check that a domain authorised the message. A failure is a strong signal. A pass only proves the message came from that domain, which may be the attacker's own look-alike.",
        ],
      },
      {
        heading: "When someone clicked",
        body: [
          "Find out exactly what happened: link opened, credentials entered, or file run. If credentials were entered, reset them and revoke active sessions, because a reset alone leaves an attacker's existing session working.",
          "Search for the same sender or link across all mailboxes. Phishing rarely goes to one person.",
        ],
      },
    ],
    realLife: [
      "Read the domain from right to left: the part before the top-level domain is the real owner.",
      "Hover over links before clicking; on mobile, long-press to preview.",
      "Treat urgency ('pay today', 'account locked') as a warning sign, not a reason to hurry.",
      "If credentials were entered: reset, revoke sessions, check the mailbox's forwarding rules.",
    ],
    drill: { href: "/blue-team/INC-2026-0902", label: "Investigate a delivered look-alike phishing message" },
    quiz: [
      { q: "Which sender domain is most likely impersonating Microsoft?", options: ["microsoft.com", "rn1crosoft-billing.com", "outlook.office365.com", "login.microsoftonline.com"], answer: 1, why: "'rn' looks like 'm' and '1' like 'i'. The extra '-billing' is another common look-alike trick." },
      { q: "An email shows 'IT Support' as the sender. What does that prove?", options: ["It came from IT", "Nothing; the display name is set by the sender", "It passed DMARC", "It is internal"], answer: 1, why: "Anyone can type any display name. Check the actual address and domain." },
      { q: "A message passes SPF and DKIM. What can you conclude?", options: ["It is safe", "The sending domain authorised it, which may still be an attacker's domain", "It came from your company", "It has no links"], answer: 1, why: "Authentication proves the message came from the domain it claims, not that the domain is trustworthy." },
      { q: "A user entered their password on a phishing page. What is the right first response?", options: ["Reset the password only", "Reset the password and revoke active sessions", "Wait to see if anything happens", "Delete the email"], answer: 1, why: "A reset alone leaves a session the attacker already opened still working." },
      { q: "Which ATT&CK technique ID is Phishing?", options: ["T1110", "T1566", "T1071", "T1486"], answer: 1, why: "T1566 is Phishing. T1110 is Brute Force, T1071 is Application Layer Protocol, and T1486 is Data Encrypted for Impact." },
    ],
  },
  {
    slug: "credential-attacks",
    level: 5,
    form: "Skandamata",
    title: "Credential attacks and account takeover",
    summary: "Brute force, password spraying and credential stuffing — how they differ and what stops each.",
    minutes: 10,
    tier: "Foundation",
    attack: [
      { id: "T1110", name: "Brute Force" },
      { id: "T1110.003", name: "Password Spraying" },
      { id: "T1110.004", name: "Credential Stuffing" },
      { id: "T1078", name: "Valid Accounts" },
    ],
    lessons: [
      {
        heading: "Three shapes of the same attack",
        body: [
          "Brute force (T1110) tries many passwords against one account. Password spraying (T1110.003) tries a few common passwords against many accounts, staying under lockout limits. Credential stuffing (T1110.004) replays username and password pairs leaked from other breaches.",
          "Each leaves a different pattern. Brute force: many failures on one account. Spraying: one or two failures on each of many accounts. Stuffing: many accounts, often from new or rotating sources, with some successes where people reused passwords.",
        ],
      },
      {
        heading: "Why one success matters most",
        body: [
          "Hundreds of failures are noise. The single success among them is the incident, because the attacker now holds a valid account (T1078) and looks like a normal user from then on.",
          "When failures spike, look for successes from the same source or in the same window, and for what those accounts did next.",
        ],
      },
      {
        heading: "What stops it",
        body: [
          "Multi-factor authentication defeats a stolen password alone; phishing-resistant MFA (FIDO2 or passkeys) also resists real-time phishing. Rate limiting and lockouts slow brute force. Checking passwords against known-breached lists blocks reused ones.",
        ],
      },
    ],
    realLife: [
      "Turn on MFA for every account that supports it, and prefer passkeys or security keys.",
      "Never reuse a password; use a password manager.",
      "In logs, always ask: among the failures, was there a success?",
      "After a successful takeover: revoke sessions, reset, and review what the account accessed.",
    ],
    drill: { href: "/blue-team/INC-2026-0901", label: "Investigate 412 failed sign-ins from a new network" },
    quiz: [
      { q: "A few common passwords tried against thousands of accounts is…", options: ["Brute force", "Password spraying", "Credential stuffing", "Phishing"], answer: 1, why: "Spraying spreads a few guesses across many accounts to stay under per-account lockouts." },
      { q: "Username and password pairs from another site's breach are replayed. Which technique is this?", options: ["T1110.004 Credential Stuffing", "T1110.003 Password Spraying", "T1566 Phishing", "T1486 Data Encrypted for Impact"], answer: 0, why: "Credential stuffing replays leaked pairs, and succeeds where people reused passwords." },
      { q: "During a stuffing attack, which event matters most?", options: ["The first failure", "The total number of failures", "A successful sign-in among the failures", "The attacker's country"], answer: 2, why: "The success gives the attacker a valid account (T1078), and from then on they look like a legitimate user." },
      { q: "Which control best defeats a stolen password used on its own?", options: ["Longer session timeouts", "Multi-factor authentication", "Changing the login page colour", "Disabling logging"], answer: 1, why: "With MFA, a password alone is no longer enough to sign in." },
      { q: "Why prefer phishing-resistant MFA such as FIDO2 or passkeys?", options: ["It is cheaper", "It resists real-time phishing that relays one-time codes", "It removes the need for passwords to be secret", "It works without a device"], answer: 1, why: "Code-based MFA can be relayed by a phishing proxy. FIDO2 binds the login to the real site's origin." },
    ],
  },
  {
    slug: "c2-and-lateral-movement",
    level: 6,
    form: "Katyayani",
    title: "Command and control, and lateral movement",
    summary: "How a compromised machine phones home, and how an attacker spreads from it.",
    minutes: 12,
    tier: "Practitioner",
    attack: [
      { id: "T1071.001", name: "Application Layer Protocol: Web Protocols" },
      { id: "T1021.002", name: "Remote Services: SMB/Windows Admin Shares" },
      { id: "T1053.005", name: "Scheduled Task/Job: Scheduled Task" },
    ],
    lessons: [
      {
        heading: "Beaconing",
        body: [
          "Malware on a host checks in with the attacker's command-and-control (C2) server, often over ordinary web traffic (T1071.001) so it blends in. Beacons repeat on a schedule, every 60 seconds give or take a few, for example.",
          "That regularity is the tell. People browse in bursts; software beacons like a clock. A destination nothing else in the network talks to, contacted at steady intervals, deserves a look.",
        ],
      },
      {
        heading: "Spreading",
        body: [
          "From one foothold, attackers move to other machines. On Windows networks that is often over SMB admin shares (T1021.002) with stolen credentials. Then they set something to run again later, such as a scheduled task (T1053.005), so they survive reboots.",
          "New connections between machines that have never talked before, followed by a new scheduled task, form a chain. Each event alone is easy to ignore; together they tell you what is happening.",
        ],
      },
      {
        heading: "Respond in proportion",
        body: [
          "Isolating the first host stops the beacon. But if the attacker has already moved, the other hosts matter too. Scope first, then contain everything in scope, or the attacker simply uses the host you missed.",
        ],
      },
    ],
    realLife: [
      "Look for periodic outbound connections to rare destinations, not just known-bad lists.",
      "Map new internal host-to-host connections. Lateral movement creates edges that didn't exist.",
      "Check for new scheduled tasks or services on any host you suspect.",
      "Scope before you contain, so you don't tip off the attacker while they still hold another host.",
    ],
    drill: { href: "/blue-team/INC-2026-0903", label: "Trace a beacon to lateral movement" },
    quiz: [
      { q: "What makes beaconing stand out from normal browsing?", options: ["It uses HTTPS", "It repeats at regular intervals to a rare destination", "It is always at night", "It uses port 80 only"], answer: 1, why: "Software checks in on a schedule; people browse in irregular bursts. A rare destination plus regular timing is the pattern." },
      { q: "Which ATT&CK technique covers C2 over ordinary web traffic?", options: ["T1071.001", "T1021.002", "T1053.005", "T1566"], answer: 0, why: "T1071.001 is Application Layer Protocol: Web Protocols." },
      { q: "A host opens SMB to two machines it has never contacted, then a scheduled task appears on one. This most likely indicates…", options: ["A backup job", "Lateral movement with persistence", "A printer update", "Normal patching"], answer: 1, why: "New SMB peers (T1021.002) followed by a scheduled task (T1053.005) is the movement-then-persistence chain." },
      { q: "Why scope before containing?", options: ["Containment is slow", "If the attacker holds another host, containing only one alerts them and leaves them inside", "Scoping is required by law", "It saves money"], answer: 1, why: "Partial containment tips the attacker off while leaving them a foothold." },
      { q: "What is the purpose of a scheduled task in an intrusion?", options: ["Speed up the network", "Persistence: running again after a reboot", "Encrypting traffic", "Hiding the IP address"], answer: 1, why: "A scheduled task is a common persistence mechanism (T1053.005)." },
    ],
  },
  {
    slug: "threat-intel",
    level: 4,
    form: "Kushmanda",
    title: "Indicators and threat intelligence",
    summary: "Indicators of compromise, sharing them safely, and using real feeds like CISA KEV.",
    minutes: 8,
    tier: "Practitioner",
    lessons: [
      {
        heading: "Indicators are evidence, not verdicts",
        body: [
          "An indicator of compromise (IOC) is an observable such as an IP address, domain, file hash or URL that has been linked to malicious activity. A match is a reason to look, not proof: an address can be reused, a domain can change hands.",
          "Indicators age. A C2 address from last month may be someone's legitimate server today. Know when and where an indicator was reported.",
        ],
      },
      {
        heading: "Share them safely",
        body: [
          "Defang indicators when sharing so nobody clicks them by accident: hxxp:// instead of http://, and example[.]com instead of example.com. Every indicator on this site is defanged for that reason.",
        ],
      },
      {
        heading: "Prioritise with KEV",
        body: [
          "CISA's Known Exploited Vulnerabilities (KEV) catalogue lists vulnerabilities with evidence of exploitation in the wild. Severity scores say how bad a flaw could be; KEV says attackers are using it now. Patch KEV entries first.",
        ],
      },
    ],
    realLife: [
      "When an indicator matches, check when it was reported and by whom before acting.",
      "Defang indicators in tickets, chat and email.",
      "Patch anything on CISA KEV before higher-scored but unexploited flaws.",
    ],
    drill: { href: "/observatory", label: "Browse real, current threat intelligence" },
    quiz: [
      { q: "An IP on a threat feed appears in your logs. What does that mean?", options: ["You are definitely breached", "It is a reason to investigate, not proof", "The feed is wrong", "Nothing"], answer: 1, why: "Indicators can be reused, shared or stale. A match starts an investigation." },
      { q: "Which is a correctly defanged URL?", options: ["http://evil.com", "hxxp://evil[.]com", "evil.com/", "https://evil.com"], answer: 1, why: "hxxp and [.] stop the link from being clickable or resolvable." },
      { q: "What does CISA's KEV catalogue tell you?", options: ["Every possible vulnerability", "Vulnerabilities known to be exploited in the wild", "Vulnerabilities fixed last year", "Only Windows flaws"], answer: 1, why: "KEV lists vulnerabilities with evidence of active exploitation, which is why they go first." },
      { q: "Why do indicators expire?", options: ["They don't", "Infrastructure is reused and changes hands, so old indicators can point at innocent systems", "Feeds delete them for fun", "IP addresses are random"], answer: 1, why: "Attackers abandon infrastructure, and it is reassigned. An old indicator can mislead." },
    ],
  },
  {
    slug: "att-and-ck",
    level: 2,
    form: "Brahmacharini",
    title: "Reading MITRE ATT&CK",
    summary: "Tactics, techniques and IDs — the shared language defenders use to describe attacks.",
    minutes: 8,
    tier: "Foundation",
    lessons: [
      {
        heading: "Why and how",
        body: [
          "MITRE ATT&CK is a public knowledge base of adversary behaviour observed in real attacks. Tactics are the attacker's goals, such as Initial Access, Persistence, Lateral Movement or Command and Control. Techniques are how they achieve them, each with an ID like T1566.",
          "Sub-techniques add a suffix: T1566.002 is Spearphishing Link, under Phishing. Using IDs means two teams describing the same attack mean exactly the same thing.",
        ],
      },
      {
        heading: "Use it for coverage",
        body: [
          "Map your detections to techniques, and the gaps become visible: the techniques nothing would catch. The ATT&CK coverage page on this site does this for the incident library.",
        ],
      },
    ],
    realLife: [
      "Tag incidents and detections with ATT&CK technique IDs.",
      "Review which tactics your detections cover and which they don't.",
      "Describe attacks by behaviour (technique), not just by tool name; tools change, behaviour repeats.",
    ],
    drill: { href: "/attack", label: "Explore the ATT&CK coverage matrix" },
    quiz: [
      { q: "In ATT&CK, a 'tactic' is…", options: ["A specific tool", "The adversary's goal, such as Persistence", "A malware family", "A CVE"], answer: 1, why: "Tactics are the why; techniques are the how." },
      { q: "T1566.002 is a sub-technique of…", options: ["T1110 Brute Force", "T1566 Phishing", "T1071 Application Layer Protocol", "T1021 Remote Services"], answer: 1, why: "The suffix marks a sub-technique: T1566.002 is Spearphishing Link under Phishing." },
      { q: "Why describe attacks by technique rather than tool name?", options: ["Tools are illegal to name", "Tools change while behaviour repeats, so techniques transfer across attacks", "Techniques are shorter", "Tool names are secret"], answer: 1, why: "Detections built on behaviour still work when the attacker switches tools." },
      { q: "Mapping detections to ATT&CK mainly helps you…", options: ["Speed up servers", "See which techniques you cannot detect", "Avoid writing documentation", "Encrypt logs"], answer: 1, why: "Coverage mapping makes the gaps visible." },
    ],
  },
  {
    slug: "logs-and-detection",
    level: 7,
    form: "Kalaratri",
    title: "Logs and detection",
    summary: "What to log, what normal looks like, and how a detection rule finds what hides in the noise.",
    minutes: 10,
    tier: "Practitioner",
    attack: [{ id: "T1078", name: "Valid Accounts" }],
    lessons: [
      {
        heading: "Log what an investigation will ask for",
        body: [
          "Authentication (successes and failures), process creation, network connections, DNS queries and administrative changes answer most investigation questions. Send them to one place, with synchronised clocks (NTP), and keep them long enough. Many intrusions are found weeks after they began.",
          "On Windows, event ID 4624 is a successful logon and 4625 a failed one; process creation is 4688 (or Sysmon event 1). Knowing the few IDs that matter makes a log readable.",
        ],
      },
      {
        heading: "Anomaly means unusual for this system",
        body: [
          "A baseline is what normal looks like for a host, account or service, including its daily and weekly rhythm. The same login count can be routine at 10:00 on a Monday and alarming at 03:00 on a Sunday.",
          "Too many low-value alerts cause alert fatigue: real alerts get missed in the noise. Tuning a detection to fire less, but on the right thing, is detection engineering, not laziness.",
        ],
      },
      {
        heading: "Detection rules you can share",
        body: [
          "Sigma is an open, generic format for detection rules. A rule written once converts to the query language of many SIEMs. Test a rule against known-bad and known-good activity before trusting it, and map it to an ATT&CK technique so coverage is visible.",
        ],
      },
    ],
    realLife: [
      "Make sure authentication, process, network and DNS logs reach one place with synced clocks.",
      "Learn the handful of event IDs your platform uses for logons and process starts.",
      "Before adding an alert, ask what someone will do when it fires. If nothing, leave it out.",
      "Test every new detection on known-good activity to measure its false positives.",
    ],
    drill: { href: "/detections", label: "Read the Sigma rules drafted from incidents" },
    quiz: [
      { q: "Why must log sources have synchronised clocks?", options: ["To save storage", "So events from different systems can be put in the right order", "Attackers cannot read them", "It is faster"], answer: 1, why: "Correlating an attack across systems depends on ordering events correctly; skewed clocks scramble the timeline." },
      { q: "On Windows, which event ID records a successful logon?", options: ["4625", "4624", "4688", "7045"], answer: 1, why: "4624 is a successful logon. 4625 is a failed logon, 4688 is process creation, and 7045 is a service install." },
      { q: "What is alert fatigue?", options: ["Servers overheating", "So many low-value alerts that real ones get missed", "Analysts working at night", "A type of malware"], answer: 1, why: "Noise trains people to ignore alerts. Fewer, better alerts protect the ones that matter." },
      { q: "What is Sigma?", options: ["A SIEM product", "An open, generic format for detection rules that converts to many SIEM queries", "A malware family", "A log shipper"], answer: 1, why: "Sigma rules are written once and translated to each SIEM's query language." },
      { q: "Why does an anomaly depend on a baseline?", options: ["It doesn't", "Unusual only means something relative to what is normal for that system and time", "Baselines are required by law", "Anomalies are always attacks"], answer: 1, why: "The same activity can be routine or alarming depending on the system's normal pattern." },
    ],
  },
  {
    slug: "recovery-and-verification",
    level: 8,
    form: "Mahagauri",
    title: "Recovery and verification",
    summary: "Removing the attacker, restoring from backups that survive, and proving the fix worked.",
    minutes: 10,
    tier: "Practitioner",
    attack: [{ id: "T1486", name: "Data Encrypted for Impact" }],
    lessons: [
      {
        heading: "Eradicate, then restore",
        body: [
          "Before restoring service, remove what the attacker left: persistence such as scheduled tasks or new accounts, the entry point (patch it), and every credential they may hold (reset and revoke sessions). Restoring onto a host the attacker still controls invites them straight back.",
        ],
      },
      {
        heading: "Backups that survive an attacker",
        body: [
          "The 3-2-1 rule: three copies of the data, on two different types of media, with one copy offsite. Against ransomware, at least one copy must also be offline or immutable, because attackers deliberately find and destroy reachable backups before encrypting.",
          "An untested backup is a hope, not a backup. Restore from it regularly and time how long it takes.",
        ],
      },
      {
        heading: "Verify, don't assume",
        body: [
          "Recovery is finished when the observed state matches the expected state: services healthy, the indicators gone, no beacon, no new persistence. Keep watching for a while, because re-infection often shows up days later. Close the incident only once that is verified.",
        ],
      },
    ],
    realLife: [
      "Keep at least one offline or immutable backup, and test a restore every quarter.",
      "Before restoring, remove persistence and reset every credential the attacker could hold.",
      "Write down what recovered looks like, then check each item before closing.",
      "Watch recovered systems closely for a week afterwards.",
    ],
    drill: { href: "/how-it-works", label: "See how verification and rollback work in the loop" },
    quiz: [
      { q: "The 3-2-1 backup rule means…", options: ["3 backups a day, 2 admins, 1 password", "3 copies, on 2 types of media, 1 offsite", "Back up every 3 hours for 2 days", "3 servers in 2 regions with 1 backup"], answer: 1, why: "Three copies, two media types and one offsite copy, so no single failure destroys all of them." },
      { q: "Why keep an offline or immutable backup against ransomware?", options: ["It is cheaper", "Attackers find and destroy reachable backups before encrypting", "Ransomware cannot read tape", "It is faster to restore"], answer: 1, why: "A backup the attacker can reach is a backup the attacker can delete or encrypt." },
      { q: "What must happen before restoring a compromised host?", options: ["Nothing; restore immediately", "Remove persistence, close the entry point and reset credentials", "Email the attacker", "Delete all logs"], answer: 1, why: "Otherwise the attacker returns through what they left behind." },
      { q: "When is recovery complete?", options: ["When the server reboots", "When the observed state is verified to match the expected state", "When the ticket is closed", "After 24 hours"], answer: 1, why: "Verification compares what is actually observed with what 'fixed' was defined to mean." },
      { q: "What is an untested backup worth?", options: ["The same as a tested one", "Unknown; you don't know whether it restores", "More, because it is newer", "Nothing; delete it"], answer: 1, why: "Only a successful restore proves a backup works." },
    ],
  },
  {
    slug: "capstone",
    level: 9,
    form: "Siddhidatri",
    title: "Capstone — the whole loop",
    summary: "Scenario questions that need every level: detect, investigate, contain, recover and learn.",
    minutes: 12,
    tier: "Mastery",
    lessons: [
      {
        heading: "Putting it together",
        body: [
          "Every real incident uses more than one skill. A credential attack is found in logs (level 7), confirmed by spotting the success among the failures (level 5), scoped by following what the account did next (level 6), contained in proportion (level 1), recovered and verified (level 8), and turned into a better detection (level 7 again).",
          "These questions are scenarios. Read each one as a defender would: what do I know, what don't I know yet, and what is the proportionate next step?",
        ],
      },
    ],
    realLife: [
      "Run a tabletop exercise: walk through one of these scenarios with your team.",
      "After every real incident, note which level's skill would have caught it sooner.",
    ],
    drill: { href: "/training#drills", label: "Clear every practice drill" },
    quiz: [
      { q: "412 failed sign-ins from one new network, then one success. What comes first?", options: ["Block the whole country", "Investigate what the successful account did, and revoke its sessions", "Wait for more failures", "Reset every password in the company"], answer: 1, why: "The success is the incident: that account is now in the attacker's hands." },
      { q: "A workstation beacons every 60 s to a rare domain and has new SMB peers. What do you do?", options: ["Isolate the workstation and close the case", "Scope which hosts are involved, then contain all of them", "Ignore it; HTTPS is encrypted", "Reboot the workstation"], answer: 1, why: "Movement has already happened. Containing one host while the attacker holds another tips them off." },
      { q: "A user approved an OAuth consent on a phishing page, and a token read their mailbox. What must be revoked?", options: ["Only the password", "The OAuth grant and its tokens", "The user's laptop", "Nothing; it was only consent"], answer: 1, why: "The token, not the password, is what has access. A password reset leaves an OAuth grant working." },
      { q: "Two vulnerabilities: one CVSS 9.8 with no known exploitation, one CVSS 7.5 listed in CISA KEV. Patch which first?", options: ["The 9.8", "The KEV-listed one", "Neither", "Whichever is older"], answer: 1, why: "KEV means attackers are exploiting it now. Active exploitation outranks theoretical severity." },
      { q: "Ransomware hits; the backups were on a file share in the same domain. What is the likely problem?", options: ["None", "The backups were reachable and are probably encrypted too", "Backups are too slow", "The share was full"], answer: 1, why: "Reachable backups are a target. That is why one copy must be offline or immutable." },
      { q: "An alert matches an IP from an 18-month-old threat feed. What is it?", options: ["Proof of compromise", "A lead to check, since the address may have changed hands", "A false alarm to ignore", "A reason to shut down the network"], answer: 1, why: "Indicators age. Check context and current ownership before acting." },
      { q: "You find T1053.005 on a host. What has the attacker done?", options: ["Encrypted files", "Set up persistence with a scheduled task", "Sent phishing", "Stolen a password from a browser"], answer: 1, why: "T1053.005 is Scheduled Task, a persistence mechanism." },
      { q: "Before isolating a production database server, what must be ready?", options: ["Nothing", "The rollback, the expected state afterwards, and approval proportionate to the risk", "A press release", "A new server"], answer: 1, why: "Isolating production is high impact: define the way back and get the right approval first." },
    ],
  },
];

MODULES.sort((a, b) => a.level - b.level);

/** The awareness level reached: the highest level with every level below it
 *  passed too. 0 means not started. */
export function levelReached(passed: (slug: string) => boolean): number {
  let level = 0;
  for (const m of MODULES) {
    if (m.level === level + 1 && passed(m.slug)) level = m.level;
    else break;
  }
  return level;
}

export function moduleBySlug(slug: string): Module | undefined {
  return MODULES.find((m) => m.slug === slug);
}

/**
 * A question with its options in a stable shuffled order.
 *
 * 43 of the 46 questions were written with the right answer second, so
 * always picking B passed every test (found 29 Oct 2026). Rather than hand-
 * edit each question, the options are reordered by a permutation seeded from
 * the question's own text. The order is the same on every visit, on the server
 * and on every phone, but the right answer no longer sits in one position.
 */
export function arranged(question: Question): Question {
  let seed = 2166136261;
  for (const ch of question.q) seed = Math.imul(seed ^ ch.charCodeAt(0), 16777619) >>> 0;
  const next = () => {
    seed = (seed + 0x6d2b79f5) >>> 0;
    let t = seed;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
  const order = question.options.map((_, i) => i);
  for (let i = order.length - 1; i > 0; i--) {
    const j = Math.floor(next() * (i + 1));
    [order[i], order[j]] = [order[j], order[i]];
  }
  return { ...question, options: order.map((i) => question.options[i]), answer: order.indexOf(question.answer) };
}
