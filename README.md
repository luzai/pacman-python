# MaaPacman `pacman-python` ruleset

This branch pins the Pacman game rules used by
[`luzai/areal-pacman`](https://github.com/luzai/areal-pacman) for reproducible
Level-1 reinforcement-learning runs.

The game is derived from David Reilly's
[`greyblue9/pacman-python`](https://github.com/greyblue9/pacman-python).
See the [original README](https://github.com/greyblue9/pacman-python/blob/master/README.md)
for project history, installation details, controls, and the maze editor.

## Ghost modes for the released AReaL recipe

Use `--curriculum 2 --ghost-mode disabled` for navigation training and
`--curriculum 2 --ghost-mode normal` for full gameplay. `--ghost-mode` defaults
to `normal`. Only Level-1 ghosts change: disabled ghosts cannot move, render,
collide, or become vulnerable; fruit and pellet rules remain unchanged.
The paired wrapper exposes `ghosts: []` when disabled and the usual ghost
records when normal. Internal inactive objects are retained for engine safety.

For Level 1, `SMALL_MAZE_GHOST_COUNT=1`, `2`, or `4` controls the active
ghosts (default `4`). Remaining objects are placed off-map in inactive state
on every restart: they cannot move, render, collide, or become vulnerable.
The paired wrapper rejects active ghosts omitted from its observation. This
fix changes reduced-ghost gameplay; regenerate source identities and datasets
for new runs rather than applying it to historical runs or saved states.

## Legacy curriculum modes

When driven through the paired `PygamePacmanEnv`, both modes advance up to 16
game-logic frames for each RL action; a terminal state can stop the action early.

| Mode | Level-1 behavior |
| --- | --- |
| `--curriculum 1` | Safe pellet collection. Four ghost objects remain in the state schema but stay `gone`, off-map, motionless, and non-colliding. Fruit is disabled. Power pellets give their normal score but do not make ghosts vulnerable. |
| `--curriculum 2` | Full `ghostdoor-v3` behavior with active ghosts and power-pellet vulnerability. Fruit is disabled by default; set `PACMAN_DISABLE_FRUIT=0` to enable it. This is the default curriculum. |

These curriculum changes apply only to Level 1.

## Run

From the repository root:

```bash
python pacman/pacman.pyw --start-level 1 --curriculum 1
python pacman/pacman.pyw --start-level 1 --curriculum 2
```

`MAAPACMAN_CURRICULUM=1` or `2` may be used instead; an explicit CLI option
takes precedence.

For AReaL training, point the paired repository at this checkout:

```bash
export MAAPACMAN_PACMAN_PYTHON_ROOT=/absolute/path/to/pacman-python
```

Then choose the matching curriculum configuration in
[`luzai/areal-pacman`](https://github.com/luzai/areal-pacman).

## Verify

```bash
python -m unittest discover -s tests -v
```

## Optional fruit switch

Fruit spawning, movement, and rendering are disabled by default
(`PACMAN_DISABLE_FRUIT=1`). Set `PACMAN_DISABLE_FRUIT=0` to enable fruit explicitly.
An unreachable fruit path
now cancels that fruit attempt safely instead of calling `len(False)`.
This switch does not disable ghosts or power pellets.
