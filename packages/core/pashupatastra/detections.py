"""Hand-written detection rules, beside the drafted ones (R77).

R71 drafts a Sigma rule from an incident's stored telemetry, and is honest to
the point of uselessness about it: the beaconing incident's SMB step supports
one field, `Computer: ws-0148`, so the drafted rule catches that incident and
nothing else. A person writing the same detection reaches for the fields the
platform *would* carry — `Image`, `CommandLine`, `ShareName` — and writes a
rule that generalises.

Both belong in one library, and the library has to keep them apart. A drafted
rule is a claim about what the telemetry held; a hand-written one is a claim
about what an analyst believes the technique looks like. The first is
checkable against stored records and the second is not, and a page that showed
them in one style would let the second borrow the first's standing.

So every rule here carries an `author` naming a person, and every drafted rule
carries `sati` — never the other way round. The files under `detections/` are
plain Sigma with three custom keys, prefixed the way R71's are so a Sigma
parser treats them as extensions rather than errors: `x-incidents`, the
incidents the rule was written against; `x-status` is not used — the standard
`status` field is; and `x-notes`, for the reviewer.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from importlib import resources
from pathlib import Path

import yaml

from .sigma import validate

RULES_DIR = "detections"
_TECHNIQUE_TAG = re.compile(r"^attack\.(t\d{4}(?:\.\d{3})?)$", re.IGNORECASE)


@dataclass
class HandWrittenRule:
    rule_id: str
    title: str
    author: str
    incidents: list[str]
    technique_id: str | None
    status: str
    level: str
    text: str
    path: str
    problems: list[str] = field(default_factory=list)
    notes: str = ""

    @property
    def valid(self) -> bool:
        return not self.problems


class DetectionsError(ValueError):
    """A rule file that cannot be admitted — no author, no incident, no id."""


def _technique_from_tags(tags: list[str]) -> str | None:
    for tag in tags:
        match = _TECHNIQUE_TAG.match(str(tag))
        if match:
            return match.group(1).upper()
    return None


def parse_rule(text: str, path: str = "<memory>") -> HandWrittenRule:
    """One file, admitted or refused.

    Refused rather than loaded with blanks: a hand-written rule with no
    author is exactly the thing this module exists to prevent — a rule on the
    page with nobody standing behind it — and an incident list it did not
    name would leave it tied to nothing.
    """
    document = yaml.safe_load(text)
    if not isinstance(document, dict):
        raise DetectionsError(f"{path}: not a Sigma document")
    author = str(document.get("author") or "").strip()
    if not author:
        raise DetectionsError(f"{path}: a hand-written rule must name its author")
    incidents = document.get("x-incidents") or []
    if not isinstance(incidents, list) or not incidents:
        raise DetectionsError(f"{path}: x-incidents must name at least one incident")
    rule_id = str(document.get("id") or "").strip()
    if not rule_id:
        raise DetectionsError(f"{path}: id is required")
    return HandWrittenRule(
        rule_id=rule_id,
        title=str(document.get("title") or ""),
        author=author,
        incidents=[str(i) for i in incidents],
        technique_id=_technique_from_tags(list(document.get("tags") or [])),
        status=str(document.get("status") or ""),
        level=str(document.get("level") or ""),
        text=text,
        path=path,
        problems=validate(text),
        notes=str(document.get("x-notes") or ""),
    )


def load_rules(directory: Path | None = None) -> list[HandWrittenRule]:
    """Every rule under `detections/`, sorted by id. A bad file raises — a
    library that quietly skips a broken rule is a library with a rule missing
    that nobody knows about."""
    if directory is None:
        directory = Path(str(resources.files("pashupatastra") / RULES_DIR))
    rules = [
        parse_rule(path.read_text(encoding="utf-8"), path.name)
        for path in sorted(directory.glob("*.yml")) + sorted(directory.glob("*.yaml"))
    ]
    seen: set[str] = set()
    for rule in rules:
        if rule.rule_id in seen:
            raise DetectionsError(f"{rule.path}: id {rule.rule_id} is used twice")
        seen.add(rule.rule_id)
    return sorted(rules, key=lambda r: r.rule_id)


__all__ = ["DetectionsError", "HandWrittenRule", "load_rules", "parse_rule"]
