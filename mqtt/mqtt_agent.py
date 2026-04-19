import json
import threading
import time
import sys
import paho.mqtt.client as mqtt
from queens.base import Queen
from db.database import Database
from mqtt.mqtt_config import MQTT_BROKER, MQTT_PORT, MQTT_KEEPALIVE

class MQTTAgent:
    def __init__(self, agent_id, column, board_size):
        self.agent_id = agent_id
        self.column = column
        self.board_size = board_size
        self.db = Database()
        self.queen = Queen(column, None, board_size, self.db)
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.running = True

        self.command_topic = f"queens/{agent_id}/command"
        self.response_topic = f"queens/{agent_id}/response"
        self.attack_query_topic = "queens/attack_query"
        self.attack_response_topic = f"queens/{agent_id}/attack_response"

    def on_connect(self, client, userdata, flags, reason_code, properties):
        print(f"Agent {self.agent_id} connected to MQTT broker.")
        client.subscribe(self.command_topic)
        client.subscribe(self.attack_query_topic)

    def on_message(self, client, userdata, msg):
        payload = json.loads(msg.payload.decode())
        if msg.topic == self.command_topic:
            self.handle_command(payload)
        elif msg.topic == self.attack_query_topic:
            self.handle_attack_query(payload)

    def handle_command(self, payload):
        cmd = payload.get("command")
        args = payload.get("args", [])
        reply_to = payload.get("reply_to")
        result = None
        if cmd == "set_neighbor":
            pass
        elif cmd == "find_solution":
            result = self.queen.find_solution()
        elif cmd == "advance":
            result = self.queen.advance()
        elif cmd == "get_position":
            result = self.queen.get_position()
        elif cmd == "get_color":
            result = self.queen.get_color()
        elif cmd == "set_row":
            self.queen.row = args[0]
        elif cmd == "set_fixed":
            self.queen.fixed = args[0]
            if args[0]:
                self.queen.fixed_row = args[1]
        elif cmd == "shutdown":
            self.running = False
            self.client.loop_stop()
        if reply_to:
            self.client.publish(reply_to, json.dumps({"result": result}))

    def handle_attack_query(self, payload):
        test_row = payload["test_row"]
        test_column = payload["test_column"]
        test_color = payload.get("test_color")
        reply_to = payload["reply_to"]
        result = self.queen.can_attack(test_row, test_column, test_color)
        self.client.publish(reply_to, json.dumps({"result": result}))

    def start(self):
        self.client.connect(MQTT_BROKER, MQTT_PORT, MQTT_KEEPALIVE)
        self.client.loop_start()
        while self.running:
            time.sleep(0.1)
        self.client.disconnect()

def run_agent(agent_id, column, board_size):
    agent = MQTTAgent(agent_id, column, board_size)
    agent.start()

if __name__ == "__main__":
    col = int(sys.argv[1])
    board_size = int(sys.argv[2])
    agent_id = f"agent_{col}"
    run_agent(agent_id, col, board_size)