"""The v1 targets (SPEC §19.3, §10.9) as data, for the eval report and the Eval page (D-139).

``scripts/check_targets.py`` (edited by humans only) enforces the same numbers in the autopilot
gate; ``tests/unit/test_eval_targets.py`` keeps the two in step. If that test fails after a human
edit of the script, update ``TARGETS`` here: never edit the script from code.

Each target names the metric key in the eval JSON (``metrics``), the operator, the value, a label,
its SPEC section and the phase that owns it. ``report_only`` targets are measured and shown but
never block (latency, D-060); ``pending`` names the phase that produces a metric not yet
measured. ``fmt`` says how the Markdown report and the Eval page write the value.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class Target:
    key: str
    op: str  # ">=" or "<="
    value: float
    label: str
    spec: str
    phase: int
    fmt: str = "ratio"  # ratio | pct | signed | m | ms
    report_only: bool = False
    pending: str | None = None

    def met(self, v: float | None) -> bool | None:
        """True or False against the target; None when the metric is missing."""
        if v is None:
            return None
        return v >= self.value if self.op == ">=" else v <= self.value

    def text(self) -> str:
        """The target in words for a table cell, e.g. "≥ 0.80", "≤ 5%", "≤ 400 m"."""
        sym = "≥" if self.op == ">=" else "≤"
        v = self.value
        if self.fmt == "pct":
            num = f"{v:.0%}"
        elif self.fmt == "signed":
            num = f"{v:+.2f}"
        elif self.fmt == "m":
            num = f"{v:,.0f} m"
        elif self.fmt == "ms":
            num = f"{v:,.0f} ms"
        else:
            num = f"{v:.2f}"
        return f"{sym} {num}"


TARGETS: tuple[Target, ...] = (
    Target("recall_at_5_t120", ">=", 0.80, "Recall@5 at T = 120 s", "§19.3", 4),
    Target(
        "dtw_lift", ">=", 0.10, "DTW lift over the Euclidean baseline", "§19.3", 4, fmt="signed"
    ),
    Target(
        "copycat_first_t120", "<=", 0.05, "Copycat-first rate at T = 120 s", "§19.3", 4, fmt="pct"
    ),
    Target(
        "latency_prefilter_p95_ms",
        "<=",
        50.0,
        "Prefilter p95",
        "§10.9",
        4,
        fmt="ms",
        report_only=True,
    ),
    Target(
        "latency_dtw_p95_ms",
        "<=",
        800.0,
        "DTW re-rank of 50 candidates p95",
        "§10.9",
        4,
        fmt="ms",
        report_only=True,
    ),
    Target(
        "latency_end_to_end_p95_ms",
        "<=",
        1500.0,
        "End-to-end live update p95",
        "§10.9",
        4,
        fmt="ms",
        report_only=True,
    ),
    Target("report_linkage", ">=", 0.70, "Report linkage", "§19.3", 5),
    Target(
        "forecast_median_t90_m",
        "<=",
        400.0,
        "Forecast median error at T = 90 s",
        "§19.3",
        5,
        fmt="m",
    ),
    Target(
        "time_to_match_t90", ">=", 0.70, "Time to match: top 3 by T = 90 s", "§19.3", 9, fmt="pct"
    ),
    Target("swarm_top1", ">=", 0.80, "Swarm top-1", "§19.3", 9, pending="phase 9"),
)

BY_KEY = {t.key: t for t in TARGETS}


def target_text(key: str) -> str:
    """``BY_KEY[key].text()``, for the Markdown report's target column."""
    return BY_KEY[key].text()


def targets_json() -> list[dict]:
    """The targets for the eval JSON (``targets``), in ``TARGETS`` order."""
    return [{**asdict(t), "text": t.text()} for t in TARGETS]
