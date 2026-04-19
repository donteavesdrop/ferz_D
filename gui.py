import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageTk
from queens.solver import NQueensSolver
from db.database import Database

class QueensGUI:
    def __init__(self, master):
        self.master = master
        master.title("N-Queens with costs and colors")
        self.canvas_size = 500
        self.board_size = 8
        self.num_queens = 8
        self.db = Database()

        self.solver = None
        self.solutions = []
        self.current_sol_index = -1
        self.sort_ascending = True
        self.priorities = {}
        self.fixed_positions = {}
        self.queen_img = self.load_queen_image()
        self.queen_photos = []

        self.create_widgets()
        self.draw_board()

    def load_queen_image(self):
        try:
            img = Image.open("queen.png")
            return img
        except FileNotFoundError:
            return None

    def create_widgets(self):
        main_frame = tk.Frame(self.master)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        canvas_frame = tk.Frame(main_frame)
        canvas_frame.pack(side=tk.LEFT, padx=(0,10))

        self.canvas = tk.Canvas(canvas_frame, width=self.canvas_size, height=self.canvas_size, bg='white')
        self.canvas.pack()
        self.canvas.bind("<Double-Button-1>", self.on_canvas_double_click)

        control_frame = tk.Frame(main_frame)
        control_frame.pack(side=tk.RIGHT, fill=tk.Y)

        settings_frame = tk.LabelFrame(control_frame, text="Настройки", padx=5, pady=5)
        settings_frame.pack(fill=tk.X, pady=(0,10))

        tk.Label(settings_frame, text="Размер доски (N):").grid(row=0, column=0, sticky='w')
        self.board_size_var = tk.IntVar(value=8)
        tk.Spinbox(settings_frame, from_=4, to=20, textvariable=self.board_size_var, width=5,
                   command=self.on_board_size_change).grid(row=0, column=1, padx=5)

        tk.Label(settings_frame, text="Количество ферзей:").grid(row=1, column=0, sticky='w')
        self.num_queens_var = tk.IntVar(value=8)
        tk.Spinbox(settings_frame, from_=1, to=20, textvariable=self.num_queens_var, width=5,
                   command=self.on_num_queens_change).grid(row=1, column=1, padx=5)

        tk.Label(settings_frame, text="Режим:").grid(row=2, column=0, sticky='w')
        self.distributed_var = tk.BooleanVar(value=False)
        tk.Checkbutton(settings_frame, text="Распределённый (MQTT)", variable=self.distributed_var).grid(row=2, column=1, sticky='w')

        btn_frame = tk.Frame(control_frame)
        btn_frame.pack(fill=tk.X, pady=5)

        self.solve_btn = tk.Button(btn_frame, text="Найти решения", command=self.find_solutions)
        self.solve_btn.pack(fill=tk.X, pady=2)

        self.start_agents_btn = tk.Button(btn_frame, text="Запустить агентов", command=self.start_agents)
        self.start_agents_btn.pack(fill=tk.X, pady=2)

        self.priority_btn = tk.Button(btn_frame, text="Приоритеты и фиксация", command=self.open_priority_dialog)
        self.priority_btn.pack(fill=tk.X, pady=2)

        nav_frame = tk.Frame(control_frame)
        nav_frame.pack(fill=tk.X, pady=5)
        self.prev_btn = tk.Button(nav_frame, text="◀ Пред.", command=self.prev_solution, state=tk.DISABLED)
        self.prev_btn.pack(side=tk.LEFT, expand=True, fill=tk.X)
        self.next_btn = tk.Button(nav_frame, text="След. ▶", command=self.next_solution, state=tk.DISABLED)
        self.next_btn.pack(side=tk.RIGHT, expand=True, fill=tk.X)

        self.info_label = tk.Label(control_frame, text="Решения не найдены")
        self.info_label.pack(pady=5)

        list_frame = tk.LabelFrame(control_frame, text="Найденные решения", padx=5, pady=5)
        list_frame.pack(fill=tk.BOTH, expand=True)

        sort_frame = tk.Frame(list_frame)
        sort_frame.pack(fill=tk.X, pady=(0,5))
        tk.Button(sort_frame, text="↑ Цена", command=lambda: self.sort_solutions(True)).pack(side=tk.LEFT, padx=2)
        tk.Button(sort_frame, text="↓ Цена", command=lambda: self.sort_solutions(False)).pack(side=tk.LEFT, padx=2)

        self.solutions_listbox = tk.Listbox(list_frame, height=10)
        self.solutions_listbox.pack(fill=tk.BOTH, expand=True)
        self.solutions_listbox.bind('<<ListboxSelect>>', self.on_solution_select)

    def on_board_size_change(self):
        new_size = self.board_size_var.get()
        if new_size != self.board_size:
            self.board_size = new_size
            self.num_queens_var.set(min(self.num_queens, self.board_size))
            self.num_queens = self.num_queens_var.get()
            self.priorities.clear()
            self.fixed_positions.clear()
            self.draw_board()

    def on_num_queens_change(self):
        new_num = self.num_queens_var.get()
        if new_num > self.board_size:
            messagebox.showwarning("Ошибка", "Ферзей не может быть больше размера доски")
            self.num_queens_var.set(self.board_size)
            new_num = self.board_size
        self.num_queens = new_num
        self.priorities.clear()
        self.fixed_positions.clear()

    def draw_board(self):
        self.canvas.delete("all")
        self.queen_photos.clear()
        cell_size = self.canvas_size // self.board_size

        def blend_color(base_hex, overlay_hex, alpha=0.4):
            base = base_hex.lstrip('#')
            ov = overlay_hex.lstrip('#')
            br, bg, bb = int(base[0:2], 16), int(base[2:4], 16), int(base[4:6], 16)
            or_, og, ob = int(ov[0:2], 16), int(ov[2:4], 16), int(ov[4:6], 16)
            r = int(br * (1 - alpha) + or_ * alpha)
            g = int(bg * (1 - alpha) + og * alpha)
            b = int(bb * (1 - alpha) + ob * alpha)
            return f'#{r:02x}{g:02x}{b:02x}'

        color_overlay = {'RED': '#FF8888', 'GREEN': '#88FF88', 'BLUE': '#8888FF'}

        for r in range(self.board_size):
            for c in range(self.board_size):
                x1 = c * cell_size
                y1 = r * cell_size
                x2 = x1 + cell_size
                y2 = y1 + cell_size
                base_color = "#F0D9B5" if (r + c) % 2 == 0 else "#B58863"
                state_color = self.db.get_cell_color(self.board_size, r+1, c+1)
                blended = blend_color(base_color, color_overlay[state_color], alpha=0.4)
                self.canvas.create_rectangle(x1, y1, x2, y2, fill=blended, outline="")
                label = state_color[0]
                self.canvas.create_text(x1 + 5, y1 + 5, text=label, anchor='nw',
                                        font=('Arial', max(8, cell_size//5), 'bold'), fill='black')

        if self.solutions and 0 <= self.current_sol_index < len(self.solutions):
            positions, _ = self.solutions[self.current_sol_index]
            for row, col in positions:
                self.draw_queen(row-1, col-1, cell_size)

    def draw_queen(self, row, col, cell_size):
        if self.queen_img is None:
            x_center = col * cell_size + cell_size // 2
            y_center = row * cell_size + cell_size // 2
            radius = cell_size // 3
            self.canvas.create_oval(x_center - radius, y_center - radius,
                                    x_center + radius, y_center + radius,
                                    fill="black", outline="black")
            return
        img_resized = self.queen_img.resize((cell_size, cell_size), Image.Resampling.LANCZOS)
        photo = ImageTk.PhotoImage(img_resized)
        self.queen_photos.append(photo)
        x = col * cell_size
        y = row * cell_size
        self.canvas.create_image(x, y, image=photo, anchor="nw")

    def start_agents(self):
        import subprocess
        import os
        base_dir = os.path.dirname(__file__)
        agent_script = os.path.join(base_dir, "mqtt", "mqtt_agent.py")
        for col in range(1, self.num_queens + 1):
            subprocess.Popen(["python", agent_script, str(col), str(self.board_size)])
        messagebox.showinfo("Агенты", f"Запущено {self.num_queens} агентов через MQTT.")

    def find_solutions(self):
        distributed = self.distributed_var.get()
        self.solver = NQueensSolver(self.board_size, self.num_queens, distributed=distributed)
        self.solver.set_config(self.priorities, self.fixed_positions)
        self.solver.solve()
        self.solutions = self.solver.solutions
        self.sort_solutions(self.sort_ascending)
        self.current_sol_index = 0 if self.solutions else -1
        self.update_ui()

    def sort_solutions(self, ascending):
        self.sort_ascending = ascending
        if self.solutions:
            self.solutions.sort(key=lambda x: x[1], reverse=not ascending)
        self.update_solutions_list()
        self.current_sol_index = 0 if self.solutions else -1
        self.update_ui()

    def update_solutions_list(self):
        self.solutions_listbox.delete(0, tk.END)
        for i, (_, cost) in enumerate(self.solutions):
            self.solutions_listbox.insert(tk.END, f"{i+1}: стоимость {cost}")

    def on_solution_select(self, event):
        selection = self.solutions_listbox.curselection()
        if selection:
            self.current_sol_index = selection[0]
            self.draw_board()
            self.update_info_label()

    def prev_solution(self):
        if self.solutions and self.current_sol_index > 0:
            self.current_sol_index -= 1
            self.update_ui()

    def next_solution(self):
        if self.solutions and self.current_sol_index < len(self.solutions) - 1:
            self.current_sol_index += 1
            self.update_ui()

    def update_ui(self):
        self.draw_board()
        self.update_info_label()
        self.solutions_listbox.selection_clear(0, tk.END)
        if self.solutions:
            self.solutions_listbox.selection_set(self.current_sol_index)
            self.solutions_listbox.see(self.current_sol_index)
        self.prev_btn.config(state=tk.NORMAL if self.current_sol_index > 0 else tk.DISABLED)
        self.next_btn.config(state=tk.NORMAL if self.current_sol_index < len(self.solutions)-1 else tk.DISABLED)

    def update_info_label(self):
        if self.solutions:
            _, cost = self.solutions[self.current_sol_index]
            self.info_label.config(text=f"Решение {self.current_sol_index+1} из {len(self.solutions)} | Стоимость: {cost}")
        else:
            self.info_label.config(text="Решения не найдены")

    def on_canvas_double_click(self, event):
        cell_size = self.canvas_size // self.board_size
        col = event.x // cell_size
        row = event.y // cell_size
        if 0 <= row < self.board_size and 0 <= col < self.board_size:
            self.selected_cell = (row+1, col+1)
            self.edit_cell_dialog(row+1, col+1)

    def edit_cell_dialog(self, row, col):
        dialog = tk.Toplevel(self.master)
        dialog.title(f"Клетка ({row}, {col})")
        dialog.transient(self.master)
        dialog.grab_set()
        tk.Label(dialog, text="Цвет:").grid(row=0, column=0, padx=5, pady=5)
        color_var = tk.StringVar(value=self.db.get_cell_color(self.board_size, row, col))
        color_combo = ttk.Combobox(dialog, textvariable=color_var, values=['RED', 'GREEN', 'BLUE'], state='readonly')
        color_combo.grid(row=0, column=1, padx=5, pady=5)
        tk.Label(dialog, text="Стоимость:").grid(row=1, column=0, padx=5, pady=5)
        cost_var = tk.IntVar(value=self.db.get_cell_cost(self.board_size, row, col))
        tk.Spinbox(dialog, from_=1, to=100, textvariable=cost_var, width=5).grid(row=1, column=1, padx=5, pady=5)
        def save():
            self.db.set_cell_state(self.board_size, row, col, color_var.get(), cost_var.get())
            dialog.destroy()
            self.draw_board()
        tk.Button(dialog, text="Сохранить", command=save).grid(row=2, column=0, columnspan=2, pady=10)

    def open_priority_dialog(self):
        dialog = tk.Toplevel(self.master)
        dialog.title("Настройка приоритетов и фиксации")
        dialog.transient(self.master)
        dialog.grab_set()
        tk.Label(dialog, text="Столбец").grid(row=0, column=0, padx=5, pady=5)
        tk.Label(dialog, text="Приоритет").grid(row=0, column=1, padx=5, pady=5)
        tk.Label(dialog, text="Фикс.").grid(row=0, column=2, padx=5, pady=5)
        tk.Label(dialog, text="Строка").grid(row=0, column=3, padx=5, pady=5)
        priority_vars = {}
        fixed_vars = {}
        row_vars = {}
        for col in range(1, self.num_queens + 1):
            tk.Label(dialog, text=f"{col}").grid(row=col, column=0, padx=5, pady=2)
            var_prio = tk.IntVar(value=self.priorities.get(col, col))
            priority_vars[col] = var_prio
            tk.Spinbox(dialog, from_=1, to=self.num_queens, textvariable=var_prio, width=5).grid(row=col, column=1, padx=5)
            var_fixed = tk.BooleanVar(value=(col in self.fixed_positions))
            fixed_vars[col] = var_fixed
            tk.Checkbutton(dialog, variable=var_fixed).grid(row=col, column=2, padx=5)
            var_row = tk.IntVar(value=self.fixed_positions.get(col, 1))
            row_vars[col] = var_row
            spin = tk.Spinbox(dialog, from_=1, to=self.board_size, textvariable=var_row, width=5)
            spin.grid(row=col, column=3, padx=5)
            def toggle_spin(*args, s=spin, v=var_fixed):
                s.config(state='normal' if v.get() else 'disabled')
            var_fixed.trace_add('write', toggle_spin)
            toggle_spin()
        def save_settings():
            used = set()
            for col, var in priority_vars.items():
                p = var.get()
                if p in used:
                    messagebox.showerror("Ошибка", "Приоритеты должны быть уникальны")
                    return
                used.add(p)
            self.priorities = {col: priority_vars[col].get() for col in range(1, self.num_queens+1)}
            self.fixed_positions = {}
            for col in range(1, self.num_queens+1):
                if fixed_vars[col].get():
                    self.fixed_positions[col] = row_vars[col].get()
            dialog.destroy()
            messagebox.showinfo("Готово", "Настройки сохранены")
        tk.Button(dialog, text="Сохранить", command=save_settings).grid(row=self.num_queens+1, column=0, columnspan=4, pady=10)