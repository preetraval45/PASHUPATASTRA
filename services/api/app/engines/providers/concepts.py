"""Everyday security words, pointed at the knowledge-base entry they mean.

Retrieval reads words, so a plain question can land on a neighbour: "what is
ransomware?" found Local Execution of Code, "what is a DDoS attack?" found
Botnet, "what is MFA?" found the technique that *disables* MFA (1 Nov 2026).
These maps send the common names to the entry a security person would mean.
They only point: every answer's text still comes from the knowledge base, and
an ID that is not in it is skipped rather than invented (rule 1).

ATT&CK's tactics (the attacker's goals) are not passages in the knowledge base,
so each is given here with MITRE's own one-line description and three of its
well-known techniques; the techniques' titles and text come from the knowledge
base. Source: https://attack.mitre.org/tactics/enterprise/
"""

from __future__ import annotations

import re

#: A common name → the knowledge-base ID it means.
CONCEPTS: dict[str, str] = {
    "ransomware": "T1486",
    "ddos": "T1498",
    "dos": "T1498",
    "denial of service": "T1498",
    "denial-of-service": "T1498",
    "distributed denial of service": "T1498",
    "mfa": "M1032",
    "2fa": "M1032",
    "multi-factor authentication": "M1032",
    "multifactor authentication": "M1032",
    "two-factor authentication": "M1032",
    "man-in-the-middle": "T1557",
    "man in the middle": "T1557",
    "mitm": "T1557",
    "adversary-in-the-middle": "T1557",
    "keylogger": "T1056.001",
    "keylogging": "T1056.001",
    "password spraying": "T1110.003",
    "spearphishing attachment": "T1566.001",
    "malicious attachment": "T1566.001",
    "supply chain attack": "T1195",
    "business email compromise": "T1657",
    "bec": "T1657",
    "brute force": "T1110",
    "credential dumping": "T1003",
    "user training": "M1017",
    "security awareness training": "M1017",
    "password policy": "M1027",
    "password policies": "M1027",
    "trojan": "T1036",
    "trojan horse": "T1036",
    # Added 2 Nov (owner: launch blockers). Each checked against knowledge.json.
    "sql injection": "CAPEC-66",
    "sqli": "CAPEC-66",
    "cross-site scripting": "CAPEC-63",
    "cross site scripting": "CAPEC-63",
    "xss": "CAPEC-63",
    "social engineering": "T1684",
    "vishing": "T1598.004",
    "voice phishing": "T1598.004",
    "cryptojacking": "T1496",
    "cryptomining": "T1496",
    "crypto mining": "T1496",
    "least privilege": "M1026",
    "principle of least privilege": "M1026",
    "watering hole": "T1189",
    "drive-by download": "T1189",
    "web shell": "T1505.003",
    "webshell": "T1505.003",
    "rootkit": "T1014",
    "botnet": "T1583.005",
    "session hijacking": "CAPEC-593",
    "clickjacking": "CAPEC-103",
    "backups": "M1053",
    "data backup": "M1053",
    "antivirus": "M1049",
    "anti-virus": "M1049",
    "network segmentation": "M1030",
    "patching": "M1051",
    "patch management": "M1051",
    "software updates": "M1051",
}

#: ATT&CK's enterprise tactics: name, ID, MITRE's description, three well-known techniques.
TACTICS: dict[str, tuple[str, str, str, tuple[str, ...]]] = {
    "reconnaissance": ("Reconnaissance", "TA0043", "The adversary is trying to gather information they can use to plan future operations.", ("T1595", "T1598", "T1589")),
    "resource development": ("Resource Development", "TA0042", "The adversary is trying to establish resources they can use to support operations.", ("T1583", "T1584", "T1587")),
    "initial access": ("Initial Access", "TA0001", "The adversary is trying to get into your network.", ("T1566", "T1190", "T1078")),
    "execution": ("Execution", "TA0002", "The adversary is trying to run malicious code.", ("T1059", "T1204", "T1053")),
    "persistence": ("Persistence", "TA0003", "The adversary is trying to maintain their foothold.", ("T1053", "T1547", "T1136")),
    "privilege escalation": ("Privilege Escalation", "TA0004", "The adversary is trying to gain higher-level permissions.", ("T1068", "T1548", "T1078")),
    "defense evasion": ("Defense Evasion", "TA0005", "The adversary is trying to avoid being detected.", ("T1027", "T1070", "T1036")),
    "defence evasion": ("Defense Evasion", "TA0005", "The adversary is trying to avoid being detected.", ("T1027", "T1070", "T1036")),
    "credential access": ("Credential Access", "TA0006", "The adversary is trying to steal account names and passwords.", ("T1003", "T1110", "T1539")),
    "discovery": ("Discovery", "TA0007", "The adversary is trying to figure out your environment.", ("T1082", "T1046", "T1087")),
    "lateral movement": ("Lateral Movement", "TA0008", "The adversary is trying to move through your environment.", ("T1021", "T1210", "T1570")),
    "collection": ("Collection", "TA0009", "The adversary is trying to gather data of interest to their goal.", ("T1005", "T1114", "T1113")),
    "command and control": ("Command and Control", "TA0011", "The adversary is trying to communicate with compromised systems to control them.", ("T1071", "T1105", "T1573")),
    "c2": ("Command and Control", "TA0011", "The adversary is trying to communicate with compromised systems to control them.", ("T1071", "T1105", "T1573")),
    "exfiltration": ("Exfiltration", "TA0010", "The adversary is trying to steal data.", ("T1041", "T1567", "T1020")),
    "data exfiltration": ("Exfiltration", "TA0010", "The adversary is trying to steal data.", ("T1041", "T1567", "T1020")),
    "impact": ("Impact", "TA0040", "The adversary is trying to manipulate, interrupt, or destroy your systems and data.", ("T1486", "T1490", "T1498")),
}

#: Everyday terms the knowledge base has no entry for, defined in the words of NIST's security glossary
#: (https://csrc.nist.gov/glossary), quoted exactly with the publication NIST cites, plus the knowledge-base
#: entries that bear on each. Rule 1: the definition is a published source's text with its link, never ours;
#: the related entries' text comes from the knowledge base. Retrieved 2 Nov 2026.
#: name -> (title, definition, cited publication, NIST glossary URL, related knowledge-base IDs)
GLOSSARY: dict[str, tuple[str, str, str, str, tuple[str, ...]]] = {}

_DEFINED = (
    (("zero-day", "zero day", "0-day", "zero-day attack", "zero-day exploit", "zero-day vulnerability", "zero day attack"),
     "Zero-day attack", "An attack that exploits a previously unknown hardware, firmware, or software vulnerability.",
     "CNSSI 4009-2022", "https://csrc.nist.gov/glossary/term/zero_day_attack", ("T1190", "T1203", "M1051")),
    (("vpn", "virtual private network"),
     "Virtual private network (VPN)",
     "Protected information system link utilizing tunneling, security controls, and endpoint address translation "
     "giving the impression of a dedicated line.",
     "CNSSI 4009-2022", "https://csrc.nist.gov/glossary/term/virtual_private_network", ("T1133", "M1032")),
    (("worm", "computer worm"),
     "Worm",
     "Self-contained program that can propagate itself through data processing systems or computer networks. Note: "
     "Worms are often designed to use up available resources such as storage space or processing time.",
     "CNSSI 4009-2022, from ISO/IEC 2382:2015", "https://csrc.nist.gov/glossary/term/worm", ("T1210", "T1570")),
    (("spyware",),
     "Spyware",
     "Software that is secretly or surreptitiously installed into an information system to gather information on "
     "individuals or organizations without their knowledge; a type of malicious code.",
     "NIST SP 800-128, from CNSSI 4009-2022", "https://csrc.nist.gov/glossary/term/spyware", ("T1056.001", "M1049")),
    (("backdoor", "back door"),
     "Backdoor", "An undocumented way of gaining access to a computer system. A backdoor is a potential security risk.",
     "NIST SP 800-82r3", "https://csrc.nist.gov/glossary/term/backdoor", ("T1505.003", "T1136")),
    (("insider threat", "insider threats", "insider"),
     "Insider threat",
     "The threat that an insider will use her/his authorized access, wittingly or unwittingly, to do harm to the "
     "security of organizational operations and assets, individuals, other organizations, and the Nation. This "
     "threat can include damage through espionage, terrorism, unauthorized disclosure of national security "
     "information, or through the loss or degradation of organizational resources or capabilities.",
     "NIST SP 800-53 Rev. 5, adapted from CNSSI 4009-2022", "https://csrc.nist.gov/glossary/term/insider_threat",
     ("M1026", "M1018")),
    (("zero trust", "zero-trust", "zero trust architecture"),
     "Zero trust",
     "A collection of concepts and ideas designed to minimize uncertainty in enforcing accurate, least privilege "
     "per-request access decisions in information systems and services in the face of a network viewed as compromised.",
     "NIST SP 800-207", "https://csrc.nist.gov/glossary/term/zero_trust", ("M1032", "M1030", "M1026")),
    (("honeypot", "honey pot", "honeypots"),
     "Honeypot",
     "A system (e.g., a web server) or system resource (e.g., a file on a server) that is designed to be attractive "
     "to potential crackers and intruders, like honey is attractive to bears.",
     "CNSSI 4009-2022, from IETF RFC 4949 Ver 2", "https://csrc.nist.gov/glossary/term/honeypot", ()),
)
for _names, *_entry in _DEFINED:
    for _name in _names:
        GLOSSARY[_name] = tuple(_entry)  # type: ignore[assignment]

#: Words around a name that do not change what it names: "a DDoS attack", "ransomware attacks".
_AROUND = re.compile(r"^(?:a|an|the)\s+|\s+(?:attacks?|tactic|techniques?)$", re.IGNORECASE)


def normalise(subject: str) -> str:
    """The subject as a key: lower case, without an article or a trailing "attack"."""
    key = " ".join(subject.lower().split())
    previous = None
    while previous != key:
        previous, key = key, _AROUND.sub("", key).strip()
    return key


def concept(question: str) -> str | None:
    """The entry a short question names, longest name first, matched as whole words in the question
    itself: the framing filter splits hyphenated names ("man-in-the-middle"), so it is not used here.
    Questions of more than six words are left to retrieval."""
    text = " ".join(question.lower().split())
    if len(re.findall(r"[a-z0-9]+", text)) > 8:
        return None
    for name in sorted(CONCEPTS, key=len, reverse=True):
        if re.search(rf"(?<![\w-]){re.escape(name)}(?![\w-])", text):
            return CONCEPTS[name]
    return None


def tactic(subject: str) -> tuple[str, str, str, tuple[str, ...]] | None:
    return TACTICS.get(normalise(subject))


def glossary(question: str) -> tuple[str, str, str, str, tuple[str, ...]] | None:
    """The glossary entry a short question names, matched as whole words, longest name first; None when the
    question is long (retrieval's job) or names nothing defined here."""
    text = " ".join(question.lower().split())
    if len(re.findall(r"[a-z0-9]+", text)) > 8:
        return None
    for name in sorted(GLOSSARY, key=len, reverse=True):
        if re.search(rf"(?<![\w-]){re.escape(name)}(?![\w-])", text):
            return GLOSSARY[name]
    return None
