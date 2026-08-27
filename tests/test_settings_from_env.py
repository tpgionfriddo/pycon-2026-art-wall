"""Every runtime dial is reachable from the environment.

`render_timeout_s` was not, and that is how it was found: renders were being
killed at the booth and the only way to raise the ceiling was a commit and a
redeploy. The comment beside the rate limit in `config.py` already states the
principle it broke, so the fix is not just that one field but a test that
fails the next time a dial is added without a way to turn it.
"""
import dataclasses
from pathlib import Path

from artwall.config import Settings

ROOT = Path(__file__).resolve().parent.parent

# The value used to prove a field is actually read, per type. Deliberately
# unlike every default, so a field that is silently ignored fails.
PROBES = {int: ("4321", 4321), float: ("9.5", 9.5), str: ("probe", "probe"),
          Path: ("/tmp/probe", Path("/tmp/probe"))}


def _probe_for(field):
    """A probe value for the field's declared type.

    Matched on the annotation rendered as text, because dataclasses hand back
    real type objects here, and `Path | None` is a union with no `__name__`.
    """
    annotation = field.type if isinstance(field.type, str) else str(field.type)
    for needle, kind in (("Path", Path), ("float", float),
                         ("int", int), ("str", str)):
        if needle in annotation:
            return PROBES[kind]
    raise AssertionError(f"no probe for {field.name}: {annotation}")


def env_var(field) -> str:
    return f"ARTWALL_{field.name.upper()}"


FIELDS = list(dataclasses.fields(Settings))


def test_every_setting_can_be_set_from_the_environment(monkeypatch):
    """No exemption list. Every field on Settings is a dial somebody may need
    to turn at a booth, and the whole point is not having to guess which.
    """
    for field in FIELDS:
        raw, expected = _probe_for(field)
        monkeypatch.setenv(env_var(field), raw)
        got = getattr(Settings.from_env(), field.name)
        assert got == expected, (
            f"{env_var(field)} did not reach Settings.{field.name}: "
            f"got {got!r}, wanted {expected!r}"
        )
        monkeypatch.delenv(env_var(field))


def test_the_render_ceiling_clears_the_slowest_example_with_room():
    """Measured on a dev laptop: the slowest shipped Example renders in about
    15 s on one dedicated CPU, and halving a container's CPU cost about 3.3x,
    not 2x. So a CPU-starved host puts that piece near 50 s and the old 60 s
    ceiling killed work that was fine. The ceiling still has to bound a
    submission that never finishes, because it is the only thing that does.
    """
    assert Settings().render_timeout_s == 180


def test_the_dials_reach_the_containers_that_use_them():
    """A variable the compose file does not forward is not tunable in the
    deployment that matters, whatever `from_env` does with it.
    """
    compose = (ROOT / "compose.yaml").read_text()
    for field in FIELDS:
        assert env_var(field) in compose, f"{env_var(field)} not in compose.yaml"


def test_the_dials_are_documented():
    readme, example = (ROOT / "README.md").read_text(), (ROOT / ".env.example").read_text()
    for field in FIELDS:
        assert env_var(field) in readme, f"{env_var(field)} missing from README"
        assert env_var(field) in example, f"{env_var(field)} missing from .env.example"
