"""One process of the live stack (RP-19): a service, the load generator, or the collector.

    python app.py service    # env SERVICE, DOWNSTREAM (comma list), RELEASE
    python app.py load       # env TARGET, RPS
    python app.py collect    # env SERVICES (comma list), INTERVAL

Standard library only, so it runs from a ConfigMap on the stock python image
with nothing built. The PIB stack is pause containers, which report replica
counts and nothing else; Sati-RCA reads service metrics, so the sim-to-real set
needs services that have them.

What each service reports is what a real one would expose: request rate,
error rate, the 90th percentile of its own latency, and its container's CPU
and memory. CPU and memory are read from the container's cgroup, not the
process, so a fault process started beside the service counts against it, as
it would on a host.
"""

from __future__ import annotations

import json
import os
import random
import sys
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

CGROUP = "/sys/fs/cgroup"
PORT = 8080


def usage(root: str = CGROUP) -> tuple[float, float, str]:
    """(CPU seconds used, memory bytes, source) for this container.

    cgroup v2 first. If it is not there, the process's own figures, and the
    record says which, because the two are not the same measurement.
    """
    try:
        with open(f"{root}/cpu.stat") as f:
            usec = next(int(line.split()[1]) for line in f if line.startswith("usage_usec"))
        with open(f"{root}/memory.current") as f:
            return usec / 1e6, float(f.read()), "cgroup"
    except (OSError, StopIteration, ValueError):
        import resource  # POSIX only; the service always runs on Linux

        r = resource.getrusage(resource.RUSAGE_SELF)
        return r.ru_utime + r.ru_stime, r.ru_maxrss * 1024.0, "process"


def p90(values: list[float]) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    return s[min(len(s) - 1, int(0.9 * len(s)))]


class State:
    lock = threading.Lock()
    requests = 0
    errors = 0
    latencies: list[float] = []
    delay_ms = 0


def work(downstream: list[str], release: str) -> bool:
    """One request: a little CPU, then each dependency in turn."""
    h = 0
    for i in range(3000):
        h = (h * 31 + i) % 1_000_003
    ok = True
    for name in downstream:
        try:
            with urllib.request.urlopen(f"http://{name}:{PORT}/work", timeout=2) as r:
                ok &= r.status == 200
        except Exception:  # a failed dependency is an error here, whatever the cause
            ok = False
    if release == "bad" and random.random() < 0.3:
        ok = False
    return ok


class Handler(BaseHTTPRequestHandler):
    downstream: list[str] = []
    release = "good"

    def log_message(self, *args: object) -> None:
        pass

    def _send(self, status: int, body: dict) -> None:
        data = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:  # noqa: N802 - the stdlib's name
        url = urlparse(self.path)
        if url.path == "/work":
            started = time.monotonic()
            if State.delay_ms:
                time.sleep(State.delay_ms / 1000)
            ok = work(self.downstream, self.release)
            took = (time.monotonic() - started) * 1000
            with State.lock:
                State.requests += 1
                State.errors += 0 if ok else 1
                State.latencies.append(took)
            self._send(200 if ok else 500, {"ok": ok})
        elif url.path == "/metrics":
            cpu, mem, source = usage()
            with State.lock:
                lat, State.latencies = State.latencies, []
                body = {"requests": State.requests, "errors": State.errors, "latency_p90": p90(lat),
                        "cpu_seconds": cpu, "mem_bytes": mem, "source": source}
            self._send(200, body)
        elif url.path == "/fault":
            # Application-level delay, as a service mesh's fault injection does it.
            State.delay_ms = int(parse_qs(url.query).get("delay_ms", ["0"])[0])
            self._send(200, {"delay_ms": State.delay_ms})
        elif url.path == "/healthz":
            self._send(200, {"ok": True})
        else:
            self._send(404, {"error": url.path})


def serve() -> None:
    Handler.downstream = [s for s in os.environ.get("DOWNSTREAM", "").split(",") if s]
    Handler.release = os.environ.get("RELEASE", "good")
    ThreadingHTTPServer(("", PORT), Handler).serve_forever()


def load() -> None:
    target, rps = os.environ["TARGET"], float(os.environ.get("RPS", "10"))
    threads = 4

    def loop() -> None:
        while True:
            started = time.monotonic()
            try:
                urllib.request.urlopen(f"{target}/work", timeout=5).close()
            except Exception:  # the errors are the services' to count, not the client's
                pass
            time.sleep(max(0.0, threads / rps * random.uniform(0.8, 1.2) - (time.monotonic() - started)))

    for _ in range(threads):
        threading.Thread(target=loop, daemon=True).start()
    while True:
        time.sleep(3600)


def collect() -> None:
    """Scrape every service each interval and print one JSON line per service.

    Counters become rates here. A counter that went down means the process
    restarted (a new release does that), so the previous reading is treated as
    zero rather than producing a negative rate.
    """
    services = os.environ["SERVICES"].split(",")
    interval = float(os.environ.get("INTERVAL", "5"))
    last: dict[str, tuple[float, dict]] = {}
    while True:
        tick = time.time()
        for svc in services:
            try:
                with urllib.request.urlopen(f"http://{svc}:{PORT}/metrics", timeout=2) as r:
                    m = json.load(r)
            except Exception:
                print(json.dumps({"t": int(tick), "service": svc, "up": 0}), flush=True)
                continue
            now = time.time()
            if svc in last:
                then, prev = last[svc]
                dt = max(now - then, 1e-6)
                restarted = m["requests"] < prev["requests"]
                base = {"requests": 0, "errors": 0, "cpu_seconds": 0.0} if restarted else prev
                d_req = m["requests"] - base["requests"]
                d_err = m["errors"] - base["errors"]
                d_cpu = m["cpu_seconds"] - base["cpu_seconds"]
                print(json.dumps({
                    "t": int(tick), "service": svc, "up": 1,
                    "cpu": round(max(d_cpu, 0.0) / dt, 4),
                    "mem": m["mem_bytes"],
                    "latency-90": round(m["latency_p90"], 2),
                    "request": round(d_req / dt, 3),
                    "error": round(d_err / d_req, 4) if d_req > 0 else 0.0,
                    "source": m["source"],
                }), flush=True)
            last[svc] = (now, m)
        time.sleep(max(0.0, interval - (time.time() - tick)))


if __name__ == "__main__":
    {"service": serve, "load": load, "collect": collect}[sys.argv[1]]()
