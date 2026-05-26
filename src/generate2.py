import json
import random
from pathlib import Path
import graph_tool.all as gt
from puzzle import Puzzle, State, Piece, Coord 
from eval import puzzle_evaluation 
from graph import PuzzleGraphBuilder 

# =====================================================================
# 1. PIECE DEFINITIONS (Compressed but readable)
# =====================================================================
def norm(coords): 
    return Piece.normalized(coords)

# Format: AREA_SIZE: (list_of_pieces, selection_weight)
# We use weights to heavily favor small pieces to avoid locking the board,
# but we give the goal piece (area 4) a low random weight to control puzzle flow.
AREAS = {
    # 1x1 Blocks
    1: ([
        norm([(0,0)])
    ], 4),
    
    # Dominoes (1x2 Vertical and Horizontal)
    2: ([
        norm([(0,0), (0,1)]), 
        norm([(0,0), (1,0)])
    ], 6),
    
    # Trominoes (L-shapes and straight 3s)
    3: ([norm(c) for c in [
        [(0,0), (0,1), (0,2)], [(0,0), (1,0), (2,0)], 
        [(0,0), (0,1), (1,1)], [(0,0), (1,0), (0,1)], 
        [(0,0), (1,0), (1,1)], [(1,0), (0,1), (1,1)]
    ]], 2),
    
    # Tetrominoes (Z, S, L, J, I, and the 2x2 Square goal piece)
    4: ([norm(c) for c in [
        [(0,0), (1,0), (1,1), (2,1)], [(1,0), (0,1), (1,1), (0,2)], 
        [(1,0), (2,0), (0,1), (1,1)], [(0,0), (0,1), (1,1), (1,2)],
        [(0,0), (0,1), (0,2), (1,2)], [(0,0), (1,0), (2,0), (0,1)], 
        [(0,0), (1,0), (1,1), (1,2)], [(2,0), (0,1), (1,1), (2,1)],
        [(1,0), (1,1), (0,2), (1,2)], [(0,0), (0,1), (1,1), (2,1)], 
        [(0,0), (1,0), (0,1), (0,2)], [(0,0), (1,0), (2,0), (2,1)],
        [(0,0), (0,1), (0,2), (0,3)], [(0,0), (1,0), (2,0), (3,0)], 
        [(0,0), (0,1), (1,0), (1,1)] # 2x2 Square
    ]], 1)
}

# =====================================================================
# 2. HELPER FUNCTIONS AND FORMATTERS
# =====================================================================
def build_graph(p: Puzzle) -> gt.Graph:
    """
    Wrapper to instantly expand a puzzle into its state-space graph.
    """
    return PuzzleGraphBuilder(p, p.to_json()).build()

class Canonicalizer:
    """Checks that the puzzle is valid and formats it into a canonical state."""
    w: int
    h: int

    walls: tuple[Coord,...]
    pieces: list[Piece]
    start_positions: list[Coord]
    goals: list[tuple[int, Coord]]

    canon_pieces: list[Piece]
    canon_positions: list[Coord]
    canon_goals: list[tuple[int, Coord]]

    old_to_new_idx: dict[int, int]
    
    def __init__(self, w: int, h: int, walls: list[Coord], pieces: list[Piece], start_positions: list[Coord], goals: list[tuple[int, Coord]]) -> None:
        """
        Initializes the Canonicalizer with the puzzle's dimensions, walls, pieces, starting positions, and goals.
        """
        self.w = w
        self.h = h

        self.walls = tuple(sorted(set(walls)))
        self.pieces = pieces
        self.start_positions = start_positions
        self.goals = goals
        
        self.canon_pieces = []
        self.canon_positions = []
        self.old_to_new_idx = {}

        self.canon_goals = []

    def translator_indexes(self) -> None:
        """
        Pairs pieces with their starting positions and assigns new canonical indices to them, sorting them for consistency.
        """
        paired = []
        for old_idx, (piece, pos) in enumerate(zip(self.pieces, self.start_positions)):
            paired.append((piece, pos, old_idx))
            
        paired.sort(key=lambda x: (x[0], x[1]))
        
        for new_idx, (piece, pos, old_idx) in enumerate(paired):
            self.canon_pieces.append(piece)
            self.canon_positions.append(pos)
            self.old_to_new_idx[old_idx] = new_idx

    def mapping_objectives(self) -> None:
        """
        Maps the original goal indices to their newly assigned canonical indices.
        """
        for old_idx, target_pos in self.goals:
            new_idx = self.old_to_new_idx[old_idx]
            self.canon_goals.append((new_idx, tuple(target_pos))) #type: ignore
        self.canon_goals.sort()

    def make_canonical(self) -> Puzzle:
        """
        Processes the puzzle state and returns a canonicalized Puzzle instance with normalized indices and positions.
        """
        self.translator_indexes()
        self.mapping_objectives()
        canon_state = State(tuple(self.canon_positions))
        
        return Puzzle(
            W=self.w,
            H=self.h,
            walls=self.walls,
            pieces=tuple(self.canon_pieces),
            start=canon_state,
            goals=tuple(self.canon_goals)
        )

# =====================================================================
# 3. GENERATION LOGIC
# =====================================================================
def create_seed(w: int, h: int) -> Puzzle:
    """Generates a random valid solved puzzle (seed) ensuring larger pieces fit first."""
    
    # Randomly leave 1 to 5 empty spaces to create variety in puzzle density.
    target_area = w*h - random.randint(1, 5)
    
    # Always start with an area 4 piece (the goal piece)
    pieces = [random.choice(AREAS[4][0])]
    cur_area = 4
    
    # Fill remaining board area with random pieces based on their weights
    while cur_area < target_area:
        valid_areas = [a for a in AREAS if a <= target_area - cur_area]
        chosen_area = random.choices(valid_areas, weights=[AREAS[a][1] for a in valid_areas])[0]
        pieces.append(random.choice(AREAS[chosen_area][0]))
        cur_area += chosen_area

    # Initialize empty board tracking and piece positions
    board = [[False] * h for _ in range(w)]
    pos = [(-1, -1)] * len(pieces)
    
    # Place goal piece randomly without going out of bounds
    gx = random.randint(0, w - max(dx for dx, _ in pieces[0].coords) - 1)
    gy = random.randint(0, h - max(dy for _, dy in pieces[0].coords) - 1)
    
    def try_place(p: Piece, px: int, py: int) -> bool:
        """Helper to check if a piece fits at (px, py) and mark it on the board if it does."""
        if all(0 <= px+dx < w and 0 <= py+dy < h and not board[px+dx][py+dy] for dx, dy in p.coords):
            for dx, dy in p.coords: 
                board[px+dx][py+dy] = True
            return True
        return False
        
    try_place(pieces[0], gx, gy)
    pos[0] = (gx, gy)
    
    # Place rest of pieces, sorted by size (largest first) to avoid packing errors (Bin-packing heuristic)
    indices_by_size = sorted(range(1, len(pieces)), key=lambda i: len(pieces[i].coords), reverse=True)
    
    for idx in indices_by_size:
        valid_spot = next(
            ((x, y) for y in range(h) for x in range(w) if try_place(pieces[idx], x, y)), 
            None
        )
        if valid_spot is None:
            raise Exception(f"Piece {idx} doesn't fit on the board!")
        pos[idx] = valid_spot
            
    canonicalizer = Canonicalizer(
        w=w, h=h, walls=[], pieces=list(pieces), 
        start_positions=pos, goals=[(0, (gx, gy))]
    )
    return canonicalizer.make_canonical()

# =====================================================================
# 4. EXTRACTION AND EVALUATION
# =====================================================================
def get_hardest(seed: Puzzle, g: gt.Graph) -> Puzzle:
    """Finds the furthest state from all goals natively using graph-tool BFS dummy vertex trick."""
    
    # 1. Identify all goal nodes, default to the initial state if none exist
    goals = gt.find_vertex(g, g.vp["is_goal"], True) or [g.vertex(0)]
    
    # 2. Attach a dummy node to all goals to calculate distances simultaneously
    dummy = g.add_vertex()
    for v in goals: 
        g.add_edge(dummy, v)
        
    # 3. Calculate distance and clean up
    dists = gt.shortest_distance(g, source=dummy).a[:-1] - 1
    g.remove_vertex(dummy)
    
    max_d = dists.max()
    if max_d < 30:
        raise ValueError(f"Graph too simple (max depth is only {max_d} moves)")
    
    # 4. Find the absolute furthest states from the goals
    furthest = int(random.choice((dists >= max_d - 2).nonzero()[0]))
    print(f"   -> Extracted level with a depth of {dists[furthest]} perfect moves from nearest goal.")
    
    # 5. Rebuild the puzzle at this new hardest starting state
    new_pos = [tuple(c) for c in json.loads(g.vp["state"][g.vertex(furthest)])]
    
    canonicalizer = Canonicalizer(
        w=seed.W, h=seed.H, walls=list(seed.walls), 
        pieces=list(seed.pieces), start_positions=new_pos, goals=list(seed.goals)
    )
    return canonicalizer.make_canonical()

def generate_puzzle(threshold: float, num_puzzles: int = 1):
    """
    Main loop generating, solving, and evaluating puzzles until threshold is met.
    """
    Path("puzzles").mkdir(exist_ok=True)
    candidate = 1
    print(f"Generating puzzles until finding one with evaluation > {threshold}...\n")
    
    while True:
        try:
            w, h = random.choice([4, 5, 6]), 5
            # 1. Generate Solved State (Seed)
            seed = create_seed(w, h)
            # 2. Expand Graph and Extract Hardest Unsolved State
            hardest = get_hardest(seed, build_graph(seed))
            # 3. Rebuild Graph from the Hardest State for evaluation
            eval_graph = build_graph(hardest)
            score = puzzle_evaluation(eval_graph, f"cand_{candidate}", save_to_disk=False)
            print(f"Candidate {candidate} (w={w}): Score {score}")
            
            # 4. Filter Quality
            if score > threshold:
                print(f"   -> Success! Exceeded the threshold of {threshold}.")
                # Save safely without overwriting
                fn, c = Path("puzzles") / f"generated_{score}.json", 2
               
                while fn.exists(): 
                    fn = Path("puzzles") / f"generated_{score}_{c}.json"
                    c += 1
                    
                fn.write_text(hardest.to_json(indent=4), encoding="utf-8")
                print(f"\nPuzzle generated and saved successfully to {fn}")
                return
                
        except Exception as e:
            print(f"Candidate {candidate} discarded due to error: {e}")
            
        candidate += 1

def main():
    generate_puzzle(threshold=3.5)

if __name__ == "__main__": 
    main()
