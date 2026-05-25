import json
import random
import os
from pathlib import Path
from typing import Optional
from dataclasses import dataclass
import graph_tool.all as gt
from puzzle import Puzzle, State, Piece, Coord 
from eval import puzzle_evaluation 
from graph import PuzzleGraphBuilder 

# =====================================================================
# 1. CONFIGURATION AND FORMATTING CLASSES
# =====================================================================

@dataclass
class PuzzleConfig:
    """Defines the structural rules for generating a puzzle."""
    w: int
    h: int
    pieces: list[Piece]
    goal_idx: int = 0
    goal_pos: Coord = (1, 3) 

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
        """Initializes the Canonicalizer with the puzzle's dimensions, walls, pieces, starting positions, and goals."""
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
        """Pairs pieces with their starting positions and assigns new canonical indices to them, sorting them for consistency."""
        paired = []
        for old_idx, (piece, pos) in enumerate(zip(self.pieces, self.start_positions)):
            paired.append((piece, pos, old_idx))
            
        paired.sort(key=lambda x: (x[0], x[1]))
        
        for new_idx, (piece, pos, old_idx) in enumerate(paired):
            self.canon_pieces.append(piece)
            self.canon_positions.append(pos)
            self.old_to_new_idx[old_idx] = new_idx

    def mapping_objectives(self) -> None:
        """Maps the original goal indices to their newly assigned canonical indices."""
        for old_idx, target_pos in self.goals:
            new_idx = self.old_to_new_idx[old_idx]
            self.canon_goals.append((new_idx, tuple(target_pos))) #type: ignore
        self.canon_goals.sort()

    def make_canonical(self) -> Puzzle:
        """Processes the puzzle state and returns a canonicalized Puzzle instance with normalized indices and positions."""
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
# 2. THE SEED FACTORY (SOLVED STATES)
# =====================================================================

class PuzzleGenerator:
    """The Factory class for creating valid solved Klotski puzzles (Seeds)."""
    
    def __init__(self):
        """Initializes the factory with sets of pieces normalized by their area."""
        self.BLOCK_2x2 = Piece.normalized([(0,0), (0,1), (1,0), (1,1)])
        
        # Area 1
        self.area_1 = [Piece.normalized([(0,0)])]
        
        # Area 2
        self.area_2 = [
            Piece.normalized([(0,0), (0,1)]), # V
            Piece.normalized([(0,0), (1,0)])  # H
        ]
        
        # Area 3 (I, L trominoes)
        self.area_3 = [
            Piece.normalized([(0,0), (0,1), (0,2)]),
            Piece.normalized([(0,0), (1,0), (2,0)]),
            Piece.normalized([(0,0), (0,1), (1,1)]),
            Piece.normalized([(0,0), (1,0), (0,1)]),
            Piece.normalized([(0,0), (1,0), (1,1)]),
            Piece.normalized([(1,0), (0,1), (1,1)])
        ]
        
        # Area 4 (Z, S, L, J, I tetrominoes)
        self.area_4 = [
            # Z, S
            Piece.normalized([(0,0), (1,0), (1,1), (2,1)]),
            Piece.normalized([(1,0), (0,1), (1,1), (0,2)]),
            Piece.normalized([(1,0), (2,0), (0,1), (1,1)]),
            Piece.normalized([(0,0), (0,1), (1,1), (1,2)]),
            # L, J
            Piece.normalized([(0,0), (0,1), (0,2), (1,2)]),
            Piece.normalized([(0,0), (1,0), (2,0), (0,1)]),
            Piece.normalized([(0,0), (1,0), (1,1), (1,2)]),
            Piece.normalized([(2,0), (0,1), (1,1), (2,1)]),
            Piece.normalized([(1,0), (1,1), (0,2), (1,2)]),
            Piece.normalized([(0,0), (0,1), (1,1), (2,1)]),
            Piece.normalized([(0,0), (1,0), (0,1), (0,2)]),
            Piece.normalized([(0,0), (1,0), (2,0), (2,1)]),
            # I
            Piece.normalized([(0,0), (0,1), (0,2), (0,3)]),
            Piece.normalized([(0,0), (1,0), (2,0), (3,0)]),
            # 2x2 Square
            self.BLOCK_2x2
        ]

    def _choose_fitting_piece(self, remaining_space: int) -> tuple[Piece, int]:
        """Selects a random piece that fits within the remaining space, favoring smaller pieces with assigned weights."""
        valid_areas = [1]
        if remaining_space >= 2: valid_areas.append(2)
        if remaining_space >= 3: valid_areas.append(3)
        if remaining_space >= 4: valid_areas.append(4)
        
        # We use weights to favor smaller pieces, avoiding complete board locks while keeping variety.
        weights = []
        for a in valid_areas:
            if a == 1: weights.append(4)
            elif a == 2: weights.append(6)
            elif a == 3: weights.append(2)
            elif a == 4: weights.append(1)
            
        chosen_area = random.choices(valid_areas, weights=weights)[0]
        
        if chosen_area == 1:
            elegida = random.choice(self.area_1)
        elif chosen_area == 2:
            elegida = random.choice(self.area_2)
        elif chosen_area == 3:
            elegida = random.choice(self.area_3)
        else:
            elegida = random.choice(self.area_4)
            
        return elegida, chosen_area

    def generate_random_template(self, w: int, h: int) -> list[Piece]:
        """Generates a random layout of pieces for a given width and height. The goal piece is randomly selected from area_4."""
        free_spaces = random.randint(1, 5)
        target_area = (w * h) - free_spaces
        
        # Use any area 4 piece as the goal piece
        goal_piece = random.choice(self.area_4)
        template = [goal_piece]
        current_area = 4
        
        while current_area < target_area:
            remaining_space = target_area - current_area
            nueva_pieza, area_nueva = self._choose_fitting_piece(remaining_space)
            template.append(nueva_pieza)
            current_area += area_nueva
                
        return template

    def _can_piece_fit(self, tablero: list[list[bool]], piece: Piece, x: int, y: int, w: int, h: int) -> bool:
        """Checks if a given piece can be placed at the specified coordinates without overlapping existing pieces or going out of bounds."""
        for dx, dy in piece.coords:
            nx, ny = x + dx, y + dy
            if nx >= w or ny >= h or tablero[nx][ny]:
                return False
        return True

    def _mark_piece_on_board(self, tablero: list[list[bool]], piece: Piece, x: int, y: int) -> None:
        """Marks the cells occupied by a piece on the internal boolean board representation."""
        for dx, dy in piece.coords:
            tablero[x + dx][y + dy] = True

    def _find_spot_and_place(self, tablero: list[list[bool]], piece: Piece, w: int, h: int) -> Coord:
        """Finds the first available spot on the board to place the piece and marks it. Raises an exception if no spot is found."""
        for y in range(h):
            for x in range(w):
                if self._can_piece_fit(tablero, piece, x, y, w, h):
                    self._mark_piece_on_board(tablero, piece, x, y)
                    return (x, y)
        raise Exception("Algorithmic error: The piece does not fit on the board.")
    
    def _create_solved_state_smart(self, config: PuzzleConfig) -> tuple[Puzzle, State]:
        """Creates a completely solved and valid puzzle configuration from the target pieces and goals."""
        tablero = [[False for _ in range(config.h)] for _ in range(config.w)]
        posiciones = [(-1, -1)] * len(config.pieces) 
        
        meta_piece = config.pieces[config.goal_idx]
        gx, gy = config.goal_pos
        self._mark_piece_on_board(tablero, meta_piece, gx, gy)
        posiciones[config.goal_idx] = (gx, gy)
        
        # Sort pieces by area (descending) so larger pieces get placed first.
        # This dramatically reduces piece packing errors caused by small pieces isolating grid cells.
        indices_restantes = [i for i in range(len(config.pieces)) if i != config.goal_idx]
        indices_restantes.sort(key=lambda i: len(config.pieces[i].coords), reverse=True)
        
        for idx in indices_restantes:
            piece = config.pieces[idx]
            pos = self._find_spot_and_place(tablero, piece, config.w, config.h)
            posiciones[idx] = pos

        canonicalizer = Canonicalizer(
            w=config.w, h=config.h, walls=[], pieces=config.pieces, 
            start_positions=posiciones, goals=[(config.goal_idx, config.goal_pos)]
        )
        puzzle = canonicalizer.make_canonical()
        return puzzle, puzzle.start

    def generate_seed(self, config: PuzzleConfig) -> Puzzle:
        """Returns a puzzle in its solved state, which acts as the seed for building the graph."""
        puzzle_resuelto, _ = self._create_solved_state_smart(config)
        return puzzle_resuelto


# =====================================================================
# 3. GRAPH EXTRACTION AND ORCHESTRATION
# =====================================================================

def extract_hardest_puzzle_from_graph(seed_puzzle: Puzzle, graph: gt.Graph) -> Puzzle:
    """
    Finds one of the vertices furthest from ALL goal states in the graph,
    and reconstructs the Puzzle with that new initial state.
    """
    # 1. Find all goal vertices in the graph
    v_goals = gt.find_vertex(graph, graph.vp["is_goal"], True)
    if len(v_goals) == 0:
        v_goals = [graph.vertex(0)]  # Fallback to seed node if none explicitly marked
        
    # 2. Create a dummy vertex connected to all goals to calculate distances from any goal natively in graph-tool
    v_dummy = graph.add_vertex()
    for v in v_goals:
        graph.add_edge(v_dummy, v)
        
    # 3. Calculate shortest distance from the dummy vertex to all other vertices
    # Subtract 1 because the dummy vertex adds 1 step to the real goal distances
    dist_array = gt.shortest_distance(graph, source=v_dummy).a[:-1] - 1
    
    # 4. Clean the graph by removing the dummy vertex (it's the last vertex, so it doesn't break indices)
    graph.remove_vertex(v_dummy)
    
    # 5. Clean unreachable nodes and find the maximum distance
    dist_array[dist_array >= 2147483646] = -1 
    max_dist = dist_array.max()
    
    # 6. Randomly pick one of the furthest nodes (within 2 steps of the maximum) to ensure variety
    candidatos = (dist_array >= max_dist - 2).nonzero()[0]
    furthest_node_idx = int(random.choice(candidatos))
    
    print(f"   -> Extracted level with a depth of {dist_array[furthest_node_idx]} perfect moves from nearest goal.")
    
    # 7. Modify the graph so it contains the solution from the furthest node to the objective
    nodo_lejano = graph.vertex(furthest_node_idx)
    vlist, elist = gt.shortest_path(graph, source=nodo_lejano, target=graph.vertex(0))
    moves = []
    for e in elist:
        moves.append([int(graph.ep["piece"][e]), str(graph.ep["direction"][e])])
    graph.graph_properties["solution"] = json.dumps(moves)
    
    # 8. Retrieve the raw state from the graph
    estado_crudo = json.loads(graph.vp["state"][graph.vertex(furthest_node_idx)])
    nuevas_posiciones = [tuple(coord) for coord in estado_crudo]

    # 9. Canonicalize the new puzzle
    canonicalizer = Canonicalizer(
        w=seed_puzzle.W, 
        h=seed_puzzle.H, 
        walls=list(seed_puzzle.walls), 
        pieces=list(seed_puzzle.pieces), 
        start_positions=nuevas_posiciones, 
        goals=list(seed_puzzle.goals)
    )
    return canonicalizer.make_canonical()

def generate_puzzle_above_threshold(threshold: float = 3.0) -> tuple[float, Puzzle]:
    """
    Generates random puzzles, explores their state space using reverse BFS from the goal,
    extracts the hardest starting position, and evaluates it until a puzzle scoring above 
    the given threshold is found. Randomizes the board dimensions (4x5, 5x5, 6x5) and the 
    goal piece position.
    """
    generador = PuzzleGenerator()
    candidate = 1

    print(f"Generating puzzles until finding one with evaluation > {threshold}...\n")
    
    while True:
        try:
            # Random dimensions: 4x5, 5x5, or 6x5
            w = random.choice([4, 5, 6])
            h = 5
            
            plantilla = generador.generate_random_template(w, h)
            
            # The first piece in the template is our goal piece (area 4)
            goal_piece = plantilla[0]
            
            # Calculate the dimensions of the goal piece to ensure the target position is valid
            min_x = min(dx for dx, dy in goal_piece.coords)
            max_x = max(dx for dx, dy in goal_piece.coords)
            min_y = min(dy for dx, dy in goal_piece.coords)
            max_y = max(dy for dx, dy in goal_piece.coords)
            
            gw = max_x - min_x + 1
            gh = max_y - min_y + 1
            
            # Random goal position without going out of bounds
            gx = random.randint(0, w - gw)
            gy = random.randint(0, h - gh)
            goal_pos = (gx, gy)
            goal_idx = 0

            config = PuzzleConfig(w=w, h=h, pieces=plantilla, goal_idx=goal_idx, goal_pos=goal_pos)
            
            # 1. Search via reverse BFS starting from the goal node (seed)
            seed = generador.generate_seed(config)
            
            # 2. Expand the complete graph universe
            builder = PuzzleGraphBuilder(seed, seed.to_json())
            graph = builder.build()
            
            # 3. Find one of the furthest points from the goals and prepare the new puzzle
            hardcore_puzzle = extract_hardest_puzzle_from_graph(seed, graph)
            
            # 4. FIX FOR EVALUATION MISMATCH:
            # eval.py assumes the graph starts at the initial state and searches for the goal.
            # We must build a new graph starting from hardcore_puzzle before evaluating it.
            eval_builder = PuzzleGraphBuilder(hardcore_puzzle, hardcore_puzzle.to_json())
            eval_graph = eval_builder.build()
            
            # 5. Evaluate the puzzle with the newly constructed graph
            nota = puzzle_evaluation(eval_graph, f"candidate_graph_{candidate}", save_to_disk=False)
            print(f"Candidate {candidate} (w={w}, pos={goal_pos}): Score {nota}")

            # 6. Quality filter based on the score
            if nota > threshold:
                print(f"   -> Success! Exceeded the threshold of {threshold}.")
                return nota, hardcore_puzzle
                
        except Exception as e:
            # Catch possible exceptions during graph creation or evaluation
            print(f"Candidate {candidate} discarded due to error: {e}")
            
        candidate += 1

def main():
    """
    Main execution point: ensures the directory exists, generates a high-quality puzzle, and saves it to disk with an uncolliding name.
    """
    
    # Ensure the target directory exists
    puzzles_dir = Path("puzzles")
    puzzles_dir.mkdir(exist_ok=True)
    
    # Generate the puzzle that exceeds 3.5
    nota, puzzle = generate_puzzle_above_threshold(3.5)
    
    # Handle repeated file names cleanly using pathlib
    base_filename = f"generado_{nota}"
    filename = puzzles_dir / f"{base_filename}.json"
    
    counter = 2
    while filename.exists():
        filename = puzzles_dir / f"{base_filename}_{counter}.json"
        counter += 1
        
    with open(filename, mode="w", encoding="utf-8") as f:
        f.write(puzzle.to_json(indent=4))
        
    print(f"\nPuzzle generated and saved successfully to {filename}")

if __name__ == "__main__":
    main()