import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import time
import paho.mqtt.client as mqtt
from db.database import Database
from mqtt.mqtt_config import (
    MQTT_BROKER, MQTT_PORT, MQTT_KEEPALIVE,
    COMMAND_TOPIC_PREFIX
)

class MQTTAgent:
    def __init__(self, agent_id, column, board_size):
        self.agent_id = agent_id
        self.column = column
        self.board_size = board_size
        self.db = Database()
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.running = True
        self.command_topic = f"{COMMAND_TOPIC_PREFIX}/{agent_id}"

    def on_connect(self, client, userdata, flags, reason_code, properties):
        print(f"[AGENT] {self.agent_id} connected.")
        client.subscribe(self.command_topic)

    def on_message(self, client, userdata, msg):
        payload = json.loads(msg.payload.decode())
        cmd = payload.get("command")
        args = payload.get("args", [])
        reply_to = payload.get("reply_to")
        result = None

        try:
            if cmd == "can_attack_local":
                # args: [my_row, my_col, test_row, test_col]
                my_row, my_col, test_row, test_col = args
                # Проверка атаки (только геометрия)
                if my_row == test_row:
                    result = True
                elif abs(my_row - test_row) == abs(my_col - test_col):
                    result = True
                else:
                    result = False
            elif cmd == "get_color":
                row = args[0]
                result = self.db.get_cell_color(self.board_size, row, self.column)
            elif cmd == "shutdown":
                self.running = False
                self.client.loop_stop()
                return
        except Exception as e:
            print(f"[AGENT] Error: {e}")
            result = None

        if reply_to:
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
    try:
        col = int(sys.argv[1])
        board_size = int(sys.argv[2])
        agent_id = f"agent_{col}"
        run_agent(agent_id, col, board_size)
    except Exception as e:
        print(f"[AGENT] crashed: {e}")
        input("Press Enter to close...")
