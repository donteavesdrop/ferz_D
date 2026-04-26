import json
import time
import uuid
import paho.mqtt.client as mqtt
from .individuals import get_queen_class
from db.database import Database
from mqtt.mqtt_config import (
    MQTT_BROKER, MQTT_PORT, MQTT_KEEPALIVE,
    COMMAND_TOPIC_PREFIX
)

class RemoteQueen:
    """Прокси для ферзя, работающего в отдельном процессе через MQTT."""
    def __init__(self, column, agent_id, client, board_size=8, db=None):
        self.column = column
        self.agent_id = agent_id
        self.client = client
        self.board_size = board_size
        self.db = db
        self.row = 1
        self.fixed = False
        self.fixed_row = None
        self.priority = column
        self.neighbor = None

    def _call(self, command, args=None, timeout=3):
        reply_topic = f"queens/response/{self.agent_id}/{uuid.uuid4()}"
        self.client.subscribe(reply_topic)
        msg = {"command": command, "args": args or [], "reply_to": reply_topic}
        self.client.publish(f"{COMMAND_TOPIC_PREFIX}/{self.agent_id}", json.dumps(msg))
        result = None
        def on_response(client, userdata, msg):
            nonlocal result
            result = json.loads(msg.payload.decode()).get("result")
        self.client.message_callback_add(reply_topic, on_response)
        start = time.time()
        while result is None and time.time() - start < timeout:
            time.sleep(0.01)
        self.client.message_callback_remove(reply_topic)
        self.client.unsubscribe(reply_topic)
        return result

    def set_neighbor(self, neighbor):
        self.neighbor = neighbor

    def can_attack(self, test_row, test_column):
        if self._call("can_attack_local", [self.row, self.column, test_row, test_column]):
            return True
        if self.neighbor is not None:
            return self.neighbor.can_attack(test_row, test_column)
        return False

    def get_color(self):
        return self._call("get_color", [self.row])

    def get_first_queen_color(self):
        if self.neighbor is None:
            return self.get_color()
        return self.neighbor.get_first_queen_color()

    def find_solution(self):
        if self.fixed:
            if self.neighbor and self.neighbor.can_attack(self.row, self.column):
                return False
            return True
        while self.neighbor and self.neighbor.can_attack(self.row, self.column):
            if not self.advance():
                return False
        return True

    def advance(self):
        if self.fixed:
            return False
        if self.row < self.board_size:
            self.row += 1
            return self.find_solution()
        if self.neighbor and self.neighbor.advance():
            self.row = 1
            return self.find_solution()
        return False

    def get_position(self):
        return self.row, self.column


class NQueensSolver:
    def __init__(self, board_size=8, num_queens=8, distributed=False):
        self.board_size = board_size
        self.num_queens = num_queens
        self.solutions = []
        self.db = Database()
        self.priorities = {}
        self.fixed_positions = {}
        self.distributed = distributed
        self.client = None
        if distributed:
            try:
                self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
                self.client.connect(MQTT_BROKER, MQTT_PORT, MQTT_KEEPALIVE)
                self.client.loop_start()
                print("[SOLVER] Connected to MQTT broker.")
            except Exception as e:
                print(f"[SOLVER] MQTT unavailable: {e}")

    def set_config(self, priorities, fixed_positions):
        self.priorities = priorities
        self.fixed_positions = fixed_positions

    def solve(self):
        self.solutions.clear()
        if self.distributed and self.client:
            self._solve_distributed()
        else:
            self._solve_local()

    def _solve_local(self):
        queens_by_col = {}
        for col in range(1, self.num_queens + 1):
            cls = get_queen_class(col)
            queen = cls(col, None, self.board_size, self.db)
            queen.priority = self.priorities.get(col, col)
            if col in self.fixed_positions:
                queen.fixed = True
                queen.fixed_row = self.fixed_positions[col]
                queen.row = queen.fixed_row
            queens_by_col[col] = queen
        sorted_queens = sorted(queens_by_col.values(), key=lambda q: q.priority)
        prev = None
        for q in sorted_queens:
            q.set_neighbor(prev)
            prev = q
        for i in range(1, len(sorted_queens)):
            if not sorted_queens[i].find_solution():
                return
        self._add_solution(sorted_queens)
        rightmost = sorted_queens[-1]
        while rightmost.advance():
            self._add_solution(sorted_queens)

    def _solve_distributed(self):
        print(f"[SOLVER] Distributed search: size {self.board_size}, queens {self.num_queens}")
        proxies = []
        for col in range(1, self.num_queens + 1):
            agent_id = f"agent_{col}"
            proxy = RemoteQueen(col, agent_id, self.client, self.board_size, self.db)
            proxy.priority = self.priorities.get(col, col)
            if col in self.fixed_positions:
                proxy.fixed = True
                proxy.fixed_row = self.fixed_positions[col]
                proxy.row = proxy.fixed_row
            proxies.append(proxy)

        sorted_proxies = sorted(proxies, key=lambda p: p.priority)
        prev = None
        for p in sorted_proxies:
            p.set_neighbor(prev)
            prev = p

        for i in range(1, len(sorted_proxies)):
            if not sorted_proxies[i].find_solution():
                print("[SOLVER] No solution.")
                return

        self._add_solution(sorted_proxies)
        rightmost = sorted_proxies[-1]
        while rightmost.advance():
            self._add_solution(sorted_proxies)
        print(f"[SOLVER] Found {len(self.solutions)} solutions")

    def _add_solution(self, queens):
        positions = [(q.row, q.column) for q in queens]
        total_cost = sum(self.db.get_cell_cost(self.board_size, r, c) for r, c in positions)
        self.solutions.append((positions, total_cost))

    def __del__(self):
        if self.client:
            self.client.loop_stop()
            self.client.disconnect()
