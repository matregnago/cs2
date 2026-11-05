"""Keep the server's ChatControl configuration aligned with the image."""

from pathlib import Path

from .filesystem import Changes, safe_target


CHAT_CONTROL = Path(
    "game/csgo/addons/counterstrikesharp/configs/plugins/ChatControl/ChatControl.json"
)


def stage_chat_control(root: Path, changes: Changes) -> None:
    source = Path(__file__).parent.parent / "ChatControl.json"
    target = safe_target(root, CHAT_CONTROL)
    if not target.exists() or target.read_bytes() != source.read_bytes():
        changes[CHAT_CONTROL] = source
