"""The ATT&CK matrix across the incident library (R75).

A technique tag on one incident says what one step resembled. The same tags
across every incident say what the library *covers* — which tactics it has
observed a step of and which it has not — and that is the claim worth showing,
because it is the one a reader cannot get by opening incidents one at a time.

Two words are kept apart on purpose. An empty tactic is **not observed**: no
incident in this library carries a step under it. It is not "not covered" or
"not detected", both of which would claim something about a detection layer
this console does not run. The matrix describes the library, and the library
is three written scenarios; a column with nothing in it is a fact about what
was written, and the page says so.

Deterministic over the incidents it is given — no model, no lookup. The
column order is ATT&CK's own, so a reader who knows the matrix finds the
tactics where they expect them.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .incidents import Incident

TACTICS: tuple[str, ...] = (
    "Reconnaissance",
    "Resource Development",
    "Initial Access",
    "Execution",
    "Persistence",
    "Privilege Escalation",
    "Defense Evasion",
    "Credential Access",
    "Discovery",
    "Lateral Movement",
    "Collection",
    "Command and Control",
    "Exfiltration",
    "Impact",
)
"""The fourteen Enterprise tactics, in the order ATT&CK draws them."""


@dataclass
class Cell:
    """One technique, and every step in the library that carries it."""

    id: str
    name: str
    tactic: str
    refs: list[str] = field(default_factory=list)
    """`INC-2026-0903#chain-1` — the incident and the step, so a cell links to
    the exact place the technique was observed rather than to a page."""
    incidents: list[str] = field(default_factory=list)

    @property
    def url(self) -> str:
        return f"https://attack.mitre.org/techniques/{self.id.replace('.', '/')}/"


@dataclass
class Column:
    tactic: str
    known: bool
    """Whether the tactic is one of ATT&CK's fourteen. A step written with a
    tactic outside that list is kept and shown rather than dropped or
    silently filed under a neighbour — the mistake is worth seeing."""
    techniques: list[Cell] = field(default_factory=list)

    @property
    def observed(self) -> bool:
        return bool(self.techniques)


@dataclass
class Matrix:
    columns: list[Column]
    incident_count: int
    step_count: int
    """Steps that carry a technique. Steps without one are legitimate — an
    infrastructure step has no ATT&CK mapping — and are not counted here."""

    @property
    def technique_count(self) -> int:
        return sum(len(column.techniques) for column in self.columns)

    @property
    def observed_tactics(self) -> list[str]:
        return [column.tactic for column in self.columns if column.observed]

    @property
    def unobserved_tactics(self) -> list[str]:
        return [column.tactic for column in self.columns if column.known and not column.observed]


def matrix(incidents: list[Incident]) -> Matrix:
    """The library's coverage, one column per tactic, one cell per technique."""
    cells: dict[tuple[str, str], Cell] = {}
    steps = 0
    for incident in incidents:
        for index, link in enumerate(incident.causal_chain):
            technique = link.attack_technique
            if technique is None:
                continue
            steps += 1
            key = (technique.tactic, technique.id)
            cell = cells.setdefault(
                key, Cell(id=technique.id, name=technique.name, tactic=technique.tactic)
            )
            cell.refs.append(f"{incident.id}#chain-{index}")
            if incident.id not in cell.incidents:
                cell.incidents.append(incident.id)

    columns = [Column(tactic=tactic, known=True) for tactic in TACTICS]
    by_tactic = {column.tactic: column for column in columns}
    for (tactic, _), cell in sorted(cells.items(), key=lambda item: item[0][1]):
        column = by_tactic.get(tactic)
        if column is None:
            column = Column(tactic=tactic, known=False)
            by_tactic[tactic] = column
            columns.append(column)
        column.techniques.append(cell)

    return Matrix(columns=columns, incident_count=len(incidents), step_count=steps)


__all__ = ["TACTICS", "Cell", "Column", "Matrix", "matrix"]
