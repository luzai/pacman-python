from __future__ import annotations

import ast
import unittest
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "pacman" / "pacman.pyw"
LARGE_SOURCE = ROOT / "pacman-large" / "pacman.pyw"


class CurriculumArgumentTests(unittest.TestCase):
    def test_default_environment_and_cli_precedence(self) -> None:
        namespace = load_classes("ParseCurriculum")
        namespace.update({"os": __import__("os"), "DEFAULT_CURRICULUM": 2})
        parser = namespace["ParseCurriculum"]
        self.assertEqual(parser(["pacman.pyw"], {}), 2)
        self.assertEqual(
            parser(["pacman.pyw"], {"MAAPACMAN_CURRICULUM": "1"}), 1
        )
        self.assertEqual(
            parser(
                ["pacman.pyw", "--curriculum", "2"],
                {"MAAPACMAN_CURRICULUM": "1"},
            ),
            2,
        )

    def test_invalid_curriculum_fails_closed(self) -> None:
        namespace = load_classes("ParseCurriculum")
        namespace.update({"os": __import__("os"), "DEFAULT_CURRICULUM": 2})
        parser = namespace["ParseCurriculum"]
        for argv in (
            ["pacman.pyw", "--curriculum", "0"],
            ["pacman.pyw", "--curriculum=3"],
            ["pacman.pyw", "--curriculum"],
        ):
            with self.subTest(argv=argv), self.assertRaises(ValueError):
                parser(argv, {})


def load_classes(*names: str, source: Path = SOURCE) -> dict[str, object]:
    tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
    selected = [
        node
        for node in tree.body
        if isinstance(node, (ast.ClassDef, ast.FunctionDef)) and node.name in names
    ]
    namespace: dict[str, object] = {}
    exec(compile(ast.Module(body=selected, type_ignores=[]), str(source), "exec"), namespace)
    return namespace


class PathFinderRegressionTests(unittest.TestCase):
    def test_manhattan_heuristic_uses_end_column(self) -> None:
        for source in (SOURCE, LARGE_SOURCE):
            with self.subTest(source=source.parent.name):
                namespace = load_classes("node", "path_finder", source=source)
                path = namespace["path_finder"]()
                if source == SOURCE:
                    path.ResizeMap(3, 10)
                else:
                    path.ResizeMap((3, 10))
                path.end = (2, 9)
                path.CalcH((0, 0))
                self.assertEqual(path.GetH((0, 0)), 11)

    def test_path_cost_above_one_thousand_is_not_rejected(self) -> None:
        for source in (SOURCE, LARGE_SOURCE):
            with self.subTest(source=source.parent.name):
                namespace = load_classes("node", "path_finder", source=source)
                path = namespace["path_finder"]()
                if source == SOURCE:
                    path.ResizeMap(1, 151)
                else:
                    path.ResizeMap((1, 151))
                route = path.FindPath((0, 0), (0, 150))
                self.assertEqual(route, "R" * 150)


class GhostDoorRoleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.namespace = load_classes("level", "ghost")
        level_type = self.namespace["level"]
        self.level = level_type()
        self.level.lvlWidth = 3
        self.level.lvlHeight = 3
        self.level.map = {(row * 3) + col: 0 for row in range(3) for col in range(3)}
        self.level.SetMapTile(1, 1, 1)
        self.namespace["thisLevel"] = self.level
        self.namespace["tileID"] = {"ghost-door": 1}

    def test_door_is_blocked_for_pacman_from_both_sides(self) -> None:
        self.assertTrue(self.level.IsWall(1, 1, actor="pacman"))
        self.assertTrue(self.level.CheckIfHitWall(16, 16, 1, 1, actor="pacman"))
        self.assertTrue(self.level.IsWall(1, 1))

    def test_door_is_open_for_all_ghost_roles(self) -> None:
        for actor in ("ghost", "vulnerable", "eyes"):
            with self.subTest(actor=actor):
                self.assertFalse(self.level.IsWall(1, 1, actor=actor))
                self.assertFalse(
                    self.level.CheckIfHitWall(16, 16, 1, 1, actor=actor)
                )

    def test_normal_ghost_can_exit_but_cannot_reenter(self) -> None:
        ghost_type = self.namespace["ghost"]
        subject = ghost_type.__new__(ghost_type)
        subject.state = 1

        subject.nearestRow, subject.nearestCol = (0, 1)
        self.assertFalse(subject.IsInGhostHouse())
        self.assertFalse(subject.CanTakePathDirection("D"))

        subject.nearestRow, subject.nearestCol = (2, 1)
        self.assertTrue(subject.IsInGhostHouse())
        self.assertTrue(subject.CanTakePathDirection("U"))

    def test_vulnerable_and_eyes_can_enter_door(self) -> None:
        ghost_type = self.namespace["ghost"]
        subject = ghost_type.__new__(ghost_type)
        subject.nearestRow, subject.nearestCol = (0, 1)
        for state in (2, 3):
            with self.subTest(state=state):
                subject.state = state
                self.assertTrue(subject.CanTakePathDirection("D"))

    def test_all_initial_ghosts_are_outside_or_have_a_door_exit_route(self) -> None:
        # A minimal faithful house: Blinky starts outside; the other three
        # starts are the pen cells directly below the one door.
        self.level.lvlWidth = 5
        self.level.lvlHeight = 5
        rows = (
            (100, 100, 100, 100, 100),
            (100, 0, 0, 0, 100),
            (100, 100, 1, 100, 100),
            (100, 0, 0, 0, 100),
            (100, 100, 100, 100, 100),
        )
        self.level.map = {
            (row * 5) + col: rows[row][col]
            for row in range(5)
            for col in range(5)
        }
        path_namespace = load_classes("node", "path_finder")
        path = path_namespace["path_finder"]()
        path.ResizeMap(5, 5)
        for row in range(5):
            for col in range(5):
                path.SetType(row, col, int(100 <= rows[row][col] <= 199))
        self.namespace["path"] = path

        starts = ((1, 2), (3, 1), (3, 2), (3, 3))
        ghost_type = self.namespace["ghost"]
        for ghost_id, start in enumerate(starts):
            subject = ghost_type.__new__(ghost_type)
            subject.id = ghost_id
            subject.state = 1
            subject.nearestRow, subject.nearestCol = start
            if ghost_id == 0:
                self.assertFalse(subject.IsInGhostHouse())
                continue
            route = subject.FindPathTo(subject.GhostHouseExitTile())
            self.assertTrue(route)
            position = start
            visited = [position]
            offsets = {
                "U": (-1, 0),
                "D": (1, 0),
                "L": (0, -1),
                "R": (0, 1),
            }
            for direction in route:
                delta = offsets[direction]
                position = (position[0] + delta[0], position[1] + delta[1])
                visited.append(position)
            self.assertIn((2, 2), visited)
            self.assertEqual(position, (1, 2))

        outside = ghost_type.__new__(ghost_type)
        outside.state = 1
        outside.nearestRow, outside.nearestCol = (1, 2)
        self.assertFalse(outside.FindPathTo((3, 2)))

    def test_eyes_revive_at_pen_with_normal_speed_and_leave(self) -> None:
        ghost_type = self.namespace["ghost"]
        subject = ghost_type.__new__(ghost_type)
        subject.state = 3
        subject.speed = 4
        subject.nearestRow, subject.nearestCol = (2, 1)
        subject.currentPath = ""
        subject.velX = subject.velY = 0
        self.namespace["player"] = SimpleNamespace(nearestRow=0, nearestCol=0)

        calls: list[tuple[tuple[int, int], tuple[int, int], list[tuple[int, int]]]] = []

        class FakePath:
            def FindPath(self, start, target, blockedNodes=None):
                calls.append((start, target, list(blockedNodes or ())))
                return "UU"

        self.namespace["path"] = FakePath()
        subject.FollowNextPathWay()
        self.assertEqual(subject.state, 1)
        self.assertEqual(subject.speed, 1)
        self.assertEqual(subject.velY, -1)
        self.assertEqual(calls, [((2, 1), (0, 1), [])])


class LargeGhostDoorCollisionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.namespace = load_classes("level", source=LARGE_SOURCE)
        self.level = self.namespace["level"]()
        self.level.lvlWidth = 3
        self.level.lvlHeight = 3
        self.level.map = {(row * 3) + col: 0 for row in range(3) for col in range(3)}
        self.level.SetMapTile((1, 1), 1)
        self.namespace["thisLevel"] = self.level
        self.namespace["tileID"] = {"ghost-door": 1}
        self.namespace["TILE_WIDTH"] = 16
        self.namespace["TILE_HEIGHT"] = 16

    def test_door_blocks_pacman_collision_from_both_sides(self) -> None:
        self.assertTrue(self.level.IsWall((1, 1), actor="pacman"))
        self.assertTrue(self.level.IsWall((1, 1)))
        self.assertTrue(self.level.CheckIfHitWall((16, 16), (1, 1)))

    def test_door_remains_open_for_ghost_pathfinding(self) -> None:
        for actor in ("ghost", "vulnerable", "eyes"):
            with self.subTest(actor=actor):
                self.assertFalse(self.level.IsWall((1, 1), actor=actor))


class CollisionRegressionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.namespace = load_classes("pacman", "RecordGameEvent")
        self.pacman_type = self.namespace["pacman"]
        self.player = self.pacman_type.__new__(self.pacman_type)
        self.player.x = self.player.y = 16
        self.player.nearestRow = self.player.nearestCol = 1

        class Game:
            mode = 1
            ghostValue = 0
            ghostTimer = 0
            score = 0

            def SetMode(self, mode):
                self.mode = mode

            def AddToScore(self, amount, eventType=None, ghostID=None):
                self.score += amount
                if eventType is not None:
                    self._record(eventType, amount, ghostID)

        self.game = Game()
        self.game._record = self.namespace["RecordGameEvent"]
        self.namespace["thisGame"] = self.game
        self.namespace["player"] = self.player
        self.namespace["GAME_EVENT_LEDGER"] = []
        self.namespace["GAME_LOGIC_FRAME"] = 1
        self.namespace["thisLevel"] = SimpleNamespace(
            CheckIfHit=lambda *args: False
        )
        self.namespace["snd_eatgh"] = SimpleNamespace(play=lambda: None)

    def _ghost(self, state: int, row: int = 1, col: int = 1):
        return SimpleNamespace(
            state=state,
            nearestRow=row,
            nearestCol=col,
            x=col * 16,
            y=row * 16,
            speed=1,
            GhostPenTile=lambda: (2, 1),
            FindPathTo=lambda target: "D",
            FollowNextPathWay=lambda: None,
        )

    def test_pacman_or_ghost_entering_other_tile_is_immediately_lethal(self) -> None:
        live = self._ghost(1)
        self.namespace["ghosts"] = {
            0: live,
            1: self._ghost(4, -1, -1),
            2: self._ghost(4, -1, -1),
            3: self._ghost(4, -1, -1),
        }
        self.player.CheckGhostCollisions()
        self.assertEqual(self.game.mode, 2)
        self.assertEqual(
            self.namespace["GAME_EVENT_LEDGER"][0]["type"], "death"
        )

    def test_pacman_entering_adjacent_ghost_tile_dies_before_ghost_moves(self) -> None:
        live = self._ghost(1, row=1, col=2)
        self.namespace["ghosts"] = {
            0: live,
            1: self._ghost(4, -1, -1),
            2: self._ghost(4, -1, -1),
            3: self._ghost(4, -1, -1),
        }
        self.player.lastMoveDir = "S"
        self.player.velX = self.player.velY = 0
        self.player.SnapToGrid = lambda: None
        self.namespace["thisFruit"] = SimpleNamespace(active=False)
        self.namespace["thisLevel"] = SimpleNamespace(
            CheckIfHitWall=lambda *args: False,
            CheckIfHitSomething=lambda *args: None,
            CheckIfHit=lambda player_x, player_y, ghost_x, ghost_y, cushion: (
                abs(player_x - ghost_x) < cushion
                and abs(player_y - ghost_y) < cushion
            ),
        )

        moved = self.player.TryMoveOneCell("R")
        self.assertTrue(moved)
        self.assertEqual((self.player.nearestRow, self.player.nearestCol), (1, 2))
        self.assertEqual((live.nearestRow, live.nearestCol), (1, 2))
        self.assertEqual(self.game.mode, 2)
        self.assertEqual(
            self.namespace["GAME_EVENT_LEDGER"][0]["type"], "death"
        )

    def test_vulnerable_collision_emits_eaten_transition(self) -> None:
        vulnerable = self._ghost(2)
        self.namespace["ghosts"] = {
            0: vulnerable,
            1: self._ghost(4, -1, -1),
            2: self._ghost(4, -1, -1),
            3: self._ghost(4, -1, -1),
        }
        self.player.CheckGhostCollisions()
        self.assertEqual(vulnerable.state, 3)
        self.assertEqual(vulnerable.speed, 4)
        self.assertEqual(self.game.score, 200)
        self.assertEqual(self.game.ghostValue, 400)
        self.assertEqual(self.game.mode, 5)
        event = self.namespace["GAME_EVENT_LEDGER"][0]
        self.assertEqual(event["type"], "ghost_eaten")
        self.assertEqual(event["ghost_id"], 0)
        self.assertEqual(event["ghost_state"], "eyes")
        self.assertEqual(event["score_delta"], 200)

    def test_four_vulnerable_collisions_score_200_400_800_1600(self) -> None:
        ghosts = {
            index: self._ghost(2 if index == 0 else 4, -1, -1)
            for index in range(4)
        }
        self.namespace["ghosts"] = ghosts
        expected_scores = [200, 400, 800, 1600]
        for index, expected in enumerate(expected_scores):
            for ghost_index, ghost in ghosts.items():
                ghost.state = 4
                ghost.nearestRow = ghost.nearestCol = -1
                ghost.x = ghost.y = -16
            subject = ghosts[index]
            subject.state = 2
            subject.nearestRow = subject.nearestCol = 1
            subject.x = subject.y = 16
            self.game.mode = 1
            score_before = self.game.score
            self.player.CheckGhostCollisions()
            self.assertEqual(self.game.score - score_before, expected)
        events = self.namespace["GAME_EVENT_LEDGER"]
        self.assertEqual(
            [event["score_delta"] for event in events], expected_scores
        )
        self.assertEqual(self.game.score, sum(expected_scores))
        self.assertEqual(self.game.ghostValue, 3200)

    def test_fruit_contact_records_exact_2500_source_event(self) -> None:
        self.namespace["ghosts"] = {
            index: self._ghost(4, -1, -1) for index in range(4)
        }
        self.player.lastMoveDir = "S"
        self.player.velX = self.player.velY = 0
        self.player.SnapToGrid = lambda: None
        fruit = SimpleNamespace(active=True, x=32, y=16)
        self.namespace["thisFruit"] = fruit
        self.namespace["snd_eatfruit"] = SimpleNamespace(play=lambda: None)
        self.namespace["thisLevel"] = SimpleNamespace(
            CheckIfHitWall=lambda *args: False,
            CheckIfHitSomething=lambda *args: None,
            CheckIfHit=lambda player_x, player_y, target_x, target_y, cushion: (
                abs(player_x - target_x) < cushion
                and abs(player_y - target_y) < cushion
            ),
        )
        self.game.fruitTimer = 42
        self.game.fruitScoreTimer = 0
        moved = self.player.TryMoveOneCell("R")
        self.assertTrue(moved)
        self.assertFalse(fruit.active)
        self.assertEqual(self.game.score, 2500)
        self.assertEqual(self.game.fruitTimer, 0)
        self.assertEqual(self.game.fruitScoreTimer, 120)
        self.assertEqual(
            [
                (event["type"], event["score_delta"])
                for event in self.namespace["GAME_EVENT_LEDGER"]
            ],
            [("fruit_eaten", 2500)],
        )


class SourceEventLedgerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.namespace = load_classes(
            "game",
            "level",
            "pacman",
            "ResetGameEventLedger",
            "BeginGameLogicFrame",
            "RecordGameEvent",
            "DrainGameEvents",
            "GetGameLogicFrameScoreDelta",
        )
        self.game = self.namespace["game"].__new__(self.namespace["game"])
        self.game.levelNum = 1
        self.game.score = 0
        self.game.lives = 3
        self.game.ghostTimer = 360
        self.game.ghostTimerStartedFrame = -1
        self.game.ghostValue = 0
        self.game.fruitTimer = 0
        self.game.fruitScoreTimer = 0
        self.namespace["thisGame"] = self.game
        self.namespace["CURRICULUM_ID"] = 2
        self.namespace["player"] = SimpleNamespace(nearestRow=4, nearestCol=7)
        self.namespace["ghosts"] = {
            0: SimpleNamespace(state=3),
            1: SimpleNamespace(state=1),
        }
        self.namespace["snd_extralife"] = SimpleNamespace(play=lambda: None)
        self.namespace["ResetGameEventLedger"]()

    def test_multiple_events_are_separate_and_score_sum_is_exact(self) -> None:
        self.namespace["BeginGameLogicFrame"]()
        self.game.AddToScore(100, eventType="power_pellet_eaten")
        self.game.AddToScore(200, eventType="ghost_eaten", ghostID=0)
        self.namespace["RecordGameEvent"]("level_cleared", scoreDelta=0)

        self.assertEqual(self.namespace["GetGameLogicFrameScoreDelta"](), 300)
        events = self.namespace["DrainGameEvents"]()
        self.assertEqual(
            [event["type"] for event in events],
            ["power_pellet_eaten", "ghost_eaten", "level_cleared"],
        )
        self.assertEqual(sum(event["score_delta"] for event in events), 300)
        self.assertTrue(all(event["frame_score_delta"] == 300 for event in events))
        self.assertEqual(events[1]["ghost_state"], "eyes")
        self.assertEqual(events[1]["edible_ticks"], 360)
        self.assertEqual(events[1]["pacman_position"], [4, 7])
        self.assertEqual(self.namespace["DrainGameEvents"](), [])

    def test_events_from_successive_logic_frames_keep_distinct_indices(self) -> None:
        self.namespace["BeginGameLogicFrame"]()
        self.game.AddToScore(10, eventType="normal_pellet_eaten")
        self.namespace["BeginGameLogicFrame"]()
        self.game.AddToScore(2500, eventType="fruit_eaten")
        events = self.namespace["DrainGameEvents"]()
        self.assertEqual([event["frame_index"] for event in events], [1, 2])
        self.assertEqual([event["frame_score_delta"] for event in events], [10, 2500])

    def test_power_pellet_remains_vulnerable_for_full_360_logic_ticks(self) -> None:
        level = self.namespace["level"]()
        level.lvlWidth = 3
        level.lvlHeight = 3
        level.map = {(row * 3) + col: 0 for row in range(3) for col in range(3)}
        level.SetMapTile(1, 1, 3)
        self.namespace["thisLevel"] = level
        self.namespace["tileID"] = {
            "pellet": 2,
            "pellet-power": 3,
            "door-h": 20,
            "door-v": 21,
        }
        self.namespace["snd_powerpellet"] = SimpleNamespace(play=lambda: None)
        self.namespace["snd_pellet"] = {
            0: SimpleNamespace(play=lambda: None),
            1: SimpleNamespace(play=lambda: None),
        }
        ghosts = {index: SimpleNamespace(state=1) for index in range(4)}
        self.namespace["ghosts"] = ghosts
        player = self.namespace["pacman"].__new__(self.namespace["pacman"])
        player.x = player.y = 16
        player.nearestRow = player.nearestCol = 1
        player.pelletSndNum = 0
        self.namespace["player"] = player
        self.namespace["thisFruit"] = SimpleNamespace(active=False)
        self.game.ghostTimer = 0
        self.game.ghostTimerStartedFrame = -1
        self.game.ghostValue = 3200

        self.namespace["BeginGameLogicFrame"]()
        level.CheckIfHitSomething(16, 16, 1, 1)
        self.assertEqual(self.game.ghostTimer, 360)
        self.assertEqual(self.game.ghostValue, 200)
        self.assertTrue(all(ghost.state == 2 for ghost in ghosts.values()))
        player.Move()
        self.assertEqual(self.game.ghostTimer, 360)

        for _ in range(359):
            self.namespace["BeginGameLogicFrame"]()
            player.Move()
        self.assertEqual(self.game.ghostTimer, 1)
        self.assertTrue(all(ghost.state == 2 for ghost in ghosts.values()))

        self.namespace["BeginGameLogicFrame"]()
        player.Move()
        self.assertEqual(self.game.ghostTimer, 0)
        self.assertEqual(self.game.ghostValue, 0)
        self.assertTrue(all(ghost.state == 1 for ghost in ghosts.values()))
        events = self.namespace["DrainGameEvents"]()
        self.assertEqual(
            [(event["type"], event["score_delta"], event["edible_ticks"])
             for event in events],
            [("power_pellet_eaten", 100, 360)],
        )

    def test_curriculum_one_power_pellet_scores_without_ghost_timer(self) -> None:
        level = self.namespace["level"]()
        level.lvlWidth = 3
        level.lvlHeight = 3
        level.map = {(row * 3) + col: 0 for row in range(3) for col in range(3)}
        level.SetMapTile(1, 1, 3)
        self.namespace["thisLevel"] = level
        self.namespace["tileID"] = {
            "pellet": 2,
            "pellet-power": 3,
            "door-h": 20,
            "door-v": 21,
        }
        self.namespace["snd_powerpellet"] = SimpleNamespace(play=lambda: None)
        self.namespace["ghosts"] = {
            index: SimpleNamespace(state=4) for index in range(4)
        }
        self.namespace["CURRICULUM_ID"] = 1
        self.game.ghostTimer = 0
        self.game.ghostTimerStartedFrame = -1
        self.game.ghostValue = 0
        self.namespace["BeginGameLogicFrame"]()

        level.CheckIfHitSomething(16, 16, 1, 1)

        self.assertEqual(self.game.score, 100)
        self.assertEqual(self.game.ghostTimer, 0)
        self.assertEqual(self.game.ghostTimerStartedFrame, -1)
        self.assertEqual(self.game.ghostValue, 0)
        self.assertTrue(
            all(ghost.state == 4 for ghost in self.namespace["ghosts"].values())
        )
        self.assertEqual(
            [event["type"] for event in self.namespace["DrainGameEvents"]()],
            ["power_pellet_eaten"],
        )

    def test_curriculum_one_restart_keeps_four_inactive_ghosts_and_no_fruit(self) -> None:
        level = self.namespace["level"]()
        self.namespace["CURRICULUM_ID"] = 1
        self.namespace["ghosts"] = {
            index: SimpleNamespace(
                x=16,
                y=16,
                velX=1,
                velY=1,
                state=1,
                speed=2,
                nearestRow=1,
                nearestCol=1,
                currentPath="RR",
            )
            for index in range(4)
        }
        self.namespace["thisFruit"] = SimpleNamespace(
            active=True,
            x=16,
            y=16,
            velX=1,
            velY=1,
            nearestRow=1,
            nearestCol=1,
            currentPath="R",
        )
        self.namespace["player"] = SimpleNamespace(
            homeX=16,
            homeY=32,
            x=0,
            y=0,
            velX=1,
            velY=1,
            lastMoveDir="R",
            SnapToGrid=lambda: None,
            anim_pacmanS={},
            anim_pacmanCurrent=None,
            animFrame=0,
        )

        level.Restart()

        self.assertEqual(len(self.namespace["ghosts"]), 4)
        for ghost in self.namespace["ghosts"].values():
            self.assertEqual((ghost.x, ghost.y), (-64, -64))
            self.assertEqual((ghost.nearestRow, ghost.nearestCol), (-4, -4))
            self.assertEqual((ghost.velX, ghost.velY), (0, 0))
            self.assertEqual(ghost.state, 4)
            self.assertIs(ghost.currentPath, False)
        self.assertFalse(self.namespace["thisFruit"].active)
        self.assertEqual(self.game.fruitTimer, 0)
        self.assertEqual(self.game.ghostTimer, 0)


if __name__ == "__main__":
    unittest.main()
