from __future__ import annotations

import ast
import unittest
from pathlib import Path
from types import SimpleNamespace


SOURCE = Path(__file__).resolve().parents[1] / "pacman" / "pacman.pyw"


def load_runtime() -> dict[str, object]:
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"), filename=str(SOURCE))
    names = {"pacman", "level", "RecordGameEvent"}
    selected = [
        node
        for node in tree.body
        if isinstance(node, (ast.ClassDef, ast.FunctionDef)) and node.name in names
    ]
    namespace: dict[str, object] = {}
    exec(
        compile(ast.Module(body=selected, type_ignores=[]), str(SOURCE), "exec"),
        namespace,
    )
    return namespace


class TunnelEventPositionRegressionTest(unittest.TestCase):
    def test_tunnel_exit_syncs_grid_before_collision_event(self) -> None:
        namespace = load_runtime()
        tunnel = namespace["level"]()
        tunnel.lvlWidth = 5
        tunnel.lvlHeight = 3
        tunnel.map = {
            (row * tunnel.lvlWidth) + col: 0
            for row in range(tunnel.lvlHeight)
            for col in range(tunnel.lvlWidth)
        }
        tunnel.SetMapTile(1, 0, 20)
        tunnel.SetMapTile(1, 4, 20)
        namespace["thisLevel"] = tunnel
        namespace["tileID"] = {
            "pellet": 2,
            "pellet-power": 3,
            "door-h": 20,
            "door-v": 21,
        }

        player = namespace["pacman"].__new__(namespace["pacman"])
        player.x = 16
        player.y = 16
        player.nearestRow = 1
        player.nearestCol = 1
        player.lastMoveDir = "S"
        player.velX = player.velY = 0
        player.pelletSndNum = 0
        namespace["player"] = player

        def ghost(state: int, row: int, col: int) -> SimpleNamespace:
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

        namespace["ghosts"] = {
            0: ghost(1, 1, 3),
            1: ghost(4, -1, -1),
            2: ghost(4, -1, -1),
            3: ghost(4, -1, -1),
        }
        namespace["thisFruit"] = SimpleNamespace(active=False)
        namespace["GAME_EVENT_LEDGER"] = []
        namespace["GAME_LOGIC_FRAME"] = 1

        class Game:
            mode = 1
            ghostValue = 0
            ghostTimer = 0

            def SetMode(self, mode):
                self.mode = mode

        namespace["thisGame"] = Game()

        moved = player.TryMoveOneCell("L")

        self.assertTrue(moved)
        self.assertEqual((player.x, player.y), (48, 16))
        self.assertEqual((player.nearestRow, player.nearestCol), (1, 3))
        event = namespace["GAME_EVENT_LEDGER"][0]
        self.assertEqual(event["type"], "death")
        self.assertEqual(event["pacman_position"], [1, 3])


if __name__ == "__main__":
    unittest.main()
