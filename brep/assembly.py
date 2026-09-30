"""Baugruppe: Features aller Gruppen einsammeln und pro Teil in der festen Bool-Reihenfolge verrechnen.

Reihenfolge je Teil (docs/geometrie_definition.md, Kap. 1): base ∪ add − cavity ∪ attach − cut, danach `details`.
Jede Gruppe wird nur mit Skelett + eigener Gruppe gebaut; Ergebnisse werden pro Gruppe gecacht, damit eine
Änderung in einer Gruppe nur diese Gruppe neu rechnet.
"""
from __future__ import annotations

import time

from build123d import Part

from .features import PARTS, Feature
from .groups import BUILDERS
from .groups.details import apply_details
from .skeleton import Skeleton
from .spec import Spec

_group_cache: dict[tuple, list[Feature]] = {}


def build_features(spec: Spec, timings: dict | None = None) -> list[Feature]:
    sk_params = spec.group("skeleton")
    sk = Skeleton.from_params(sk_params)
    feats: list[Feature] = []
    for name, builder in BUILDERS.items():
        g = spec.group(name)
        key = (sk_params.key(), g.key())
        t0 = time.perf_counter()
        if key not in _group_cache:
            _group_cache[key] = builder(sk, g)
        if timings is not None:
            timings[name] = time.perf_counter() - t0
        feats += _group_cache[key]
    return feats


def combine(feats: list[Feature]) -> dict[str, Part]:
    parts: dict[str, Part] = {}
    for part in PARTS:
        by_role = {r: [f.shape for f in feats if f.part == part and f.role == r]
                   for r in ("base", "add", "cavity", "attach", "cut")}
        if not by_role["base"]:
            continue
        # Bewusst nacheinander: fuse(*viele) liefert unter OCCT 8.0.1 bei den Kielen/Heckflossen ein
        # falsches Ergebnis (2 Körper, 44'090 statt 303'579 mm³) – siehe docs/befunde_brep.md.
        body = by_role["base"][0]
        for add in by_role["base"][1:] + by_role["add"]:
            body = body.fuse(add)
        for cav in by_role["cavity"]:
            body = body - cav
        for att in by_role["attach"]:
            body = body.fuse(att)
        body = body.clean()
        for cut in by_role["cut"]:
            body = body - cut
        parts[part] = body
    return parts


def build(spec: Spec) -> dict:
    """Ganzes Modell. Rückgabe: parts, notes, timing (s) je Gruppe und gesamt."""
    t0 = time.perf_counter()
    timings: dict[str, float] = {}
    feats = build_features(spec, timings)
    t1 = time.perf_counter()
    parts = combine(feats)
    t2 = time.perf_counter()
    sk = Skeleton.from_params(spec.group("skeleton"))
    parts, notes = apply_details(sk, spec.group("details"), parts)
    t3 = time.perf_counter()
    return {"parts": parts, "features": feats, "notes": notes,
            "timing": {"groups_s": timings, "features_s": t1 - t0, "booleans_s": t2 - t1, "details_s": t3 - t2,
                       "total_s": t3 - t0}}
