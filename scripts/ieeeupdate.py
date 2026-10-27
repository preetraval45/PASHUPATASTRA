"""Bring `docs/research/Pashupatastra IEEE Paper.docx` up to date, as tracked changes.

    python scripts/ieeeupdate.py --out "docs/research/Pashupatastra IEEE Paper.docx"

The paper (7 Oct 2026) predates Sati's own models. This inserts the results
since then: the nine models, the external benchmark against general LLMs,
sim-to-real on three systems, the detection and verification models, and
serving fidelity. Every insertion is a tracked change by "Claude", so the
author accepts or rejects each one in Word; the paper's voice stays the
author's. Every number is read from the committed results files, never typed:
`scripts/reproduce.py --check` keeps those files and the tables in step.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import tempfile
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parents[1]
MODELS = ROOT / "docs" / "research" / "models"
WEB = ROOT / "apps" / "web" / "lib" / "models"
AUTHOR, DATE = "Claude", "2026-10-27T00:00:00Z"
ORIGINAL = "bcc5849"  # the paper as the author wrote it
_ids = iter(range(91000, 99999))


def j(name: str, folder: Path = MODELS) -> dict:
    return json.loads((folder / name).read_text(encoding="utf-8"))


def f3(x: float) -> str:
    return f"{x:.3f}"


# --- tracked XML builders, in the paper's own formatting ---------------------

def _mark() -> str:
    return f'w:id="{next(_ids)}" w:author="{AUTHOR}" w:date="{DATE}"'


def _run(text: str, rpr: str = "") -> str:
    return (f'<w:ins {_mark()}><w:r>{f"<w:rPr>{rpr}</w:rPr>" if rpr else ""}'
            f'<w:t xml:space="preserve">{escape(text)}</w:t></w:r></w:ins>')


def _para(ppr: str, text: str, rpr: str = "") -> str:
    return f'<w:p><w:pPr>{ppr}<w:rPr><w:ins {_mark()}/></w:rPr></w:pPr>{_run(text, rpr)}</w:p>'


def body(text: str) -> str:
    return _para('<w:spacing w:after="0" w:line="240"/><w:ind w:firstLine="202"/><w:jc w:val="both"/>', text)


def subhead(text: str) -> str:
    return _para('<w:keepNext/><w:spacing w:after="40" w:before="80"/>', text, "<w:i/><w:iCs/>")


def caption(number: str, title: str) -> str:
    small = "<w:smallCaps/><w:sz w:val=\"16\"/><w:szCs w:val=\"16\"/>"
    return (_para('<w:keepNext/><w:spacing w:after="0" w:before="160"/><w:jc w:val="center"/>', f"TABLE {number}", small)
            + _para('<w:keepNext/><w:spacing w:after="60"/><w:jc w:val="center"/>', title, small))


def table(rows: list[list[str]], widths: list[int]) -> str:
    assert sum(widths) == 5040, "a column of the paper is 5040 twips wide"
    grid = "".join(f'<w:gridCol w:w="{w}"/>' for w in widths)
    out = ['<w:tbl><w:tblPr><w:tblW w:type="dxa" w:w="5040"/></w:tblPr><w:tblGrid>' + grid + "</w:tblGrid>"]
    for r, row in enumerate(rows):
        cells = []
        for c, (text, w) in enumerate(zip(row, widths, strict=True)):
            edge = '<w:top w:val="single" w:color="000000" w:sz="4"/>' if r == 0 else ""
            edge += '<w:bottom w:val="single" w:color="000000" w:sz="4"/>' if r in (0, len(rows) - 1) else ""
            rpr = ("<w:b/><w:bCs/>" if r == 0 else "") + '<w:sz w:val="16"/><w:szCs w:val="16"/>'
            cells.append(f'<w:tc><w:tcPr><w:tcW w:type="dxa" w:w="{w}"/><w:tcBorders>{edge}</w:tcBorders>'
                         '<w:tcMar><w:left w:type="dxa" w:w="60"/><w:right w:type="dxa" w:w="60"/></w:tcMar></w:tcPr>'
                         f'<w:p><w:pPr><w:jc w:val="{"left" if c == 0 else "center"}"/><w:rPr><w:ins {_mark()}/></w:rPr>'
                         f"</w:pPr>{_run(text, rpr)}</w:p></w:tc>")
        out.append(f"<w:tr><w:trPr><w:cantSplit/><w:ins {_mark()}/></w:trPr>{''.join(cells)}</w:tr>")
    return "".join(out) + "</w:tbl>"


FIGURES = ROOT / "docs" / "research" / "figures"
SERVED = ROOT / "services" / "api" / "app" / "sati_models"
# file: (relationship id, docPr id) for the images this script adds, drawn by scripts/ieeefigures.py
IMAGES = {"nine-models.png": ("rIdClaude1", 9101), "rq5-rca.png": ("rIdClaude2", 9102)}


def _png_size(path: Path) -> tuple[int, int]:
    head = path.read_bytes()[:24]
    return int.from_bytes(head[16:20], "big"), int.from_bytes(head[20:24], "big")


def figure(name: str, number: int, text: str) -> str:
    """A tracked image paragraph and its caption, in the form of the paper's Fig. 1."""
    rid, pid = IMAGES[name]
    w_px, h_px = _png_size(FIGURES / name)
    cx = 3048000
    cy = round(cx * h_px / w_px)
    alt = escape(text, {'"': "&quot;"})
    drawing = (
        f'<w:drawing><wp:inline distT="0" distB="0" distL="0" distR="0"><wp:extent cx="{cx}" cy="{cy}"/>'
        f'<wp:effectExtent t="0" r="0" b="0" l="0"/><wp:docPr id="{pid}" name="Figure {number}" descr="{alt}" '
        f'title="Figure {number}"/><wp:cNvGraphicFramePr><a:graphicFrameLocks '
        'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" noChangeAspect="1"/></wp:cNvGraphicFramePr>'
        '<a:graphic xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"><a:graphicData '
        'uri="http://schemas.openxmlformats.org/drawingml/2006/picture"><pic:pic '
        'xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture"><pic:nvPicPr><pic:cNvPr id="0" '
        f'name="{name}" descr=""/><pic:cNvPicPr><a:picLocks noChangeAspect="1" noChangeArrowheads="1"/></pic:cNvPicPr>'
        f'</pic:nvPicPr><pic:blipFill><a:blip r:embed="{rid}" cstate="none"/><a:srcRect/><a:stretch><a:fillRect/>'
        f'</a:stretch></pic:blipFill><pic:spPr bwMode="auto"><a:xfrm><a:off x="0" y="0"/><a:ext cx="{cx}" '
        f'cy="{cy}"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom></pic:spPr></pic:pic></a:graphicData>'
        "</a:graphic></wp:inline></w:drawing>")
    image = (f'<w:p><w:pPr><w:keepNext/><w:spacing w:after="60" w:before="120"/><w:jc w:val="center"/>'
             f'<w:rPr><w:ins {_mark()}/></w:rPr></w:pPr><w:ins {_mark()}><w:r>{drawing}</w:r></w:ins></w:p>')
    small = '<w:sz w:val="16"/><w:szCs w:val="16"/>'
    return image + _para('<w:spacing w:after="140"/><w:jc w:val="both"/>', f"Fig. {number}. {text}", small)


def renumber(xml: str, old: str, new: str) -> str:
    """Change a figure number in the author's text as a tracked deletion and insertion."""
    pattern = re.compile(r'<w:r>(<w:rPr>(?:(?!</w:rPr>).)*</w:rPr>)?<w:t xml:space="preserve">([^<]*?)'
                         + re.escape(old) + r"([^<]*)</w:t></w:r>", re.S)

    def swap(m: re.Match) -> str:
        rpr, before, after = m.group(1) or "", m.group(2), m.group(3)

        def keep(t: str) -> str:
            return f'<w:r>{rpr}<w:t xml:space="preserve">{t}</w:t></w:r>' if t else ""

        return (keep(before) + f'<w:del {_mark()}><w:r>{rpr}<w:delText>{old}</w:delText></w:r></w:del>'
                + f'<w:ins {_mark()}><w:r>{rpr}<w:t>{new}</w:t></w:r></w:ins>' + keep(after))

    xml, count = pattern.subn(swap, xml)
    assert count, f"nothing to renumber: {old!r}"
    return xml


def live_examples(form: str) -> tuple[int, int]:
    """How many of a served tree model's held-out examples it gets right, scored as the API scores them."""
    from pashupatastra import trees

    m = json.loads((SERVED / f"{form}.json").read_text(encoding="utf-8"))
    right = sum((trees.predict(m, trees.row_from(m, e["features"])) >= m["threshold"]) == bool(e["truth"])
                for e in m["examples"])
    return right, len(m["examples"])


# --- the content ---------------------------------------------------------------

def content() -> dict[str, list[str]]:
    smd = j("shailaputri-smd.results.json")["mean_across_groups"]
    shail, pca = smd["shailaputri-v1 onset-weighted"], smd["pca per machine"]
    cic = j("chandraghanta.results.json")["datasets"]["cic"]
    ch0, ch2 = cic["detectors"]["chandraghanta-v0"], cic["detectors"]["chandraghanta-v2 (1% false-alarm budget)"]
    ch_random = cic["reference_random_split"]["chandraghanta-v0"]["f1"]
    kal, kal_bgl = j("kalaratri.results.json")["test"], j("kalaratri-bgl.results.json")["test"]
    maha = j("mahagauri.results.json")["pooled"]["mahagauri-v2 + 3σ agreement"]
    sidd = j("siddhidatri.results.json")["mean_across_groups"]
    skt, brt = j("skandamata.results.json")["test"], j("brahmacharini.results.json")["test"]
    ku = j("kushmanda.results.json")["sft"]["grounded"]
    kc = j("kushmanda-constrained.results.json")
    rca = j("sati-rca.results.json")["pooled"]["leave-one-system-out"]
    diag = j("rcaeval-diagnosis.results.json", WEB)
    ev = j("katyayani-events.results.json")["systems"]
    live = j("katyayani-live.results.json")["test"]
    s2r = j("katyayani-simtoreal.results.json")["test"]
    lin_b = brt.get("tf-idf logistic regression", {}).get("recall@1")
    lin_s = skt.get("tf-idf logistic regression", {}).get("hit@1")

    nine = [["Model", "Job", "Held-out result", "Baseline"],
            ["Shailaputri", "Server metric anomalies", f"F1 {f3(shail['f1'])}, {shail['false_alarms_per_1000']:.1f} FA/1k",
             f"PCA {f3(pca['f1'])}, {pca['false_alarms_per_1000']:.1f}"],
            ["Brahmacharini", "Behaviour → ATT&CK technique", f"R@1 {f3(brt['brahmacharini-v0']['recall@1'])}",
             f"BM25 {f3(brt['bm25']['recall@1'])}" + (f"; TF-IDF LR {f3(lin_b)}" if lin_b else "")],
            ["Chandraghanta", "Network intrusion, unseen days", f"F1 {f3(ch2['f1'])}", f"best-F1 thr. {f3(ch0['f1'])}"],
            ["Kushmanda", "Answer from passages, cite", f"ROUGE-L {f3(ku['kushmanda']['remediate']['rouge_l'])}",
             f"word overlap {f3(ku['lexical baseline']['remediate']['rouge_l'])}"],
            ["Skandamata", "Behaviour → mitigations", f"hit@1 {f3(skt['skandamata-v0']['hit@1'])}",
             f"BM25 {f3(skt['bm25 two-hop']['hit@1'])}" + (f"; TF-IDF LR {f3(lin_s)}" if lin_s else "")],
            ["Katyayani", "Root-cause service", f"RCA@1 {f3(rca['sati']['ac@1'])}", f"loudest {f3(rca['baseline']['ac@1'])}"],
            ["Kalaratri", "Log session anomalies (HDFS)", f"F1 {f3(kal['kalaratri-v0']['f1'])}",
             f"PCA {f3(kal['pca (Xu et al. 2009)']['f1'])}"],
            ["Mahagauri", "Is the incident over?", f"early {f3(maha['premature_rate'])}, confirmed {f3(maha['confirmed_rate'])}",
             "budget 0.050"],
            ["Siddhidatri", "Fuse three detectors", f"F1 {f3(sidd['siddhidatri-v0']['f1'])}, "
             f"{sidd['siddhidatri-v0']['false_alarms_per_1000']:.1f} FA/1k",
             f"Shailaputri {f3(sidd['shailaputri']['f1'])}, {sidd['shailaputri']['false_alarms_per_1000']:.1f}"]]

    d1, paired = diag["rca@1"], diag["paired_vs_katyayani"]
    llm = [["Diagnoser", "RCA@1", "Only Katy. right", "Only it right"],
           ["Katyayani", f3(d1["katyayani"]), "–", "–"],
           ["Llama 3 8B", f3(d1["llm:llama3"]), str(paired["llm:llama3"]["only_katyayani"]), str(paired["llm:llama3"]["only_other"])],
           ["Qwen2.5 7B", f3(d1["llm:qwen2.5:7b"]), str(paired["llm:qwen2.5:7b"]["only_katyayani"]),
            str(paired["llm:qwen2.5:7b"]["only_other"])],
           ["Loudest service", f3(d1["loudest"]), str(paired["loudest"]["only_katyayani"]), str(paired["loudest"]["only_other"])]]
    worst_p = max(p["holm_p"] for p in paired.values())

    claims = []
    if lin_b:
        claims.append(f"scores R@1 {f3(lin_b)} against Brahmacharini's {f3(brt['brahmacharini-v0']['recall@1'])}")
    if lin_s:
        claims.append(f"hit@1 {f3(lin_s)} against Skandamata's {f3(skt['skandamata-v0']['hit@1'])}")
    linear_claim = " and ".join(claims) or "rivals the retrieval and mitigation models on their own splits"
    fused = brt.get("brahmacharini-v0 + tf-idf (fused)")
    if fused:
        linear_claim += (f"; fusing it with Brahmacharini, with the weight chosen on validation sources, reaches "
                         f"R@1 {f3(fused['recall@1'])}")
    tr = MODELS / "brahmacharini-transformer.results.json"
    bigger = ""
    if tr.exists():
        t = json.loads(tr.read_text(encoding="utf-8"))["test"]["brahmacharini-v1 (transformer)"]
        bigger = (f"Bigger was not better: a 20M-parameter transformer encoder trained from scratch on the same "
                  f"split reached R@1 {f3(t['recall@1'])}, against {f3(brt['brahmacharini-v0']['recall@1'])} for "
                  "the bag-of-words encoder that is served. ")

    roles = [
        "Server metric anomalies (Shailaputri) scores each minute of a server's metrics. It is trained on SMD "
        "machine groups and tested on a group it never saw, and separately on NAB.",
        "Log session anomalies (Kalaratri) flags failing sessions from counts of their log templates, trained on "
        "the earlier part of HDFS and of BGL and tested on the later part.",
        "Network intrusion (Chandraghanta) flags attack flows. On CIC-IDS2017 it trains on Monday to Wednesday and "
        "is tested on Thursday and Friday, whose attack families it has not seen.",
        "Fusion (Siddhidatri) combines three detectors' scores into one alarm, on the same held-out servers.",
        "Root-cause service (Katyayani) ranks an incident's services by how likely each is the root, trained on "
        "RCAEval fault injections with whole systems held out.",
        "Behaviour to technique (Brahmacharini) maps an observed behaviour to its ATT&CK technique and retrieves "
        "the passages that ground Sati's answers. Its test procedures describe groups and tools unseen in training.",
        "Answer from passages (Kushmanda) is a 17M-parameter language model trained from scratch. It writes an "
        "answer from retrieved passages and declines when none answers.",
        f"Mitigations (Skandamata) ranks ATT&CK's {j('skandamata.results.json')['dataset']['mitigations']} "
        "mitigations for an observed behaviour, with the same split by source.",
        "Is it over (Mahagauri) reads a server's metrics after an incident and says, minute by minute, whether "
        "recovery has held. An early all-clear is the error that counts.",
    ]
    kal_ok, kal_n = live_examples("kalaratri")
    ch_ok, ch_n = live_examples("chandraghanta")

    names = {"live": "Live cluster", "ob": "Online Boutique", "ss": "Sock Shop"}
    s2r_rows = [["Held out", "Real-trained", "Simulator-trained", "Loudest"]]
    for key in ("live", "ob", "ss"):
        row = ev[key]
        s2r_rows.append([names[key], f3(row["events, real-trained"]["value"]), f3(row["events, Kaal-trained"]["value"]),
                         f3(row["loudest service"]["value"])])
    live_real = live["katyayani (trained on RCAEval, zero-shot)"]["rca@1"]["value"]

    return {
        "contribution": [body(
            "7) Nine models trained in this repository on public data, one for each stage of the loop, each "
            "evaluated with the split that keeps its test honest (by group, source, system, day or time) and "
            "against the strongest simple baseline, and served from the same exported weights that were evaluated.")],
        "abstract": [
            " The nine models Sati runs on are trained in the project itself. On a pre-declared sample of an "
            f"external root-cause benchmark, the project's ranker names the root first in {f3(d1['katyayani'])} of "
            f"cases, against {f3(d1['llm:llama3'])} and {f3(d1['llm:qwen2.5:7b'])} for two general language "
            "models given the same evidence."],
        "models": [
            subhead("C. Sati's Own Models"),
            body("Since this paper's first draft the agent no longer depends on general language models for its "
                 "judgements. Nine models are trained in the project's repository on public data, one for each part "
                 "of the loop, named for the nine forms of Navadurga. Each is evaluated with a split chosen so the "
                 "test measures something unseen: a held-out machine group, attacker, system, day or time, never a "
                 "random split where that would leak. Each is compared with the strongest simple baseline found, "
                 "and the results that went against the project are reported beside the rest (Table XI)."),
            body("Fig. 2 shows where each model works in the loop, each named by its job first."),
            figure("nine-models.png", 2, "Where the nine models work in the incident loop. Each box on the right "
                   "is one model, its job first and its name below. Dharma, the policy gate, is shaded and has no "
                   "model: whatever the models conclude, an action still needs Dharma's verdict."),
            *[body(t) for t in roles],
            caption("XI", "Sati's Models on Held-Out Data"),
            table(nine, [1000, 1440, 1340, 1260]),
            body("Two of the nine do not yet earn a decision on their own. Mahagauri, the recovery verifier, stays "
                 "within its safety budget only by rarely confirming recovery, and Siddhidatri's fusion of three "
                 "detectors buys recall with false alarms. Both remain advisory: a person decides."),
        ],
        "evaluation": [
            subhead("G. RQ5: The Project's Model Against General Language Models"),
            body("RQ5 asks whether a small model trained on real incidents diagnoses better than general language "
                 "models given the same evidence, on a benchmark this project did not write. The cases come from "
                 "RCAEval: fault injections on real microservice deployments, labelled by the injected root service. "
                 "A sample of 100 Online Boutique and Sock Shop cases was declared and hash-locked before any run. "
                 "Every diagnoser received the same per-service evidence, built without the label, and was scored by "
                 "the same harness. Katyayani was trained only on other systems. The language models ran through the "
                 "AI Gateway at temperature 0.2 (Table XII)."),
            caption("XII", "RQ5: Root Cause on 100 Pre-Declared RCAEval Cases"),
            table(llm, [1440, 1000, 1300, 1300]),
            body("Paired on the same cases with exact McNemar tests and Holm's correction, Katyayani is better than "
                 f"every other diagnoser (largest corrected p {worst_p:.1g}). Neither language model beats the "
                 "no-learning rule of naming the loudest service. The models are 7 to 8 billion parameters on CPU, "
                 "run once each; a frontier model behind the same Gateway is the obvious next arm."),
            figure("rq5-rca.png", 4, f"RQ5: the share of the {diag['cases']} pre-declared RCAEval cases in which "
                   "each diagnoser ranks the injected root service first, with 95% Wilson intervals. The "
                   "simulator-trained ranker is the RQ6 contrast."),
            subhead("H. RQ6: From a Simulator to Real Systems"),
            body("RQ6 asks whether a root-cause model trained on synthetic incidents works on real ones. The same "
                 "ranker was trained twice: on 50,000 incidents from the project's simulator, and on real "
                 "fault injections. It was tested, each system held out in turn, on two RCAEval systems and on a "
                 "third built for this test: 200 faults injected on a real Kubernetes cluster from a plan committed "
                 "before any run. The features are the event-level ones the deployed API can compute (Table XIII)."),
            caption("XIII", "RQ6: RCA@1, Trained on Real Incidents or on the Simulator"),
            table(s2r_rows, [1440, 1200, 1200, 1200]),
            body("The simulator taught topology-first reasoning, and on real faults the culprit is usually the "
                 "service that moved most. Trained on RCAEval alone, the ranker names the root first in "
                 f"{f3(live_real)} of the live-cluster incidents it never saw. Synthetic data is at most an "
                 "augmentation here, not a substitute. Zero-shot on raw RCAEval series, the simulator-trained "
                 f"ranker scores {f3(s2r['ob']['katyayani-kaal-v0 (zero-shot)']['rca@1']['value'])} on Online "
                 f"Boutique and {f3(s2r['ss']['katyayani-kaal-v0 (zero-shot)']['rca@1']['value'])} on Sock Shop."),
            subhead("I. RQ7: Detection, Verification and Language"),
            body(f"How a model is tested decides its headline. On CIC-IDS2017 the intrusion detector scores F1 "
                 f"{f3(ch_random)} on a random split and {f3(ch0['f1'])} when the test days hold only attack families "
                 f"it never saw. Its operating point mattered more than its architecture: with the threshold set for "
                 f"a 1% false-alarm rate on validation flows, unseen-day F1 rises to {f3(ch2['f1'])} and recall from "
                 f"{f3(ch0['recall'])} to {f3(ch2['recall'])}. On log sessions, Kalaratri reaches F1 "
                 f"{f3(kal['kalaratri-v0']['f1'])} on HDFS but {f3(kal_bgl['kalaratri-bgl-v0']['f1'])} on BGL, where "
                 "failures are rarer: one log dataset alone flatters the task."),
            body("Kushmanda, a 17M-parameter language model trained from scratch, answers from retrieved passages "
                 f"well (ROUGE-L {f3(ku['kushmanda']['remediate']['rouge_l'])} on required actions) and declines on "
                 f"{f3(ku['kushmanda']['unanswerable']['abstained'])} of questions no passage answers, but copies an "
                 f"exact technique identifier on only {f3(ku['kushmanda']['lookup']['exact_match'])} of lookups. "
                 "Constrained decoding makes every output valid and raises that to "
                 f"{f3(kc['constrained']['lookup']['exact_match'])}. In the system, identifiers come from retrieval "
                 "and the model writes around them."),
            subhead("J. Serving What Was Evaluated"),
            body("A model is evidence only if the deployed model is the evaluated one. The five gradient-boosted "
                 "models are exported as JSON and scored in plain Python in the API, with a test that the scores "
                 "equal LightGBM's, missing values included; the embedding models are served from int8 weights "
                 "checked to rank as the trained ones did. The live examples a visitor can run are held out from "
                 "training. Serving also exposed a failure the held-out score did not: asked in a user's words how "
                 "to defend against ransomware encrypting file shares, the mitigation model recommended one wrong "
                 "defence, while the retrieval model read the question correctly as Data Encrypted for Impact "
                 "(T1486). The deployed system now chains them, so every recommendation traces to a cited technique."),
            body(f"Kalaratri and Chandraghanta run live on held-out test examples, with the truth shown beside "
                 f"each answer. Kalaratri is right on {kal_ok} of {kal_n} log sessions. Chandraghanta is right on "
                 f"{ch_ok} of {ch_n} flows from the unseen days, two per family; the families it misses on the "
                 "test days it also misses live. Both are trained on research-use-only data and are served for "
                 "research use only."),
        ],
        "discussion": [body(
            "The project's own models add a second, measured claim. On a benchmark it did not write, a small ranker "
            "trained on real incidents outperforms two general language models given identical evidence (RQ5), and "
            "a simulator, however carefully built, was no substitute for real data (RQ6). The models that did not "
            "earn a decision on their own are reported with the same prominence and remain advisory.")],
        "limitations": [body(
            "The models carry their own threats. A plain TF-IDF and logistic regression baseline, added after the "
            "public notebooks found it, " + linear_claim +
            "; a neural model is worth serving only where it beats the strongest simple baseline. " + bigger +
            "Gradient-boosted "
            "results move by a few hundredths between CI machines, so they are reported with seed spreads where it "
            "matters. The live cluster's steady load leaves near-flat baselines, and its 200 incidents were built "
            "by the same project; RCAEval is the independent check.")],
        "conclusion": [body(
            "Part of that work is now done. Root-cause accuracy has been measured on an external benchmark against "
            "real language models (RQ5), and sim-to-real on three systems (RQ6). What remains is the 20 labelled "
            "PIB incidents with answer keys written before any run, the head-to-head on them at N ≥ 3, and the "
            "escalation analysis they make possible.")],
        "availability": [body(
            "The nine models, their datasets and a reproducing notebook for each are published on Kaggle under the "
            "owner preetraval4518071604; models trained on research-use-only data are released for research use only.")],
    }


ANCHORS = {
    # key: (paragraph whose text starts with this, insert "before" or "after", or "append" into it)
    "abstract": ("Abstract.", "append"),
    "contribution": ("6) PIB, a 104 scenario benchmark", "after"),
    "models": ("VIII. Bounded Autonomy", "before"),
    "evaluation": ("XV. Discussion", "before"),
    "discussion": ("On novelty", "after"),
    "limitations": ("XVII. Ethical Considerations", "before"),
    "conclusion": ("The work needed to close that gap", "after"),
    "availability": ("The source code, the PIB scenarios", "after"),
}


def apply(xml: str, parts: dict[str, list[str]]) -> str:
    body_start = xml.index("<w:body>")
    for key, (start, where) in ANCHORS.items():
        spans = [(m.start(), m.end()) for m in re.finditer(r"<w:p[ >].*?</w:p>", xml[body_start:], flags=re.S)]
        hit = None
        for a, b in spans:
            text = "".join(re.findall(r"<w:t[^>]*>([^<]*)</w:t>", xml[body_start + a : body_start + b])).strip()
            if text.startswith(start):
                hit = (body_start + a, body_start + b)
                break
        assert hit, f"anchor not found: {start!r}"
        a, b = hit
        if where == "append":
            xml = xml[: b - len("</w:p>")] + "".join(_run(t) for t in parts[key]) + xml[b - len("</w:p>"):]
        elif where == "after":
            xml = xml[:b] + "".join(parts[key]) + xml[b:]
        else:
            xml = xml[:a] + "".join(parts[key]) + xml[a:]
    return xml


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--source", type=Path, default=None,
                        help="the untracked original; default: the paper as committed in bcc5849 (7 Oct 2026)")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.source is None:
        # Rerunnable: always start from the untracked original, so numbers can be refreshed.
        import subprocess

        blob = subprocess.run(["git", "show", f"{ORIGINAL}:docs/research/Pashupatastra IEEE Paper.docx"],
                              cwd=ROOT, capture_output=True, check=True).stdout
        args.source = Path(tempfile.mkdtemp()) / "original.docx"
        args.source.write_bytes(blob)
    with zipfile.ZipFile(args.source) as z:
        xml = z.read("word/document.xml").decode("utf-8")
        assert f'w:author="{AUTHOR}"' not in xml, "already updated: start from the untracked original"
        names = z.namelist()
        blobs = {n: z.read(n) for n in names}
    # The new models figure is Fig. 2, so the author's Fig. 2 becomes Fig. 3.
    xml = renumber(xml, "Fig. 2", "Fig. 3")
    blobs["word/document.xml"] = apply(xml, content()).encode("utf-8")
    rels = blobs["word/_rels/document.xml.rels"].decode("utf-8")
    for name, (rid, _) in IMAGES.items():
        part = f"word/media/claude-{name}"
        blobs[part] = (FIGURES / name).read_bytes()
        names.append(part)
        rels = rels.replace("</Relationships>", f'<Relationship Id="{rid}" Type="http://schemas.openxmlformats.org/'
                            f'officeDocument/2006/relationships/image" Target="media/claude-{name}"/></Relationships>')
    blobs["word/_rels/document.xml.rels"] = rels.encode("utf-8")
    tmp = Path(tempfile.mkdtemp()) / "paper.docx"
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as out:
        for n in names:
            out.writestr(n, blobs[n])
    shutil.copy(tmp, args.out)
    print("wrote", args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
