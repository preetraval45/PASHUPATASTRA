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
