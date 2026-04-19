import json
import time
import paho.mqtt.client as mqtt
from .individuals import get_queen_class
from db.database import Database
from mqtt.mqtt_config import MQTT_BROKER, MQTT_PORT, MQTT_KEEPALIVE

class MQTTQueenProxy:
    def __init__(self, agent_id, column, board_size, client):
        self.agent_id = agent_id
        self.column = column
        self.board_size = board_size
        self.client = client
        self.row = 1
        self.fixed = False
        self.fixed_row = None
        self.priority = column
        self._pending_response = None

    def _call(self, command, args=None, timeout=5):
        reply_topic = f"queens/{self.agent_id}/response/{int(time.time()*1000)}"
        self.client.subscribe(reply_topic)
        msg = {"command": command, "args": args or [], "reply_to": reply_topic}
        self.client.publish(f"queens/{self.agent_id}/command", json.dumps(msg))
        self._pending_response = None
        def on_response(client, userdata, msg):
            self._pending_response = json.loads(msg.payload.decode()).get("result")
        self.client.message_callback_add(reply_topic, on_response)
        start = time.time()
        while self._pending_response is None and time.time() - start < timeout:
            time.sleep(0.01)
        self.client.message_callback_remove(reply_topic)
        self.client.unsubscribe(reply_topic)
        return self._pending_response

    def can_attack(self, test_row, test_column, test_color=None):
        reply_topic = f"queens/{self.agent_id}/attack_response/{int(time.time()*1000)}"
        self.client.subscribe(reply_topic)
        msg = {
            "test_row": test_row,
            "test_column": test_column,
            "test_color": test_color,
            "reply_to": reply_topic
        }
        self.client.publish("queens/attack_query", json.dumps(msg))
        self._pending_response = None
        def on_response(client, userdata, msg):
            self._pending_response = json.loads(msg.payload.decode()).get("result")
        self.client.message_callback_add(reply_topic, on_response)
        start = time.time()
        while self._pending_response is None and time.time() - start < 5:
            time.sleep(0.01)
        self.client.message_callback_remove(reply_topic)
        self.client.unsubscribe(reply_topic)
        return self._pending_response

    def find_solution(self):
        return self._call("find_solution")

    def advance(self):
        return self._call("advance")

    def get_position(self):
        return self._call("get_position")

    def get_color(self):
        return self._call("get_color")

    def set_row(self, row):
        self.row = row
        self._call("set_row", [row])

    def set_fixed(self, fixed, fixed_row=None):
        self.fixed = fixed
        self.fixed_row = fixed_row
        self._call("set_fixed", [fixed, fixed_row])

    def set_neighbor(self, neighbor):
        pass


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
            except Exception as e:
                print(f"MQTT broker unavailable, falling back to local mode: {e}")
                self.distributed = False

    def set_config(self, priorities, fixed_positions):
        self.priorities = priorities
        self.fixed_positions = fixed_positions

    def solve(self):
        self.solutions.clear()
        if self.distributed:
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
        queens_by_col = {}
        for col in range(1, self.num_queens + 1):
            proxy = MQTTQueenProxy(f"agent_{col}", col, self.board_size, self.client)
            proxy.priority = self.priorities.get(col, col)
            if col in self.fixed_positions:
                proxy.set_fixed(True, self.fixed_positions[col])
                proxy.set_row(self.fixed_positions[col])
            queens_by_col[col] = proxy
        sorted_queens = sorted(queens_by_col.values(), key=lambda q: q.priority)
        for i in range(1, len(sorted_queens)):
            if not sorted_queens[i].find_solution():
                return
        self._add_solution(sorted_queens)
        rightmost = sorted_queens[-1]
        while rightmost.advance():
            self._add_solution(sorted_queens)

    def _add_solution(self, queens):
        positions = [(q.row, q.column) for q in queens]
        total_cost = sum(self.db.get_cell_cost(self.board_size, r, c) for r, c in positions)
        self.solutions.append((positions, total_cost))

    def __del__(self):
        if self.client:
            self.client.loop_stop()
            self.client.disconnect()