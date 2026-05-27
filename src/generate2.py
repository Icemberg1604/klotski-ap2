import json
import random
from pathlib import Path
import graph_tool.all as gt
from puzzle import Puzzle, State, Piece, Coord 
from eval import puzzle_evaluation 
from graph import PuzzleGraphBuilder, build_graph_bfs

# --- Pieces Definition ---

def norm(coords: list[Coord]) -> Piece: 
    """
    Returns the standarized representation of a piece.
    Coords (list[Coord]): List of coordinates of the piece.
    """

    return Piece.normalized(coords)


#Has a dictionary with some of the pieces which are grouped by size and selected with a 
#weight that delimits the probability of being choosen in the generation process.

AREAS = {
    # 1x1 Blocks
    1: ([
        norm([(0,0)])
    ], 4),
    
    #1x2
    2: ([
        norm([(0,0), (0,1)]), 
        norm([(0,0), (1,0)])
    ], 6),
    
    # 1x3 and L-shapes
    3: ([norm(c) for c in [
        [(0,0), (0,1), (0,2)], [(0,0), (1,0), (2,0)], 
        [(0,0), (0,1), (1,1)], [(0,0), (1,0), (0,1)], 
        [(0,0), (1,0), (1,1)], [(1,0), (0,1), (1,1)]
    ]], 2),
    
    # 1x4, 2x2 and other shapes
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

# --- Helper functions for the process ---

class Canonicalizer:
    """
    Checks that the puzzle is valid and formats it into a canonical state.
    """

    w: int #width
    h: int #height

    walls: tuple[Coord,...]
    pieces: list[Piece]
    start_positions: list[Coord] #starting positions of the pieces
    goals: list[tuple[int, Coord]]

    #the canonical position of the pieces
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

        #creates a list of tuples (piece, position, original index)
        for old_idx, (piece, pos) in enumerate(zip(self.pieces, self.start_positions)):
            paired.append((piece, pos, old_idx))

        #sorts the pieces based on their shape and position
        paired.sort(key=lambda x: (x[0], x[1]))
        
        #assigns new indices to the pieces
        for new_idx, (piece, pos, old_idx) in enumerate(paired):
            self.canon_pieces.append(piece)
            self.canon_positions.append(pos)
            self.old_to_new_idx[old_idx] = new_idx #saves the old index for being able to map the goals

    def mapping_objectives(self) -> None:
        """
        Maps the original goal indices to their newly assigned canonical indices.
        """

        #iterates through the goals to find them in the new order
        for old_idx, target_pos in self.goals:
            new_idx = self.old_to_new_idx[old_idx]
            self.canon_goals.append((new_idx, tuple(target_pos))) #type: ignore
        self.canon_goals.sort()

    def make_canonical(self) -> Puzzle:
        """
        Processes the puzzle state and returns a canonicalized Puzzle instance with normalized indices and positions.
        """

        self.translator_indexes() #reorders the pieces and positions
        self.mapping_objectives() #reorders the goals
        canon_state = State(tuple(self.canon_positions)) #creates the canonical state

        #returns the canonical puzzle
        return Puzzle(
            W=self.w,
            H=self.h,
            walls=self.walls,
            pieces=tuple(self.canon_pieces),
            start=canon_state,
            goals=tuple(self.canon_goals)
        )

# --- Generation Logic ---

def create_seed(w: int, h: int) -> Puzzle:
    """
    Generates a random valid solved puzzle (seed) ensuring larger pieces fit first.
    w and h are the width and height of the puzzle.
    """

    target_area: int = 0
    pieces: list[Piece] = []
    cur_area: int = 0
    gx: int = 0 #position of the goal piece in x
    gy: int = 0 #position of the goal piece in y

    # Randomly leave 1 to 5 empty spaces to create variety in puzzle density.
    target_area = w*h - random.randint(1, 5)
    
    # Always start with an area 4 piece (the goal piece)
    pieces = [random.choice(AREAS[4][0])]
    cur_area = 4
    

    # Fill remaining board area with random pieces based on their weights
    while cur_area < target_area:
        valid_areas = [a for a in AREAS if a <= target_area - cur_area]

        #selects the next piece based on the weights and area
        chosen_area = random.choices(valid_areas, weights=[AREAS[a][1] for a in valid_areas])[0]
        pieces.append(random.choice(AREAS[chosen_area][0]))
        cur_area += chosen_area

    #Initialize empty board tracking and piece positions
    board = [[False] * h for _ in range(w)]
    pos = [(-1, -1)] * len(pieces) #stores the positions of the pieces
    
    #Place goal piece randomly without going out of bounds
    gx = random.randint(0, w - max(dx for dx, _ in pieces[0].coords) - 1) #Calculates the maximum x position the goal piece can be placed
    gy = random.randint(0, h - max(dy for _, dy in pieces[0].coords) - 1)#Calculates the maximum y position the goal piece can be placed
    
    def try_place(p: Piece, px: int, py: int) -> bool:
        """
        Helper to check if a piece fits at (px, py) and mark it on the board if it does.
        Checks two conditions for each coordinate of the piece:

        1: 0 <= px+dx < w and 0 <= py+dy < h --> The piece is within the board
        2: not board[px+dx][py+dy] --> The piece is not overlapping with other pieces
        """
        if all(0 <= px+dx < w and 0 <= py+dy < h and not board[px+dx][py+dy] for dx, dy in p.coords):
            for dx, dy in p.coords: 
                board[px+dx][py+dy] = True
            return True
        return False
        
    try_place(pieces[0], gx, gy)
    pos[0] = (gx, gy)
    

    #Place the rest of the pieces.
    #We sort them by size (largest first) to avoid packing errors. (i.e. a 1x1 piece can always fit, unlike a 2x2)
    indices_by_size = sorted(range(1, len(pieces)), key=lambda i: len(pieces[i].coords), reverse=True)
    

    #Tries to place each piece in every available spot 
    #but stopping once it finds one (greedy algorithm)
    for idx in indices_by_size:

        # checks if the piece can be placed at every position (x, y), until one is found
        valid_spot = next(
            ((x, y) for y in range(h) for x in range(w) if try_place(pieces[idx], x, y)), 
            None
        )

        #Raises exception if no spot is found
        if valid_spot is None:
            raise Exception(f"Piece {idx} doesn't fit on the board!")

        pos[idx] = valid_spot

    #Creates the canonical puzzle
    canonicalizer = Canonicalizer(
        w=w, h=h, walls=[], pieces=list(pieces), 
        start_positions=pos, goals=[(0, (gx, gy))]
    )
    return canonicalizer.make_canonical()


# --- Puzzle Extraction and Evaluation ---

def get_hardest(seed: Puzzle, g: gt.Graph, min_req: int) -> Puzzle:
    
    """
    Finds the furthest state from all goals natively using graph-tool BFS dummy vertex trick.
    """

    # 1. Identify all goal nodes, default to the initial state if none exist
    goals = gt.find_vertex(g, g.vp["is_goal"], True) or [g.vertex(0)]

    # 2. Attach a dummy node to all goals to calculate distances simultaneously
    dummy = g.add_vertex()
    for v in goals: 
        g.add_edge(dummy, v)

    # 3. Calculate distance and clean up
    dists = gt.shortest_distance(g, source=dummy).a[:-1] - 1
    g.remove_vertex(dummy)
    
    # Raises exception if the graph is too simple (max depth is less than min_req)
    max_d = dists.max()
    if max_d < min_req:
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

def generate_puzzle(threshold: float, num_puzzles: int = 1, min_steps: int = 30):
    """
    Main loop generating, solving, and evaluating puzzles until threshold is met.
    """
    Path("puzzles").mkdir(exist_ok=True)
    candidate = 1
    print(f"Generating puzzles until finding one with evaluation > {threshold}...\n")
    
    while True:
        try:
            w, h = random.choice([4, 5, 6]), 5

            #creates a random valid solved puzzle
            seed = create_seed(w, h)

            #finds a new puzzle with maximum difficulty possible, based on the seed
            hardest = get_hardest(seed, build_graph_bfs(seed), min_steps)
            eval_graph = build_graph_bfs(hardest)
            score = puzzle_evaluation(eval_graph, f"cand_{candidate}", save_to_disk=False)
            print(f"Candidate {candidate} (w={w}): Score {score}")
            

            #Checks if the score is higher than the threshold
            if score > threshold:
                print(f"   -> Success! Exceeded the threshold of {threshold}.")
                
                #Save safely without overwriting
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
