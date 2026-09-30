"""Spec laden, Overrides (`gruppe.param=wert`) anwenden, Grenzen prüfen.

Die Gruppen-Builder bekommen nie die ganze Spec, sondern nur ein `GroupParams`-Objekt ihrer eigenen
Gruppe (plus das Skelett). Zugriff auf einen fremden Parameter wirft sofort einen Fehler.
"""
from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from pathlib import Path

DEFAULT_SPEC = Path(__file__).resolve().parent.parent / "spec" / "boreas_spec.json"
GROUPS = ("skeleton", "upper_body", "arms", "motor_pods", "lower_body", "body_fins", "tail_fins", "nose", "joints",
          "details")


class SpecError(ValueError):
    """Ungültige Spec, unbekannter Parameter oder Wert ausserhalb der Grenzen."""


class GroupParams:
    """Schreibgeschützte Parameter einer einzigen Gruppe: `g.wall`, `g["wall"]`, `g.as_dict()`."""

    __slots__ = ("_name", "_values")

    def __init__(self, name: str, values: dict[str, float]):
        object.__setattr__(self, "_name", name)
        object.__setattr__(self, "_values", dict(values))

    def __getattr__(self, key: str) -> float:
        values = object.__getattribute__(self, "_values")
        if key in values:
            return values[key]
        name = object.__getattribute__(self, "_name")
        raise AttributeError(f"Gruppe '{name}' hat keinen Parameter '{key}' (vorhanden: {', '.join(values)})")

    def __getitem__(self, key: str) -> float:
        return self.__getattr__(key)

    def __setattr__(self, key, value):
        raise AttributeError("GroupParams ist schreibgeschützt – Overrides über Spec.with_overrides()")

    @property
    def name(self) -> str:
        return self._name

    def as_dict(self) -> dict[str, float]:
        return dict(self._values)

    def key(self) -> tuple:
        """Hashbarer Schlüssel (für Caches)."""
        return (self._name,) + tuple(sorted(self._values.items()))

    def __repr__(self) -> str:
        return f"GroupParams({self._name}: {self._values})"


@dataclass
class Spec:
    raw: dict
    path: Path | None = None
    overrides: dict | None = None

    # ---------------------------------------------------------------- laden
    @classmethod
    def load(cls, path: str | Path = DEFAULT_SPEC) -> "Spec":
        path = Path(path)
        spec = cls(json.loads(path.read_text(encoding="utf-8")), path, {})
        spec.validate()
        return spec

    def with_overrides(self, assignments: list[str] | dict | None) -> "Spec":
        """Neue Spec mit geänderten Werten. `assignments`: ['body_fins.chord=40', ...] oder {'g.p': 40}."""
        if not assignments:
            return self
        items = assignments.items() if isinstance(assignments, dict) else (_split(a) for a in assignments)
        raw = copy.deepcopy(self.raw)
        applied = dict(self.overrides or {})
        for dotted, value in items:
            group, _, param = str(dotted).partition(".")
            try:
                entry = raw["groups"][group]["params"][param]
            except KeyError as exc:
                raise SpecError(f"Unbekannter Parameter '{dotted}' (Format gruppe.parameter)") from exc
            entry["value"] = _coerce(value, entry)
            applied[f"{group}.{param}"] = entry["value"]
        spec = Spec(raw, self.path, applied)
        spec.validate()
        return spec

    # ---------------------------------------------------------------- Zugriff
    def group(self, name: str) -> GroupParams:
        try:
            params = self.raw["groups"][name]["params"]
        except KeyError as exc:
            raise SpecError(f"Unbekannte Gruppe '{name}'") from exc
        return GroupParams(name, {k: v["value"] for k, v in params.items()})

    def param_info(self, dotted: str) -> dict:
        group, _, param = dotted.partition(".")
        return self.raw["groups"][group]["params"][param]

    def iter_params(self):
        """(gruppe, parameter, eintrag) für alle Parameter."""
        for g, gdef in self.raw["groups"].items():
            for p, entry in gdef["params"].items():
                yield g, p, entry

    @property
    def meta(self) -> dict:
        return self.raw.get("meta", {})

    # ---------------------------------------------------------------- prüfen
    def validate(self) -> None:
        groups = self.raw.get("groups", {})
        missing = [g for g in GROUPS if g not in groups]
        if missing:
            raise SpecError(f"Gruppen fehlen in der Spec: {missing}")
        for g, p, e in self.iter_params():
            for key in ("value", "min", "max"):
                if key not in e:
                    raise SpecError(f"{g}.{p}: Feld '{key}' fehlt")
            if not (e["min"] - 1e-9 <= e["value"] <= e["max"] + 1e-9):
                raise SpecError(f"{g}.{p} = {e['value']} liegt ausserhalb [{e['min']}, {e['max']}]")


def _split(assignment: str) -> tuple[str, str]:
    if "=" not in assignment:
        raise SpecError(f"Override '{assignment}' hat kein '=' (Format gruppe.parameter=wert)")
    key, value = assignment.split("=", 1)
    return key.strip(), value.strip()


def _coerce(value, entry: dict):
    try:
        v = float(value)
    except (TypeError, ValueError) as exc:
        raise SpecError(f"Wert '{value}' ist keine Zahl") from exc
    is_int = all(float(entry.get(k, 0)).is_integer() for k in ("value", "min", "max", "step")) and \
        float(entry.get("step", 1)).is_integer()
    return int(round(v)) if is_int else v
