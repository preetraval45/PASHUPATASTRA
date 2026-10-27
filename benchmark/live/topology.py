"""The live stack's shape, and the Kubernetes objects that build it.

Eight services, authored for this set and checked (testlive.py) to differ in
shape from every topology a model here is trained or tested on: Online
Boutique, Sock Shop, the PIB reference stack, and Kaal's generated graphs.
A fixed, known graph is the point: the call edges are the stack's own
configuration (each service's DOWNSTREAM), so unlike RCAEval's they are not
authored from a README, they are what runs.
"""

from __future__ import annotations

from pathlib import Path

IMAGE = "python:3.12-slim"
APP = Path(__file__).with_name("app.py")

CALLS: list[tuple[str, str]] = [
    ("web", "orders"), ("web", "search"), ("web", "account"),
    ("orders", "stock"), ("orders", "billing"), ("orders", "account"),
    ("search", "stock"), ("billing", "ledger"),
    ("stock", "db"), ("ledger", "db"), ("account", "db"),
]
SERVICES = sorted({s for edge in CALLS for s in edge})
LAYER = {"web": "edge", "orders": "api", "db": "store"}
KIND = {"db": "database"}

#: In the form `pashupatastra.kaal.references.REFERENCES` uses, for the feature mapping.
GRAPH = {"name": "live stack (RP-19)", "calls": CALLS, "layer": LAYER, "kind": {}}


def downstream(service: str) -> list[str]:
    return [b for a, b in CALLS if a == service]


def _deployment(name: str, mode: str, env: dict[str, str], cpu: str = "300m", mem: str = "256Mi") -> str:
    env_yaml = "".join(f"            - {{name: {k}, value: \"{v}\"}}\n" for k, v in env.items())
    probe = (
        "          readinessProbe:\n"
        "            httpGet: {path: /healthz, port: 8080}\n"
        "            periodSeconds: 2\n"
    ) if mode == "service" else ""
    return f"""---
apiVersion: apps/v1
kind: Deployment
metadata: {{name: {name}, labels: {{app: {name}, stack: live}}}}
spec:
  replicas: 1
  selector: {{matchLabels: {{app: {name}}}}}
  template:
    metadata: {{labels: {{app: {name}}}}}
    spec:
      terminationGracePeriodSeconds: 0
      containers:
        - name: {name}
          image: {IMAGE}
          command: ["python", "/app/app.py", "{mode}"]
          env:
            - {{name: PYTHONUNBUFFERED, value: "1"}}
{env_yaml}          resources:
            requests: {{cpu: 20m, memory: 32Mi}}
            limits: {{cpu: {cpu}, memory: {mem}}}
{probe}          volumeMounts: [{{name: app, mountPath: /app}}]
      volumes: [{{name: app, configMap: {{name: live-app}}}}]
"""


def manifest(namespace: str) -> str:
    app = APP.read_text(encoding="utf-8")
    parts = [
        f"apiVersion: v1\nkind: Namespace\nmetadata: {{name: {namespace}}}\n",
        "---\napiVersion: v1\nkind: ConfigMap\nmetadata: {name: live-app}\ndata:\n  app.py: |\n"
        + "".join(f"    {line}\n" if line else "\n" for line in app.splitlines()),
    ]
    for s in SERVICES:
        parts.append(_deployment(s, "service", {"SERVICE": s, "DOWNSTREAM": ",".join(downstream(s)), "RELEASE": "good"}))
        parts.append(f"---\napiVersion: v1\nkind: Service\nmetadata: {{name: {s}}}\n"
                     f"spec: {{selector: {{app: {s}}}, ports: [{{port: 8080, targetPort: 8080}}]}}\n")
    parts.append(_deployment("loadgen", "load", {"TARGET": "http://web:8080", "RPS": "15"}))
    parts.append(_deployment("collector", "collect", {"SERVICES": ",".join(SERVICES), "INTERVAL": "5"}))
    # Every object but the namespace lands in it.
    return parts[0] + "".join(p.replace("metadata: {name:", f"metadata: {{namespace: {namespace}, name:", 1)
                              for p in parts[1:])
