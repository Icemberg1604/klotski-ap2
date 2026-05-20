import json
import random
from puzzle import Puzzle, State, Piece, Coord # Reutilizando tus clases existentes
import logic as lg
from eval import puzzle_evaluation # Tu juez implacable
from graph import PuzzleGraphBuilder # Tu constructor de grafos optimizado
from typing import Optional


class Canonicalizer:

    """
    Checks that the puzzle is valid and formats it into a canonical state.
    """

    w: int
    h: int
    walls: tuple[Coord,...]
    pieces: list[Piece]
    start_positions: list[Coord]
    goals: list[tuple[int, Coord]]

    canon_pieces: list[Piece]
    canon_positions: list[Coord]
    old_to_new_idx: dict[int, int]
    canon_goals: list[tuple[int, Coord]]
    

    def __init__(self, w: int, h: int, walls: list[Coord], pieces: list[Piece], start_positions: list[Coord], goals: list[tuple[int, Coord]]) -> None:
        self.w = w
        self.h = h

        # Sort the walls and remove duplicates immediately
        self.walls = tuple(sorted(set(walls)))
        self.pieces = pieces
        self.start_positions = start_positions
        self.goals = goals
        
        # Attributes to hold the translated data
        self.canon_pieces = []
        self.canon_positions = []
        self.old_to_new_idx = {}
        self.canon_goals = []

    def translator_indexes(self) -> None:
        """
        Matches pieces with their initial positions, sorts them canonically, 
        and builds a dictionary to translate old indexes to new ones.
        """
        paired = []
        for old_idx, (piece, pos) in enumerate(zip(self.pieces, self.start_positions)):
            paired.append((piece, pos, old_idx))
            
        # Since Piece has order=True, it will automatically sort by shape and then position
        paired.sort(key=lambda x: (x[0], x[1]))
        
        # Unpack the sorted result and populate class attributes
        for new_idx, (piece, pos, old_idx) in enumerate(paired):
            self.canon_pieces.append(piece)
            self.canon_positions.append(pos)
            self.old_to_new_idx[old_idx] = new_idx

    def mapping_objectives(self) -> None:
        """
        Updates the goal indexes using the translator dictionary and sorts them.
        """
        for old_idx, target_pos in self.goals:
            new_idx = self.old_to_new_idx[old_idx]
            self.canon_goals.append((new_idx, tuple(target_pos))) #type: ignore
            
        # We sort the goals
        self.canon_goals.sort()

    def make_canonical(self) -> Puzzle:
        """
        Executes the translation steps and returns the valid Puzzle object.
        """
        # Execute the formatting steps
        self.translator_indexes()
        self.mapping_objectives()
        
        canon_state = State(tuple(self.canon_positions))
        
        # Create and return the puzzle
        return Puzzle(
            W=self.w,
            H=self.h,
            walls=self.walls,
            pieces=tuple(self.canon_pieces),
            start=canon_state,
            goals=tuple(self.canon_goals)
        )

class PuzzleGenerator:

    """
    The Factory class for creating valid, scrambled Klotski puzzles.´
    """
    def __init__(self):
        # Catalog of common normalized pieces
        self.BLOCK_2x2 = Piece.normalized([(0,0), (0,1), (1,0), (1,1)])
        self.BLOCK_1x2_V = Piece.normalized([(0,0), (0,1)])
        self.BLOCK_1x1 = Piece.normalized([(0,0)])

    def _generate_random_positions(self, pieces: list[Piece], width: int, height: int, goal_idx: int, goal_pos: Coord) -> list[Coord]:
        """
        Generates random coordinates for all pieces, forcing the goal piece to its target.
        """
        posiciones = []
        for i, _ in enumerate(pieces):
            if i == goal_idx:
                posiciones.append(goal_pos)
            else:
                posiciones.append((random.randint(0, width - 1), random.randint(0, height - 1)))
        return posiciones

    def _create_solved_state(self, width: int, height: int, pieces: list[Piece], goal_idx: int, goal_pos: Coord) -> tuple[Puzzle, State]:
        """
        Attempts to place all pieces in the board without collisions to create a solved state.
        """

        intentos = 0
        while intentos < 10000:
            posiciones = self._generate_random_positions(pieces, width, height, goal_idx, goal_pos)
            
            try:
                canonicalizer = Canonicalizer(
                    w=width, h=height, walls=[], pieces=pieces, 
                    start_positions=posiciones, goals=[(goal_idx, goal_pos)])
                puzzle_temporal = canonicalizer.make_canonical()
                
                if lg.valid_placement(puzzle_temporal, puzzle_temporal.start):
                    return puzzle_temporal, puzzle_temporal.start
            except ValueError:
                pass # Pieces out of bounds or colliding on initialization
                
            intentos += 1
            
        raise Exception("Impossible to fit the requested pieces in this board size.")

    def _scramble(self, puzzle: Puzzle, solved_state: State, depth: int) -> State:
        """Walks backwards from the solved state taking random valid moves."""
        current_state = solved_state
        last_piece = -1

        for _ in range(depth):
            moves = lg.possible_moves(puzzle, current_state)
            if not moves: break # The board is completely stuck
            
            valid_moves = [m for m in moves if m[0] != last_piece]
            if not valid_moves: valid_moves = moves 

            chosen_move = random.choice(valid_moves)
            current_state = lg.apply_move(puzzle, current_state, chosen_move)
            last_piece = chosen_move[0]

        return current_state

    def generate_single(self, w: int, h: int, piezas_plantilla: list[Piece], meta_inicial_idx: int, posicion_meta: Coord, depth: int = 100) -> Puzzle:
        """Core workflow: Places pieces -> Scrambles them -> Formats back to Canonical."""
        # 1. Generate Solved State
        puzzle_resuelto, estado_resuelto = self._create_solved_state(w, h, piezas_plantilla, meta_inicial_idx, posicion_meta)
        
        # 2. Scramble
        estado_desordenado = self._scramble(puzzle_resuelto, estado_resuelto, depth)
        
        # 3. Canonicalize the final scattered state
        canonicalizer = Canonicalizer(
            w=w, h=h, walls=[], pieces=list(puzzle_resuelto.pieces),
            start_positions=list(estado_desordenado.positions),
            goals=list(puzzle_resuelto.goals)
        )
        return canonicalizer.make_canonical()
    




def generate_best_puzzle(amount: int) -> Optional[Puzzle]:
    generator = PuzzleGenerator()
    
    w, h = 4, 5
    # PLANTILLA CORREGIDA: 18 casillas ocupadas, 2 vacías
    plantilla = [
        generator.BLOCK_2x2,
        generator.BLOCK_1x2_V, generator.BLOCK_1x2_V, generator.BLOCK_1x2_V,
        generator.BLOCK_1x1, generator.BLOCK_1x1, generator.BLOCK_1x1, generator.BLOCK_1x1
    ]
    goal_idx = 0
    goal_pos = (1, 3)

    mejor_puzzle = None
    mejor_nota = -1.0

    print(f"Generando y evaluando {amount} puzzles candidatos...")

    for i in range(amount):
        try:
            candidate = generator.generate_single(w, h, plantilla, goal_idx, goal_pos, depth=150)
            
            json_str = candidate.to_json()
            builder = PuzzleGraphBuilder(candidate, json_str)
            graph = builder.build()
            
            # MAGIA: Le decimos al evaluador que NO guarde el archivo en disco
            nota = puzzle_evaluation(graph, f"cantidate_{i}", save_to_disk=False)
            
            print(f"Candidate {i}: Note {nota}")

            if nota > mejor_nota:
                mejor_nota = nota
                mejor_puzzle = candidate
                
        except Exception as e:
            # Si un puzzle no logra encajar las piezas (intentos < 10000), 
            # simplemente pasamos al siguiente sin que el programa crashee.
            print(f"Candidato {i} descartado durante la creación: {e}")
            
    print(f"\n¡Proceso terminado! El mejor puzzle sacó un {mejor_nota}.")
    return mejor_puzzle

def main():
    # Pedimos al programa que genere 20 tableros y se quede el más difícil
    puzzle_ganador = generate_best_puzzle(amount=20)
    
    # Lo guardamos en disco
    if puzzle_ganador:
        with open("graphs/generated_hardcore.json", mode="w", encoding="utf-8") as f:
            f.write(puzzle_ganador.to_json(indent=4))
        print("Guardado exitosamente en graphs/generated_hardcore.json")

if __name__ == "__main__":
    main()

