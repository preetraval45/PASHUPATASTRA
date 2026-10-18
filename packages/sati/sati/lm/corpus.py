"""The corpus Kushmanda learns from — permissively licensed security text only.

Kushmanda (adr/Navadurga, model 4) is Sati's own language model. Its weights
are meant to ship under Apache-2.0, so it learns only from text whose terms
allow that:

* **MITRE ATT&CK** (enterprise) and **CAPEC** — technique, group, software,
  mitigation and attack-pattern descriptions. MITRE grants a royalty-free
  licence to use and prepare derivative works, with attribution.
* **CISA KEV** — vulnerability names and required actions; U.S. government work.
* **This repository's own writing** — the training course and the docs.

LogHub is deliberately excluded: it is research-use only (datasheets.md).

Documents, not lines, are the unit — the held-out split is by document, so
no paragraph of a test document was seen in training.
"""

from __future__ import annotations

import hashlib
import json
import re
import urllib.request
from pathlib import Path

ATTACK = "https://raw.githubusercontent.com/mitre/cti/master/enterprise-attack/enterprise-attack.json"
CAPEC = "https://raw.githubusercontent.com/mitre/cti/master/capec/2.1/stix-capec.json"
KEV = "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json"

CITATION = re.compile(r"\(Citation: [^)]*\)")
MARKUP = re.compile(r"<[^>]+>")


def _get(url: str, cache: Path) -> bytes:
    target = cache / hashlib.sha1(url.encode()).hexdigest()
    if target.exists():
        return target.read_bytes()
    cache.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(url, headers={"User-Agent": "Pashupatastra-corpus/1.0"})
    with urllib.request.urlopen(request, timeout=300) as response:
        body = response.read()
    target.write_bytes(body)
    return body


def _clean(text: str) -> str:
    text = CITATION.sub("", text)
    text = MARKUP.sub("", text)
    return re.sub(r"[ \t]+", " ", text).strip()


def stix_documents(url: str, source: str, cache: Path) -> list[dict]:
    bundle = json.loads(_get(url, cache))
    docs = []
    for obj in bundle.get("objects", []):
        if obj.get("revoked") or obj.get("x_mitre_deprecated"):
            continue
        description = _clean(obj.get("description", ""))
        name = obj.get("name", "")
        if len(description) < 80 or not name:
            continue
        kind = obj.get("type", "").replace("x-mitre-", "").replace("-", " ")
        external = next((r.get("external_id") for r in obj.get("external_references", []) if r.get("external_id")), "")
        header = f"{name} ({external})" if external else name
        docs.append({"source": source, "id": obj.get("id", name), "text": f"{header} — {kind}\n{description}"})
    return docs


def kev_documents(cache: Path) -> list[dict]:
    data = json.loads(_get(KEV, cache))
    return [
        {
            "source": "cisa-kev",
            "id": v["cveID"],
            "text": (
                f"{v['cveID']}: {v.get('vulnerabilityName', '')}. {v.get('shortDescription', '')} "
                f"Affected: {v.get('vendorProject', '')} {v.get('product', '')}. "
                f"Required action: {v.get('requiredAction', '')}"
            ).strip(),
        }
        for v in data.get("vulnerabilities", [])
    ]


def repo_documents(root: Path) -> list[dict]:
    docs = []
    for path in sorted([*root.glob("docs/**/*.md"), root / "apps" / "web" / "lib" / "training.ts"]):
        if not path.exists() or "node_modules" in path.parts:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for i, chunk in enumerate(re.split(r"\n#{1,3} ", text)):
            chunk = chunk.strip()
            if len(chunk) >= 200:
                docs.append({"source": "repository", "id": f"{path.relative_to(root)}#{i}", "text": chunk})
    return docs


def build(cache: Path, root: Path) -> list[dict]:
    return [
        *stix_documents(ATTACK, "mitre-attack", cache),
        *stix_documents(CAPEC, "mitre-capec", cache),
        *kev_documents(cache),
        *repo_documents(root),
    ]


def split(docs: list[dict], held_out: float = 0.05) -> tuple[list[dict], list[dict]]:
    """By document, deterministically: a document's hash decides its side, so
    the split is stable across runs and machines."""
    train, test = [], []
    for doc in docs:
        bucket = int(hashlib.sha256(f"{doc['source']}:{doc['id']}".encode()).hexdigest(), 16) % 1000
        (test if bucket < held_out * 1000 else train).append(doc)
    return train, test
