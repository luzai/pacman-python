# Historical C1 game snapshot

This clean-history branch preserves the `pacman/` subtree from
`d258122eecf6e0dc0a04d6fb8ff57a9b43f0c1d8`, plus its original README attribution.
No game logic changes are made for publication. Other game variants and editor
assets are intentionally not included. Some links/images in the historical
README refer to the original full repository layout.

Recipe: [repro/c1-iter25-lineage](https://github.com/luzai/areal-pacman/tree/repro/c1-iter25-lineage).
Runtime draft: [repro/c1-iter25-runtime](https://github.com/luzai/AReaL/tree/repro/c1-iter25-runtime).
The overall reproduction remains incomplete; publishing these branches is not
training acceptance. Validation is OFF in the companion recipe.

## Preserve ghost-door behavior

Ghost-door tile ID 1 is traversable by Pacman; the wall range is 100-199.
The companion historical MaaPacman mask uses the same IsWall predicate and does
not forbid entering the ghost house. Do not substitute the release branch's
newer game rules into this historical reference.

A real local positioned-fixture test passed movement down through (11,10) from
(10,10) to (12,10), and up in reverse, with the unchanged worker mask allowing
both directions (zero-based row,column). No learned-policy rollout was used.
Headless legacy environment tests also passed horizons 256/700/512.

This game identity is fixed for this draft; the exact first-stage historical
dependency identity still needs provenance closure.

Original authorship and redistribution request: see README.md (David Reilly,
Andy Sommerville). No new license or trademark rights are asserted here.
