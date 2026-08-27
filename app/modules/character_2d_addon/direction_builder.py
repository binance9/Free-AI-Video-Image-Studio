from __future__ import annotations

DIRECTIONS_8 = {
    "down": "facing camera / front view",
    "up": "back view",
    "left": "left side view",
    "right": "right side view",
    "down_left": "three-quarter front left view",
    "down_right": "three-quarter front right view",
    "up_left": "three-quarter back left view",
    "up_right": "three-quarter back right view",
}

ACTION_HINTS = {
    "idle": "neutral ready stance, readable silhouette, both feet visible, calm but alert",
    "run": "running motion, readable leg separation, strong forward lean, cloth and hair flowing",
    "attack": "weapon swing pose, strong attack arc, readable blade placement, dynamic action",
}


def build_pose_hint(direction: str, action: str, frame_index: int = 0, total_frames: int = 1) -> str:
    direction_text = DIRECTIONS_8.get(direction, direction)
    action_text = ACTION_HINTS.get(action, action)
    beat = ""
    if total_frames > 1:
        phase = frame_index % max(1, total_frames)
        if action == "run":
            phases = [
                "contact step with left leg forward",
                "passing pose",
                "contact step with right leg forward",
                "passing pose mirrored",
            ]
            beat = phases[phase % len(phases)]
        elif action == "attack":
            phases = [
                "anticipation / wind-up",
                "main swing impact",
                "follow-through",
                "recovery stance",
            ]
            beat = phases[phase % len(phases)]
        elif action == "idle":
            phases = [
                "neutral pose",
                "subtle breathing",
                "weight shift",
                "return to neutral",
            ]
            beat = phases[phase % len(phases)]
    return f"{direction_text}, {action_text}{', ' + beat if beat else ''}"
