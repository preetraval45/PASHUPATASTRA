"""The corpus Kushmanda learns from — permissively licensed security text only.

Kushmanda (adr/Navadurga, model 4) is Sati's own language model. Its weights
are meant to ship under Apache-2.0, so it learns only from text whose terms
allow that:

* **MITRE ATT&CK** (enterprise) and **CAPEC** — technique, group, software,
  mitigation and attack-pattern descriptions. MITRE grants a royalty-free
  licence to use and prepare derivative works, with attribution.
* **CISA KEV** — vulnerability names and required actions; U.S. government work.
* **NVD CVE descriptions** (from v2, `cve=True`) — every published CVE, from
  NIST's yearly JSON 2.0 feeds. The descriptions come from the CVE Program,
  whose terms of use grant a perpetual, royalty-free licence to reproduce and
  prepare derivative works; NVD's own data is a U.S. government work. About
  20x the rest of the corpus put together: v1 (1.1M tokens) overfitted after
  a few hundred steps, because the corpus was too small for the model.
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
CWE = "https://cwe.mitre.org/data/xml/cwec_latest.xml.zip"
NVD = "https://nvd.nist.gov/feeds/json/cve/2.0/nvdcve-2.0-{year}.json.gz"
NVD_YEARS = range(2002, 2027)

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


def procedure_documents(cache: Path) -> list[dict]:
    """ATT&CK procedure examples: how a named group, malware family, tool or
    campaign used a technique, in an analyst's words."""
    bundle = json.loads(_get(ATTACK, cache))
    objects = {o["id"]: o for o in bundle["objects"]}
    docs = []
    for o in bundle["objects"]:
        if o.get("type") != "relationship" or o.get("relationship_type") != "uses" or o.get("revoked"):
            continue
        source, target = objects.get(o["source_ref"]), objects.get(o["target_ref"])
        if not source or not target or target.get("type") != "attack-pattern":
            continue
        text = _clean(o.get("description", ""))
        if len(text) >= 60:
            docs.append({"source": "mitre-attack-procedure", "id": o["id"], "text": f"{target.get('name', '')}: {text}"})
    return docs


def cwe_documents(cache: Path) -> list[dict]:
    """MITRE CWE weaknesses — free for research, development and commercial use
    with MITRE's copyright notice retained (datasheets.md)."""
    import io
    import xml.etree.ElementTree as ET
    import zipfile

    with zipfile.ZipFile(io.BytesIO(_get(CWE, cache))) as zf:
        xml = zf.read(next(n for n in zf.namelist() if n.endswith(".xml")))
    root = ET.fromstring(xml)
    ns = {"c": root.tag.split("}")[0].strip("{")} if root.tag.startswith("{") else {}
    prefix = "c:" if ns else ""
    docs = []
    for weakness in root.iter(f"{{{ns['c']}}}Weakness" if ns else "Weakness"):
        if weakness.get("Status") == "Deprecated":
            continue
        parts = [
            " ".join("".join(el.itertext()).split())
            for tag in ("Description", "Extended_Description")
            for el in weakness.findall(f"{prefix}{tag}", ns)
        ]
        text = " ".join(p for p in parts if p)
        if len(text) >= 80:
            docs.append({"source": "mitre-cwe", "id": f"CWE-{weakness.get('ID')}",
                         "text": f"CWE-{weakness.get('ID')} {weakness.get('Name', '')}\n{text}"})
    return docs


def nvd_record(item: dict) -> dict | None:
    """One NVD JSON 2.0 vulnerability → a document, or None if rejected or empty."""
    cve = item.get("cve", {})
    if cve.get("vulnStatus") == "Rejected":
        return None
    description = next((d["value"] for d in cve.get("descriptions", []) if d.get("lang") == "en"), "").strip()
    if len(description) < 60 or description.startswith("** REJECT"):
        return None
    weaknesses = sorted({
        d["value"] for w in cve.get("weaknesses", []) for d in w.get("description", [])
        if d.get("value", "").startswith("CWE-")
    })
    text = f"{cve['id']}: {description}"
    if weaknesses:
        text += f" Weakness: {', '.join(weaknesses)}."
    return {"source": "nvd-cve", "id": cve["id"], "text": text}


def nvd_documents(cache: Path, years: range = NVD_YEARS) -> list[dict]:
    import gzip
    import urllib.error

    docs = []
    for year in years:
        try:
            feed = json.loads(gzip.decompress(_get(NVD.format(year=year), cache)))
        except urllib.error.HTTPError:  # a year not published yet
            continue
        docs.extend(d for d in map(nvd_record, feed.get("vulnerabilities", [])) if d)
    return docs


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


def build(cache: Path, root: Path, clean: bool = True, cve: bool = False) -> list[dict]:
    docs = [
        *stix_documents(ATTACK, "mitre-attack", cache),
        *procedure_documents(cache),
        *stix_documents(CAPEC, "mitre-capec", cache),
        *cwe_documents(cache),
        *kev_documents(cache),
        *repo_documents(root),
        *(nvd_documents(cache) if cve else []),
    ]
    if not clean:
        return docs
    from sati.lm.clean import deduplicate

    kept, stats = deduplicate(docs)
    print(f"cleaning: {stats}")
    return kept


def split(docs: list[dict], held_out: float = 0.05) -> tuple[list[dict], list[dict]]:
    """By document, deterministically: a document's hash decides its side, so
    the split is stable across runs and machines."""
    train, test = [], []
    for doc in docs:
        bucket = int(hashlib.sha256(f"{doc['source']}:{doc['id']}".encode()).hexdigest(), 16) % 1000
        (test if bucket < held_out * 1000 else train).append(doc)
    return train, test
