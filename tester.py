# tester.py
import sys
import sys
import glob
import os
from collections import deque
from q2 import solve_sokoban  # student functions


UNSAT = -1
SAT = 1

def parse_input(input_path):
    with open(input_path) as f:
        first_line = f.readline().strip().split()
        T = int(first_line[0])
        board = []
        for line in f:  # reads until EOF
            row = line.strip().split()
            if row:  # skip empty lines if any
                board.append(row)
    return board, T

def verify_solution(board, moves, T):
    """
    board: 2D list of characters ['#','P','B','G','.']
    moves: list of moves ['U','D','L','R']
    n: size of board
    T: max moves allowed
    """
    n = len(board)
    m = len(board[0])


    if len(moves) > T:
        return False

    player_pos = None
    goals = set()

    for i in range(n):
        for j in range(m):
            if board[i][j] == 'P':
                player_pos = (i, j)
                board[i][j] = '.'
            if board[i][j] == 'G':
                goals.add((i, j))

    if not player_pos:
        return False

    DIRS = {'U': (-1, 0), 'D': (1, 0), 'L': (0, -1), 'R': (0, 1)}

    for move in moves:
        if move not in DIRS:
            return False

        di, dj = DIRS[move]
        pi, pj = player_pos
        ni, nj = pi + di, pj + dj

        if not (0 <= ni < n and 0 <= nj < m):
            return False
        if board[ni][nj] == '#':
            return False

        if board[ni][nj] == 'B':
            bi, bj = ni + di, nj + dj
            if not (0 <= bi < n and 0 <= bj < m):
                return False
            if board[bi][bj] in ['#', 'B']:
                return False
            board[bi][bj] = 'B'
            board[ni][nj] = '.'

        player_pos = (ni, nj)

    # for each box, check if its on a goal
    for i in range(n):
        for j in range(m):
            if board[i][j] == 'B':
                if (i, j) not in goals:
                    return False


    return True

def is_sokoban_solvable(grid, T):
    rows = len(grid)
    cols = len(grid[0])
    G = [list(row) for row in grid]

    # Parse positions
    player = None
    boxes = set()
    goals = set()
    for i in range(rows):
        for j in range(cols):
            c = G[i][j]
            if c == 'P':
                player = (i, j)
                G[i][j] = '.'  # treat as empty for movement
            elif c == 'B':
                boxes.add((i, j))
            elif c == 'G':
                goals.add((i, j))

    if player is None:
        raise ValueError("No player found.")

    # Quick checks
    if not boxes:
        return True  # trivially satisfied
    if boxes.issubset(goals):
        return True

    dirs = [(-1,0), (1,0), (0,-1), (0,1)]

    def in_bounds(x, y):
        return 0 <= x < rows and 0 <= y < cols

    # BFS
    start_state = (player, frozenset(boxes))
    q = deque()
    q.append((player, frozenset(boxes), 0))
    visited = {start_state}

    while q:
        ppos, box_set, steps = q.popleft()

        if steps > T:
            continue

        # Goal check
        if box_set.issubset(goals):
            return SAT

        px, py = ppos
        for dx, dy in dirs:
            nx, ny = px + dx, py + dy

            if not in_bounds(nx, ny):
                continue
            if G[nx][ny] == '#':
                continue

            new_boxes = set(box_set)
            if (nx, ny) in box_set:
                # Trying to push box
                bx, by = nx + dx, ny + dy
                if not in_bounds(bx, by):
                    continue
                if G[bx][by] == '#' or (bx, by) in box_set:
                    continue
                # Push the box
                new_boxes.remove((nx, ny))
                new_boxes.add((bx, by))

            new_state = ((nx, ny), frozenset(new_boxes))
            if new_state not in visited:
                visited.add(new_state)
                q.append(((nx, ny), frozenset(new_boxes), steps + 1))

    return UNSAT

def run_testcase(path):
    board, T = parse_input(path)
    result = solve_sokoban([row[:] for row in board], T)  # copy board so we don't mutate original
    expected_result = is_sokoban_solvable(board, T)
    if expected_result == UNSAT:
        return result == UNSAT
    
    return verify_solution(board, result, T)

if __name__ == "__main__":
    # If arguments given → use them; else → find all .txt testcases in folder
    if len(sys.argv) > 1:
        testcases = sys.argv[1:]
    else:
        testcases = sorted(glob.glob("input/*.txt"))

    if not testcases:
        print("No testcases found.")
        sys.exit(1)

    passed = 0
    for idx, tc in enumerate(testcases, start=1):
        if run_testcase(tc):
            print(f"Testcase {idx} ({os.path.basename(tc)}): Passed ✅")
            passed += 1
        else:
            print(f"Testcase {idx} ({os.path.basename(tc)}): Failed ❌")
            print(f"Expected: {is_sokoban_solvable(parse_input(tc)[0], parse_input(tc)[1])}")
            print(f"Got: {solve_sokoban(parse_input(tc)[0], parse_input(tc)[1])}")

    print(f"\nSummary: {passed}/{len(testcases)} testcases passed.")
