/**
 * Practice questions with worked answers, from beginner to expert
 * (components/practice.tsx). Flashcards rather than a quiz: say your answer,
 * reveal the model one, and mark whether you knew it.
 *
 * Facts follow NIST, MITRE ATT&CK, CISA and the sources named in an answer;
 * ATT&CK IDs are linked by the page.
 */

export type Tier = "beginner" | "intermediate" | "advanced" | "expert";

export const TIERS: { id: Tier; label: string; who: string }[] = [
  { id: "beginner", label: "Beginner", who: "Anyone with an inbox and a phone" },
  { id: "intermediate", label: "Intermediate", who: "New analysts and curious engineers" },
  { id: "advanced", label: "Advanced", who: "Incident responders" },
  { id: "expert", label: "Expert", who: "Threat hunters and detection engineers" },
];

export type Card = { tier: Tier; q: string; a: string };

export const CARDS: Card[] = [
  // Beginner
  { tier: "beginner", q: "What is multi-factor authentication (MFA), and why does it help?", a: "A second proof of who you are besides the password: an app prompt, a code or a security key. A stolen password alone no longer gets an attacker in. Phishing-resistant keys (FIDO2) are the strongest kind." },
  { tier: "beginner", q: "What makes a password strong?", a: "Length and uniqueness. A long passphrase or a password manager's random password, used on one site only. Symbol swaps like P@ssw0rd add almost nothing." },
  { tier: "beginner", q: "Why install updates promptly?", a: "Updates fix known flaws, and attackers exploit known flaws quickly once they are public. CISA keeps a catalogue of vulnerabilities seen exploited in the wild for exactly this reason." },
  { tier: "beginner", q: "You clicked a suspicious link. What now?", a: "Report it to IT or security straight away, even if nothing seemed to happen. If you typed a password, change it from the real site and say so. Fast reporting is what limits the damage, and nobody should be blamed for it." },
  { tier: "beginner", q: "What does a password manager do for you?", a: "It creates and stores a unique strong password for every site, behind one master password. It also only fills in on the real site, so a look-alike phishing page gets nothing." },
  { tier: "beginner", q: "What is the difference between a virus and ransomware?", a: "A virus is code that spreads by infecting files or programs. Ransomware encrypts your data and demands payment to unlock it; today it usually steals the data first too, and threatens to publish it." },
  { tier: "beginner", q: "What is the 3-2-1 backup rule?", a: "Three copies of your data, on two different kinds of storage, with one kept offsite. Keep one copy offline or unchangeable too, because ransomware goes after backups it can reach." },
  { tier: "beginner", q: "How can you tell where a link really goes?", a: "Hover or long-press to see the address, then read the domain: the part just before the first single slash. paypal.com.account-verify.example is account-verify.example, not PayPal." },

  // Intermediate
  { tier: "intermediate", q: "In MITRE ATT&CK, what is the difference between a tactic and a technique?", a: "A tactic is the attacker's goal, the why: Credential Access. A technique is how they achieve it: OS Credential Dumping, T1003. Sub-techniques go one level deeper: LSASS Memory, T1003.001." },
  { tier: "intermediate", q: "What is an indicator of compromise (IOC)?", a: "An artefact that shows an intrusion: a file hash, an IP address, a domain, a registry key. Useful for matching, but brittle: attackers change them cheaply, so they expire." },
  { tier: "intermediate", q: "What does the Pyramid of Pain describe?", a: "David Bianco's ranking of indicators by how much it hurts attackers when you detect them. Hashes and IPs at the bottom are trivial to change; tools and TTPs (behaviour) at the top are expensive. Detect behaviour for lasting value." },
  { tier: "intermediate", q: "What is lateral movement?", a: "Moving from the first compromised machine to others, towards the real target: remote services like RDP or SMB (T1021), stolen credentials, remote execution. It is the ATT&CK tactic TA0008." },
  { tier: "intermediate", q: "What does a SIEM do?", a: "Collects logs from many systems in one place, normalises them, and correlates them to detect and investigate attacks. Its value depends on which logs reach it and how well the rules are tuned." },
  { tier: "intermediate", q: "What is the principle of least privilege?", a: "Every account and service gets only the access its job needs, for only as long as it needs it. When something is compromised, the attacker inherits less." },
  { tier: "intermediate", q: "What does credential stuffing look like in logs?", a: "Many failed sign-ins spread across many accounts, a few attempts each, from many IP addresses, often residential proxies, followed by some successes. It is breached passwords being replayed (T1110.004)." },
  { tier: "intermediate", q: "How is EDR different from traditional antivirus?", a: "Antivirus mainly blocks known malicious files. EDR records what processes on the endpoint do, flags suspicious behaviour, and lets responders investigate and isolate the machine remotely." },

  // Advanced
  { tier: "advanced", q: "What are the phases of incident response in NIST SP 800-61 Rev. 2?", a: "Preparation; detection and analysis; containment, eradication and recovery; post-incident activity. Rev. 3 (2025) reorganises them around the NIST Cybersecurity Framework 2.0 functions, but the work is the same." },
  { tier: "advanced", q: "Why contain before you eradicate?", a: "Containment stops the spread while evidence is preserved. Eradicating one foothold first can tip the attacker off while they still hold others, and they come back through those." },
  { tier: "advanced", q: "Why does a password reset not end a token-theft incident?", a: "A stolen session or refresh token stays valid after the password changes. Revoke the user's sessions and tokens, check for attacker-added MFA methods and inbox rules, then reset." },
  { tier: "advanced", q: "How do you tell malware beaconing from backup software?", a: "Both make regular connections to one destination. The difference is the destination and the software: a known backup provider and a known process, versus a new or rare domain, low-jitter timing, small even-sized messages, and an unexpected process." },
  { tier: "advanced", q: "What is DNS tunnelling, and how does it show up?", a: "Hiding data or command traffic in DNS queries and answers (Application Layer Protocol: DNS, T1071.004). Look for long, random-looking subdomains, unusual record types like TXT, and high query volume to one domain." },
  { tier: "advanced", q: "What is Kerberoasting, and how do you defend against it?", a: "Requesting Kerberos service tickets for accounts with service principal names and cracking them offline (T1558.003). Defend with long random service-account passwords or managed service accounts, and alert on bursts of service-ticket requests, especially using RC4." },
  { tier: "advanced", q: "What should a post-incident review produce?", a: "A timeline, the root cause, what worked and what did not, and action items with owners and dates. Blameless, so people say what really happened." },
  { tier: "advanced", q: "Why verify after remediation?", a: "To compare what you observe with what you expected: no more beacons, the attacker's accounts disabled, the fix still in place. A fix that is not checked is a hope." },

  // Expert
  { tier: "expert", q: "What is detection-as-code?", a: "Detections written as version-controlled rules, tested against sample attack and benign data, reviewed like code, and deployed by a pipeline. It makes detections repeatable, reviewable and measurable." },
  { tier: "expert", q: "What is Sigma?", a: "An open, generic format for log-based detection rules. One Sigma rule converts into the query languages of many SIEMs, so detections can be shared and kept independent of a vendor." },
  { tier: "expert", q: "What is hypothesis-driven threat hunting?", a: "Start from a testable idea informed by intelligence or ATT&CK, such as 'attackers here persist through scheduled tasks (T1053.005)'. Query the data to prove or disprove it, and turn what you find into a detection." },
  { tier: "expert", q: "What is adversary emulation?", a: "Replaying a real group's known techniques in a controlled way, using tools like MITRE CALDERA or Atomic Red Team, to test whether detection and response actually work against them." },
  { tier: "expert", q: "Why test detectors on attack families they never saw?", a: "A random train/test split puts near-copies of training attacks in the test, so scores look near perfect. Holding out whole families measures what matters, detecting the new; in this project's own measurement F1 fell by more than half." },
  { tier: "expert", q: "What is 'living off the land'?", a: "Attacking with tools already on the system, such as PowerShell, WMI or certutil, so nothing new is installed and activity blends in. Detect it through behaviour and command lines, not file signatures." },
  { tier: "expert", q: "What is purple teaming?", a: "Attackers (red) and defenders (blue) working together in real time: red runs a technique, blue checks whether it was seen, and both fix the gap before moving on." },
  { tier: "expert", q: "How do you reduce alert fatigue without missing attacks?", a: "Measure each rule's false-alarm rate and tune or retire the noisy ones, correlate related alerts into one incident, rank by risk, and suppress known-benign activity by name. Track precision as a number, not a feeling." },
];
