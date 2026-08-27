import re
import shlex
from collections import defaultdict, deque
from pathlib import Path


def parse_pipeline_star(text):
    """Extract process and edge tables from a pipeline STAR file."""
    need_proc  = {"_rlnPipeLineProcessName", "_rlnPipeLineProcessTypeLabel",
                  "_rlnPipeLineProcessStatusLabel"}
    need_efrom = {"_rlnPipeLineEdgeFromNode", "_rlnPipeLineEdgeProcess"}
    need_eto   = {"_rlnPipeLineEdgeProcess",  "_rlnPipeLineEdgeToNode"}
    out = {"processes": [], "e_from": [], "e_to": []}
    lines = text.splitlines()
    i, n = 0, len(lines)
    while i < n:
        if lines[i].strip().lower() == "loop_":
            i += 1
            cols = []
            while i < n and lines[i].lstrip().startswith("_"):
                cols.append(lines[i].split()[0]); i += 1
            rows = []
            while i < n and lines[i].strip() \
                    and not lines[i].lstrip().startswith("_") \
                    and not lines[i].strip().lower().startswith("data_") \
                    and lines[i].strip().lower() != "loop_":
                try:
                    parts = shlex.split(lines[i].strip(), posix=True)
                except ValueError:
                    parts = re.split(r"\s+", lines[i].strip())
                if len(parts) >= len(cols):
                    rows.append(parts[:len(cols)])
                i += 1
            cset = set(cols)
            make = lambda: [dict(zip(cols, r)) for r in rows]
            if need_proc.issubset(cset):  out["processes"].extend(make())
            elif need_efrom.issubset(cset): out["e_from"].extend(make())
            elif need_eto.issubset(cset):   out["e_to"].extend(make())
            continue
        i += 1
    return out


def load_pipeline(project):
    """Read default_pipeline.star and per-job star files under `project`
    (a pathlib.Path). Returns (procs, node_to_prod, proc_to_in)."""
    def read(p):
        try:
            return Path(p).read_text(encoding="utf-8", errors="ignore")
        except Exception:
            return ""

    procs = set()
    e_from, e_to = [], []

    def ingest(text):
        t = parse_pipeline_star(text)
        for p in t["processes"]:
            name = p.get("_rlnPipeLineProcessName", "").strip().rstrip("/")
            if name:
                procs.add(name)
        e_from.extend(t["e_from"])
        e_to.extend(t["e_to"])

    ps = project / "default_pipeline.star"
    if ps.exists():
        ingest(read(ps))
    for fam in sorted([d for d in project.iterdir() if d.is_dir()]):
        for jd in fam.glob("job*/"):
            for fn in ("job_pipeline.star", "default_pipeline.star"):
                f = jd / fn
                if f.exists():
                    ingest(read(f))

    node_to_prod = defaultdict(set)
    proc_to_in   = defaultdict(set)
    for r in e_to:
        proc = r.get("_rlnPipeLineEdgeProcess", "").strip().rstrip("/")
        node = r.get("_rlnPipeLineEdgeToNode",  "").strip()
        if proc and node:
            node_to_prod[node].add(proc)
    for r in e_from:
        node = r.get("_rlnPipeLineEdgeFromNode", "").strip()
        proc = r.get("_rlnPipeLineEdgeProcess",  "").strip().rstrip("/")
        if proc and node:
            proc_to_in[proc].add(node)

    return procs, node_to_prod, proc_to_in


def build_parents(procs, node_to_prod, proc_to_in):
    parents = {p: set() for p in procs}
    for proc in procs:
        for node in proc_to_in.get(proc, ()):
            for par in node_to_prod.get(node, ()):
                if par != proc:
                    parents[proc].add(par)
    return parents


def upstream(selected, parents):
    """Return all upstream jobs of selected (inclusive)."""
    keep = {selected}
    q = deque([selected])
    while q:
        u = q.popleft()
        for p in parents.get(u, ()):
            if p not in keep:
                keep.add(p)
                q.append(p)
    sub = {k: {p for p in v if p in keep}
           for k, v in parents.items() if k in keep}
    return keep, sub


def layers(selected, parents):
    """Assign BFS depth to each job → chronological layers root→selected."""
    job_num_re = re.compile(r"job(\d+)$")

    def job_num(j):
        m = job_num_re.search(j)
        return int(m.group(1)) if m else 10 ** 9

    memo = {}

    def depth(u):
        if u in memo:
            return memo[u]
        if not parents.get(u):
            memo[u] = 0
            return 0
        memo[u] = 1 + max(depth(p) for p in parents[u])
        return memo[u]

    for u in parents:
        depth(u)

    max_d = max(memo.values()) if memo else 0
    out = [[] for _ in range(max_d + 1)]
    for j, d in memo.items():
        out[d].append(j)
    for layer in out:
        layer.sort(key=lambda j: (job_num(j), j))
    return out
