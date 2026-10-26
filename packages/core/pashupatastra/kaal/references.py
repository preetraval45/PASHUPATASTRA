"""Topologies Kaal must never reproduce: the systems its models are tested on.

RCAEval's Online Boutique and Sock Shop are the sim-to-real test (RP-24).
They are written here once and used twice:

* **the RP-18 contamination guard** fails if a generated topology has the same
  shape as one of them;
* **`sati.rca.simtoreal`** builds its features from them.

Authored from each project's published architecture: Google's
microservices-demo README for Online Boutique, and Weaveworks' Sock Shop
design. Online Boutique's graph is checked against RCAEval's traces on every
sim-to-real run. Sock Shop has no traces in RCAEval, so its graph is
unchecked. Train Ticket (64 components) is not authored, because it would be
a guess. Auxiliary components (PassthroughCluster, main) have no edges and
are left out.
"""

from __future__ import annotations

from pashupatastra.events import EntityKind

REFERENCES: dict[str, dict[str, object]] = {
    "ob": {
        "name": "Online Boutique (RCAEval)",
        "calls": [
            ("frontend-external", "frontend"),
            *[("frontend", s) for s in ("adservice", "cartservice", "checkoutservice", "currencyservice",
                                        "productcatalogservice", "recommendationservice", "shippingservice")],
            *[("checkoutservice", s) for s in ("cartservice", "currencyservice", "emailservice", "paymentservice",
                                               "productcatalogservice", "shippingservice")],
            ("recommendationservice", "productcatalogservice"),
            ("cartservice", "redis"),
        ],
        "layer": {"frontend-external": "edge", "frontend": "edge", "checkoutservice": "api",
                  "recommendationservice": "api", "redis": "store"},
        "kind": {"redis": EntityKind.CACHE},
    },
    "ss": {
        "name": "Sock Shop (RCAEval)",
        "calls": [
            *[("front-end", s) for s in ("catalogue", "carts", "orders", "user", "session-db")],
            *[("orders", s) for s in ("carts", "user", "payment", "shipping", "orders-db")],
            ("shipping", "rabbitmq"), ("queue-master", "rabbitmq"), ("rabbitmq-exporter", "rabbitmq"),
            ("catalogue", "catalogue-db"), ("carts", "carts-db"), ("user", "user-db"),
        ],
        "layer": {"front-end": "edge", "orders": "api", "carts-db": "store", "catalogue-db": "store",
                  "orders-db": "store", "user-db": "store", "session-db": "store", "rabbitmq": "store"},
        "kind": {"carts-db": EntityKind.DATABASE, "catalogue-db": EntityKind.DATABASE,
                 "orders-db": EntityKind.DATABASE, "user-db": EntityKind.DATABASE,
                 "session-db": EntityKind.CACHE, "rabbitmq": EntityKind.QUEUE},
    },
}


def nodes(system: str) -> list[tuple[str, str, str]]:
    """(name, layer, kind) for every component in a reference graph."""
    ref = REFERENCES[system]
    names = sorted({n for edge in ref["calls"] for n in edge})  # type: ignore[union-attr]
    layer, kind = ref["layer"], ref["kind"]
    return [(n, layer.get(n, "backend"), kind.get(n, EntityKind.SERVICE).value) for n in names]  # type: ignore[union-attr]
