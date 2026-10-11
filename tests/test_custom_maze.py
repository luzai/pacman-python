"""Exercise actual game functions without initializing its GUI/audio loop."""

import unittest
from types import SimpleNamespace

from test_level1_rules import load_classes


class CustomMazeTests(unittest.TestCase):
    def test_ghost_count_defaults_cli_precedence_and_invalid_values(self):
        parser = load_classes("ParseActiveGhostCount")["ParseActiveGhostCount"]
        self.assertEqual(parser(["game"], {}), 4)
        for count in (1, 2, 4):
            self.assertEqual(parser(["game"], {"SMALL_MAZE_GHOST_COUNT": str(count)}), count)
            self.assertEqual(
                parser(["game", "--active-ghost-count", str(count)], {"SMALL_MAZE_GHOST_COUNT": "invalid"}), count
            )
            self.assertEqual(parser(["game", f"--active-ghost-count={count}"], {}), count)
        for raw in ("0", "3", "5", "x", "", "1.5"):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                parser(["game"], {"SMALL_MAZE_GHOST_COUNT": raw})
        with self.assertRaises(ValueError):
            parser(["game", "--active-ghost-count"], {})

    def test_count_is_level_one_only_and_disabled_mode_wins(self):
        ns = load_classes("game")
        ns.update(CURRICULUM_ID=2, GHOST_MODE="normal", ACTIVE_GHOST_COUNT=2)
        game = ns["game"].__new__(ns["game"])
        game.levelNum = 1
        self.assertEqual(game.ActiveGhostCount(), 2)
        game.levelNum = 2
        self.assertEqual(game.ActiveGhostCount(), 4)
        game.levelNum = 1
        ns["GHOST_MODE"] = "disabled"
        self.assertEqual(game.ActiveGhostCount(), 0)
        ns.update(GHOST_MODE="normal", CURRICULUM_ID=1)
        self.assertEqual(game.ActiveGhostCount(), 0)

    def test_unreachable_fruit_path_stops_before_movement(self):
        ns = load_classes("fruit")
        ns["thisGame"] = SimpleNamespace(fruitTimer=123)
        fruit = ns["fruit"].__new__(ns["fruit"])
        fruit.active, fruit.currentPath = True, False
        fruit.velX, fruit.velY = 1, -1
        self.assertIs(fruit.Move(), False)
        self.assertFalse(fruit.active)
        self.assertEqual((fruit.velX, fruit.velY, ns["thisGame"].fruitTimer), (0, 0, 0))

    def test_restart_activates_exactly_the_selected_count(self):
        for count in (1, 2, 4):
            with self.subTest(count=count):
                ns = load_classes("game", "level")
                ns.update(CURRICULUM_ID=2, GHOST_MODE="normal", ACTIVE_GHOST_COUNT=count)
                game = ns["game"].__new__(ns["game"])
                game.levelNum = 1
                level = ns["level"]()
                level.lvlWidth = level.lvlHeight = 3
                level.map = {i: 2 for i in range(9)}
                ghosts = {
                    i: SimpleNamespace(
                        homeX=16, homeY=16, state=1, FindPathTo=lambda target: "R", FollowNextPathWay=lambda: None
                    )
                    for i in range(4)
                }
                ns.update(
                    thisGame=game,
                    ghosts=ghosts,
                    thisFruit=SimpleNamespace(active=True),
                    random=SimpleNamespace(randint=lambda a, b: 1),
                    tileID={"pellet": 2},
                    player=SimpleNamespace(homeX=16, homeY=16, SnapToGrid=lambda: None, anim_pacmanS={}),
                )
                level.Restart()
                self.assertEqual(sum(g.state == 1 for g in ghosts.values()), count)
                for i in range(count, 4):
                    self.assertEqual((ghosts[i].x, ghosts[i].y, ghosts[i].state), (-64, -64, 4))
                    self.assertIs(ghosts[i].currentPath, False)

    def test_custom_wall_render_bypasses_sprite_and_preserves_default(self):
        ns = load_classes("level")
        level = ns["level"]()
        level.lvlWidth = level.lvlHeight = 1
        level.powerPelletBlinkTimer = 0
        level.map = {0: 100}
        level.edgeLightColor = (0, 0, 255)
        draws, blits = [], []
        ns.update(
            thisLevel=level,
            screen=SimpleNamespace(blit=lambda *args: blits.append(args)),
            pygame=SimpleNamespace(draw=SimpleNamespace(rect=lambda *args: draws.append(args))),
            tileID={"door-h": 20, "door-v": 21, "pellet-power": 3, "showlogo": 22, "hiscores": 23},
            tileIDImage={100: "original"},
            CUSTOM_WALL_RENDER=True,
        )
        level.DrawMap()
        self.assertEqual(len(draws), 1)
        self.assertEqual(blits, [])
        ns["CUSTOM_WALL_RENDER"] = False
        level.DrawMap()
        self.assertEqual(blits, [("original", (0, 0))])


if __name__ == "__main__":
    unittest.main()
