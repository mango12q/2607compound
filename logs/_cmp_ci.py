# -*- coding: utf-8 -*-
"""Print ALL-equivalent return periods with bootstrap CIs for several tags side by side.

Reads results/tables/phase6_gev{tag}.json (structure produced by phase6_cesm.cmd_gev).
Purpose: decide whether the remaining marine tail gap (0.56-0.68x at 50/100 y) is
sampling noise of the 440 model-year sample or a real residual.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from python.phase6_cesm import _force_utf8_stdout  # noqa: E402

_force_utf8_stdout()

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TAGS = sys.argv[1:] or ["_v7", "_v10", "_v12w50", "_v12w60", "_v12w89"]
PANELS = ("marine", "terrestrial", "compound")
RPS = ("5", "10", "20", "50", "100")
PAPER = {
    "marine": {"5": 2.30, "10": 3.80, "20": 6.30, "50": 13.4, "100": 24.0},
    "terrestrial": {"5": 1.26, "10": 1.46, "20": 1.75, "50": 2.44, "100": 3.26},
    "compound": {"5": 1.96, "10": 2.56, "20": 3.50, "50": 5.14, "100": 7.85},
}


def load(tag):
    path = os.path.join(BASE, "results", "tables", "phase6_gev%s.json" % tag)
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def fmt_ci(node):
    lo, hi = node.get("ci_lower"), node.get("ci_upper")
    return "[%7.3f,%9.3f]" % (lo, hi)


def main():
    data = {t: load(t) for t in TAGS}
    for tag in TAGS:
        if data[tag] is None:
            print("!! %s: json missing" % tag)

    for panel in PANELS:
        print("=" * 100)
        print(panel.upper())
        head = "  %-6s %8s |" % ("rp", "paper")
        for tag in TAGS:
            head += " %-28s |" % tag
        print(head)
        for rp in RPS:
            line = "  %-6s %8.2f |" % (rp, PAPER[panel][rp])
            for tag in TAGS:
                d = data[tag]
                if d is None or panel not in d:
                    line += " %-28s |" % "-"
                    continue
                node = d[panel]["all"][rp]
                med = node["median"]
                lo, hi = node.get("ci_lower"), node.get("ci_upper")
                inside = ""
                if lo is not None and hi is not None:
                    inside = "IN" if (lo <= PAPER[panel][rp] <= hi) else "out"
                line += " %7.3f %-19s %-3s|" % (med, fmt_ci(node), inside)
            print(line)
        # ratio of 100y to 5y (tail steepness)
        line = "  %-6s %8s |" % ("r100/5", "-")
        for tag in TAGS:
            d = data[tag]
            if d is None or panel not in d:
                line += " %-28s |" % "-"
                continue
            a5 = d[panel]["all"]["5"]["median"]
            a100 = d[panel]["all"]["100"]["median"]
            line += " %-28s |" % ("%.2f" % (a100 / a5 if a5 else float("nan")))
        print(line)

    print("=" * 100)
    print("FixGHG return levels (days/yr) + 100y CI")
    for panel in PANELS:
        for tag in TAGS:
            d = data[tag]
            if d is None or panel not in d:
                continue
            f = d[panel]["fixghg"]
            vals = " ".join("%9.2f" % f[rp]["median"] if f[rp]["median"] < 1e6 else "%9.2e" % f[rp]["median"] for rp in RPS)
            print("  %-12s %-9s %s   ci100=%s" % (panel, tag, vals, fmt_ci(f["100"])))


if __name__ == "__main__":
    main()
