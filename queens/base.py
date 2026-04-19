class Queen:
    def __init__(self, column, neighbor=None, board_size=8, db=None):
        self.column = column
        self.row = 1
        self.neighbor = neighbor
        self.board_size = board_size
        self.db = db
        self.fixed = False
        self.fixed_row = None
        self.priority = column

    def get_color(self):
        if self.db is None:
            return 'RED'
        return self.db.get_cell_color(self.board_size, self.row, self.column)

    def can_attack(self, test_row, test_column, test_color=None):
        if self.row == test_row:
            return True
        col_diff = test_column - self.column
        if (self.row + col_diff == test_row) or (self.row - col_diff == test_row):
            return True

        first_color = self.get_first_queen_color()
        if test_color is None:
            if self.db is not None:
                test_color = self.db.get_cell_color(self.board_size, test_row, test_column)
            else:
                test_color = 'RED'
        if first_color != test_color:
            return True

        if self.neighbor is not None:
            return self.neighbor.can_attack(test_row, test_column, test_color)
        return False

    def get_first_queen_color(self):
        if self.neighbor is None:
            return self.get_color()
        return self.neighbor.get_first_queen_color()

    def find_solution(self):
        if self.fixed:
            if self.neighbor is not None and self.neighbor.can_attack(self.row, self.column):
                return False
            return True
        while (self.neighbor is not None and
               self.neighbor.can_attack(self.row, self.column)):
            if not self.advance():
                return False
        return True

    def advance(self):
        if self.fixed:
            return False
        if self.row < self.board_size:
            self.row += 1
            return self.find_solution()
        if self.neighbor is not None and self.neighbor.advance():
            self.row = 1
            return self.find_solution()
        return False

    def get_position(self):
        return self.row, self.column

    def set_neighbor(self, neighbor):
        self.neighbor = neighbor