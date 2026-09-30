"""Gruppen-Unabhängigkeit (Skelett-Methode) und Gültigkeit – ausführbar mit pytest oder direkt:

    python -m brep.tests.test_groups

1. Ändert man einen Parameter einer Nicht-Skelett-Gruppe, ändern sich nur die Features dieser Gruppe.
2. Jeder Parameter baut auf min und max ein gültiges Modell (alle anderen auf Referenzwert).
"""
from __future__ import annotations

import sys

from brep.assembly import build, build_features
from brep.spec import Spec


def fingerprint(shape) -> tuple:
    b = shape.bounding_box()
    return (round(shape.volume, 3), round(shape.area, 3), round(b.min.X, 3), round(b.max.X, 3), round(b.min.Z, 3),
            round(b.max.Z, 3))


def features_by_name(spec: Spec) -> dict:
    return {f.name: (f.group, fingerprint(f.shape)) for f in build_features(spec)}


def mid_value(info: dict):
    v = info["value"]
    lo, hi = info["min"], info["max"]
    new = (v + hi) / 2 if hi > v else (v + lo) / 2
    return int(round(new)) if all(float(info.get(k, 0)).is_integer() for k in ("value", "min", "max", "step")) else new


def test_group_independence():
    spec = Spec.load()
    base = features_by_name(spec)
    problems = []
    for g, p, info in spec.iter_params():
        if g in ("skeleton", "details"):
            continue
        new = mid_value(info)
        if new == info["value"]:
            continue
        try:
            changed = features_by_name(spec.with_overrides({f"{g}.{p}": new}))
        except Exception as exc:  # noqa: BLE001
            problems.append(f"{g}.{p}={new}: Aufbau fehlgeschlagen ({type(exc).__name__})")
            continue
        for name, (grp, fp) in changed.items():
            if grp != g and base.get(name, (None, None))[1] != fp:
                problems.append(f"{g}.{p}={new} veraendert fremdes Feature {name} ({grp})")
    assert not problems, "\n".join(problems)


def test_min_max_valid():
    spec = Spec.load()
    bad = []
    for g, p, info in spec.iter_params():
        for v in (info["min"], info["max"]):
            try:
                parts = build(spec.with_overrides({f"{g}.{p}": v}))["parts"]
                if not all(part.is_valid and part.volume > 0 for part in parts.values()):
                    bad.append(f"{g}.{p}={v}: ungueltiges Teil")
            except Exception as exc:  # noqa: BLE001
                bad.append(f"{g}.{p}={v}: {type(exc).__name__}")
    assert not bad, "\n".join(bad)


if __name__ == "__main__":
    ok = True
    for fn in (test_group_independence, test_min_max_valid):
        try:
            fn()
            print(f"OK    {fn.__name__}")
        except AssertionError as exc:
            ok = False
            print(f"FEHLER {fn.__name__}\n{exc}")
    sys.exit(0 if ok else 1)
