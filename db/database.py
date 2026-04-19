import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'queens.db')

class Database:
    def __init__(self):
        self._init_db()

    def _get_connection(self):
        return sqlite3.connect(DB_PATH)

    def _init_db(self):
        with self._get_connection() as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS cell_states (
                    board_size INTEGER NOT NULL,
                    row INTEGER NOT NULL,
                    col INTEGER NOT NULL,
                    color TEXT NOT NULL DEFAULT 'RED',
                    cost INTEGER NOT NULL DEFAULT 1,
                    PRIMARY KEY (board_size, row, col)
                )
            ''')

    def get_cell_color(self, board_size, row, col):
        with self._get_connection() as conn:
            cur = conn.execute(
                'SELECT color FROM cell_states WHERE board_size=? AND row=? AND col=?',
                (board_size, row, col)
            )
            row_data = cur.fetchone()
            if row_data:
                return row_data[0]
            # Если нет записи – создаём с цветом по умолчанию
            self.set_cell_state(board_size, row, col, 'RED', 1)
            return 'RED'

    def get_cell_cost(self, board_size, row, col):
        with self._get_connection() as conn:
            cur = conn.execute(
                'SELECT cost FROM cell_states WHERE board_size=? AND row=? AND col=?',
                (board_size, row, col)
            )
            row_data = cur.fetchone()
            if row_data:
                return row_data[0]
            self.set_cell_state(board_size, row, col, 'RED', 1)
            return 1

    def set_cell_state(self, board_size, row, col, color, cost):
        with self._get_connection() as conn:
            conn.execute('''
                INSERT INTO cell_states (board_size, row, col, color, cost)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(board_size, row, col) DO UPDATE SET
                    color=excluded.color,
                    cost=excluded.cost
            ''', (board_size, row, col, color, cost))

    def get_all_states(self, board_size):
        with self._get_connection() as conn:
            cur = conn.execute(
                'SELECT row, col, color, cost FROM cell_states WHERE board_size=?',
                (board_size,)
            )
            return {(row, col): (color, cost) for row, col, color, cost in cur.fetchall()}