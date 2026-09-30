"""Ein Modul je Parameter-Gruppe. Jede `build_<gruppe>(sk, g)` bekommt nur das Skelett und die eigene Gruppe."""
from .arms import build_arms
from .body_fins import build_body_fins
from .joints import build_joints
from .lower_body import build_lower_body
from .motor_pods import build_motor_pods
from .nose import build_nose
from .tail_fins import build_tail_fins
from .upper_body import build_upper_body

BUILDERS = {
    "upper_body": build_upper_body,
    "arms": build_arms,
    "motor_pods": build_motor_pods,
    "lower_body": build_lower_body,
    "body_fins": build_body_fins,
    "tail_fins": build_tail_fins,
    "nose": build_nose,
    "joints": build_joints,
}
