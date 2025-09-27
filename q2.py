# q2.py
from pysat.formula import CNF
from pysat.solvers import Solver

DIRS = {'U': (-1, 0), 'D': (1, 0), 'L': (0, -1), 'R': (0, 1)}
DIRS_LIST = list(DIRS.items())
DIR_IDX = {'U': 0, 'D': 1, 'L': 2, 'R': 3}

class SokobanEncoder:
    def __init__(self, grid, T):
        # Ensure mutable grid of chars
        self.grid = [list(row) for row in grid]
        self.T = T
        self.N = len(self.grid)
        self.M = len(self.grid[0])

        self.goals = []
        self.boxes = []
        self.player_start = None
        self._parse_grid()

        self.num_boxes = len(self.boxes)
        # precompute free cells
        self.free_cells = [(i, j) for i in range(self.N) for j in range(self.M) if self.grid[i][j] != '#']

        # per-time-slot variable layout:
        # [player (N*M)] + [boxes (num_boxes * N*M)] + [moves (4)] + [pushed flags (num_boxes)]
        self.slot_size = self.N*self.M*(1 + self.num_boxes) + 4 + self.num_boxes

        self.cnf = CNF()

    def _parse_grid(self):
        for i in range(self.N):
            for j in range(self.M):
                c = self.grid[i][j]
                if c == 'P':
                    self.player_start = (i, j)
                    self.grid[i][j] = '.'
                elif c == 'B':
                    self.boxes.append((i, j))
                    self.grid[i][j] = '.'
                elif c == 'G':
                    self.goals.append((i, j))
                    self.grid[i][j] = '.'

    # ------------- Variable encoding -------------
    def _base_t(self, t):
        return 1 + t * self.slot_size

    def var_player(self, x, y, t):
        return self._base_t(t) + (x * self.M + y)

    def var_box(self, b, x, y, t):
        return self._base_t(t) + self.N*self.M + b*(self.N*self.M) + (x*self.M + y)

    def var_move(self, d, t):
        # only meaningful for t in [0..T-1], but allocated for all t
        return self._base_t(t) + self.N*self.M*(1 + self.num_boxes) + DIR_IDX[d]

    def var_pushed(self, b, t):
        return self._base_t(t) + self.N*self.M*(1 + self.num_boxes) + 4 + b

    # ------------- Helpers -------------
    def in_free(self, x, y):
        return 0 <= x < self.N and 0 <= y < self.M and self.grid[x][y] != '#'

    # ------------- Encoding -------------
    def encode(self):
        cnf = CNF()
        N, M, T = self.N, self.M, self.T
        B = self.num_boxes

        # --- Initial conditions ---
        px, py = self.player_start
        cnf.append([self.var_player(px, py, 0)])
        for b, (bx, by) in enumerate(self.boxes):
            cnf.append([self.var_box(b, bx, by, 0)])

        # --- Per-time constraints for t = 0..T (states exist at final step too) ---
        for t in range(T + 1):
            # Exactly one player position
            pvars = [self.var_player(x, y, t) for (x, y) in self.free_cells]
            cnf.append(pvars)  # at least one
            for i in range(len(pvars)):
                for j in range(i + 1, len(pvars)):
                    cnf.append([-pvars[i], -pvars[j]])  # at most one

            # Each box occupies exactly one cell
            for b in range(B):
                bvars = [self.var_box(b, x, y, t) for (x, y) in self.free_cells]
                cnf.append(bvars)
                for i in range(len(bvars)):
                    for j in range(i + 1, len(bvars)):
                        cnf.append([-bvars[i], -bvars[j]])

            # No two boxes share a cell
            for x, y in self.free_cells:
                for b1 in range(B):
                    for b2 in range(b1 + 1, B):
                        cnf.append([-self.var_box(b1, x, y, t), -self.var_box(b2, x, y, t)])

            # Player never on a box
            for x, y in self.free_cells:
                for b in range(B):
                    cnf.append([-self.var_player(x, y, t), -self.var_box(b, x, y, t)])

        # --- Action (move) variables and dynamics for t = 0..T-1 ---
        for t in range(T):
            # Exactly one move per step
            mvars = [self.var_move(d, t) for d, _ in DIRS_LIST]
            cnf.append(mvars)
            for i in range(4):
                for j in range(i + 1, 4):
                    cnf.append([-mvars[i], -mvars[j]])

            # At most one box is pushed per step (optional but clean)
            if B >= 2:
                for b1 in range(B):
                    for b2 in range(b1 + 1, B):
                        cnf.append([-self.var_pushed(b1, t), -self.var_pushed(b2, t)])

            # Movement/push rules
            for x, y in self.free_cells:
                p_t = self.var_player(x, y, t)

                for d, (dx, dy) in DIRS_LIST:
                    m_t_d = self.var_move(d, t)
                    nx, ny = x + dx, y + dy

                    # If neighbor is a wall/out of bounds, that move cannot be chosen from (x,y)
                    if not self.in_free(nx, ny):
                        cnf.append([-p_t, -m_t_d])
                        continue

                    # Simple step into empty neighbor:
                    # move(d,t) & player(x,y,t) & (no box at nx,ny,t) -> player(nx,ny,t+1)
                    p_next = self.var_player(nx, ny, t + 1)
                    clause = [-m_t_d, -p_t, p_next]
                    # gate with "or a box is there" to avoid forcing when push case applies
                    for b in range(B):
                        clause.append(self.var_box(b, nx, ny, t))
                    cnf.append(clause)

                    # Push case: if a box is at (nx,ny), we must have destination free and update it
                    nnx, nny = nx + dx, ny + dy

                    for b in range(B):
                        box_front = self.var_box(b, nx, ny, t)

                        # If destination not free, pushing is illegal from this state:
                        if not self.in_free(nnx, nny):
                            cnf.append([-m_t_d, -p_t, -box_front])
                            continue

                        # Destination cell must be empty of boxes at time t for a valid push
                        for bb in range(B):
                            cnf.append([-m_t_d, -p_t, -box_front, -self.var_box(bb, nnx, nny, t)])

                        # Effects of a valid push:
                        # move(d,t) & player(x,y,t) & box_b at (nx,ny,t)  -> player(nx,ny,t+1)
                        cnf.append([-m_t_d, -p_t, -box_front, self.var_player(nx, ny, t + 1)])
                        # and box_b moves to (nnx,nny) at t+1
                        cnf.append([-m_t_d, -p_t, -box_front, self.var_box(b, nnx, nny, t + 1)])
                        # mark "pushed" for that box
                        cnf.append([-m_t_d, -p_t, -box_front, self.var_pushed(b, t)])

            # Box persistence unless pushed
            for b in range(B):
                pushed_bt = self.var_pushed(b, t)
                for x, y in self.free_cells:
                    cnf.append([-self.var_box(b, x, y, t), pushed_bt, self.var_box(b, x, y, t + 1)])

        # --- Goal condition at final step (t = T): every box on some goal cell ---
        final_t = T
        for b in range(B):
            clause = [self.var_box(b, gx, gy, final_t) for (gx, gy) in self.goals if self.in_free(gx, gy)]
            # If there are no valid goal cells (shouldn't happen), keep it robust
            cnf.append(clause if clause else [-1])  # unsat if no goals

        self.cnf = cnf
        return cnf


def decode(model, encoder: SokobanEncoder):
    # Prefer decoding from move variables (deterministic & simpler)
    moves = []
    for t in range(encoder.T):
        for d, _ in DIRS_LIST:
            v = encoder.var_move(d, t)
            if v in model:
                moves.append(d)
                break
    return moves


def solve_sokoban(grid, T):
    encoder = SokobanEncoder(grid, T)
    cnf = encoder.encode()
    with Solver(name='g3') as solver:
        solver.append_formula(cnf)
        if not solver.solve():
            return -1
        model = solver.get_model()
        if not model:
            return -1
        return decode(model, encoder)
