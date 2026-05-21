import json
import random
from typing import Optional
from dataclasses import dataclass
import graph_tool.all as gt

# Importaciones de tus otros módulos
from puzzle import Puzzle, State, Piece, Coord 
from eval import puzzle_evaluation 
from graph import PuzzleGraphBuilder 

# =====================================================================
# 1. CLASES DE CONFIGURACIÓN Y FORMATEO
# =====================================================================

@dataclass
class PuzzleConfig:
    """Define las reglas estructurales para generar un puzzle."""
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
    old_to_new_idx: dict[int, int]
    canon_goals: list[tuple[int, Coord]]
    
    def __init__(self, w: int, h: int, walls: list[Coord], pieces: list[Piece], start_positions: list[Coord], goals: list[tuple[int, Coord]]) -> None:
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
        paired = []
        for old_idx, (piece, pos) in enumerate(zip(self.pieces, self.start_positions)):
            paired.append((piece, pos, old_idx))
            
        paired.sort(key=lambda x: (x[0], x[1]))
        
        for new_idx, (piece, pos, old_idx) in enumerate(paired):
            self.canon_pieces.append(piece)
            self.canon_positions.append(pos)
            self.old_to_new_idx[old_idx] = new_idx

    def mapping_objectives(self) -> None:
        for old_idx, target_pos in self.goals:
            new_idx = self.old_to_new_idx[old_idx]
            self.canon_goals.append((new_idx, tuple(target_pos))) #type: ignore
        self.canon_goals.sort()

    def make_canonical(self) -> Puzzle:
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
# 2. LA FÁBRICA DE SEMILLAS (SOLVED STATES)
# =====================================================================

class PuzzleGenerator:
    """The Factory class for creating valid solved Klotski puzzles (Seeds)."""
    
    def __init__(self):
        self.BLOCK_2x2 = Piece.normalized([(0,0), (0,1), (1,0), (1,1)])
        self.BLOCK_1x2_V = Piece.normalized([(0,0), (0,1)])
        self.BLOCK_1x2_H = Piece.normalized([(0,0), (1,0)])
        self.BLOCK_1x1 = Piece.normalized([(0,0)])

    def _choose_fitting_piece(self, remaining_space: int) -> tuple[Piece, int]:
        opciones = [self.BLOCK_1x1]
        if remaining_space >= 2:
            opciones.extend([self.BLOCK_1x2_V, self.BLOCK_1x2_H])
            
        elegida = random.choice(opciones)
        area_elegida = 1 if elegida == self.BLOCK_1x1 else 2
        return elegida, area_elegida

    def generate_random_template(self, w: int, h: int) -> list[Piece]:
        target_area = (w * h) - 2
        template = [self.BLOCK_2x2]
        current_area = 4
        
        while current_area < target_area:
            remaining_space = target_area - current_area
            nueva_pieza, area_nueva = self._choose_fitting_piece(remaining_space)
            template.append(nueva_pieza)
            current_area += area_nueva
                
        return template

    def _can_piece_fit(self, tablero: list[list[bool]], piece: Piece, x: int, y: int, w: int, h: int) -> bool:
        for dx, dy in piece.coords:
            nx, ny = x + dx, y + dy
            if nx >= w or ny >= h or tablero[nx][ny]:
                return False
        return True

    def _mark_piece_on_board(self, tablero: list[list[bool]], piece: Piece, x: int, y: int) -> None:
        for dx, dy in piece.coords:
            tablero[x + dx][y + dy] = True

    def _find_spot_and_place(self, tablero: list[list[bool]], piece: Piece, w: int, h: int) -> Coord:
        for y in range(h):
            for x in range(w):
                if self._can_piece_fit(tablero, piece, x, y, w, h):
                    self._mark_piece_on_board(tablero, piece, x, y)
                    return (x, y)
        raise Exception("Error algorítmico: La pieza no cabe en el tablero.")
    
    def _create_solved_state_smart(self, config: PuzzleConfig) -> tuple[Puzzle, State]:
        tablero = [[False for _ in range(config.h)] for _ in range(config.w)]
        posiciones = [(-1, -1)] * len(config.pieces) 
        
        meta_piece = config.pieces[config.goal_idx]
        gx, gy = config.goal_pos
        self._mark_piece_on_board(tablero, meta_piece, gx, gy)
        posiciones[config.goal_idx] = (gx, gy)
        
        for idx, piece in enumerate(config.pieces):
            if idx == config.goal_idx:
                continue
            pos = self._find_spot_and_place(tablero, piece, config.w, config.h)
            posiciones[idx] = pos

        canonicalizer = Canonicalizer(
            w=config.w, h=config.h, walls=[], pieces=config.pieces, 
            start_positions=posiciones, goals=[(config.goal_idx, config.goal_pos)]
        )
        puzzle = canonicalizer.make_canonical()
        return puzzle, puzzle.start

    def generate_seed(self, config: PuzzleConfig) -> Puzzle:
        """Devuelve un puzzle en su estado resuelto (la semilla del grafo)."""
        puzzle_resuelto, _ = self._create_solved_state_smart(config)
        return puzzle_resuelto


# =====================================================================
# 3. EL ORQUESTADOR Y LA EXTRACCIÓN DEL GRAFO
# =====================================================================

def extract_hardest_puzzle_from_graph(seed_puzzle: Puzzle, graph: gt.Graph) -> Puzzle:
    """
    Encuentra el vértice más alejado del estado resuelto (nodo 0) 
    y reconstruye el Puzzle con ese nuevo estado inicial.
    """
    # 1. Encontrar las distancias desde el estado resuelto (vértice 0)
    nodo_resuelto = graph.vertex(0)
    distancias = gt.shortest_distance(graph, source=nodo_resuelto)
    
    # 2. Convertir a array de numpy y limpiar inalcanzables
    dist_array = distancias.a
    dist_array[dist_array == 2147483647] = -1 
    
    # 3. Obtener el índice del nodo más alejado
    furthest_node_idx = int(dist_array.argmax())
    distancia_max = dist_array[furthest_node_idx]
    
    print(f"   -> Nivel extraído con una profundidad de {distancia_max} movimientos perfectos.")
    
    # 4. Recuperar el estado crudo desde el grafo
    estado_crudo = json.loads(graph.vp["state"][graph.vertex(furthest_node_idx)])
    nuevas_posiciones = [tuple(coord) for coord in estado_crudo]

    # 5. Canonicalizar el nuevo puzzle "desordenado" para validarlo
    canonicalizer = Canonicalizer(
        w=seed_puzzle.W, 
        h=seed_puzzle.H, 
        walls=list(seed_puzzle.walls), 
        pieces=list(seed_puzzle.pieces), 
        start_positions=nuevas_posiciones, 
        goals=list(seed_puzzle.goals)
    )
    return canonicalizer.make_canonical()

def generate_good_puzzles(amount: int, threshold: float = 3.5) -> list[tuple[float, Puzzle]]:
    generador = PuzzleGenerator()
    w, h = 4, 5
    goal_idx = 0
    goal_pos = (1, 3)

    puzzles_aprobados = [] # Nuestra bóveda para la "cosecha buena"

    print(f"Generando y evaluando {amount} universos candidatos...")
    print(f"Umbral de aprobación: {threshold}\n")

    for i in range(amount):
        try:
            plantilla = generador.generate_random_template(w, h)
            config = PuzzleConfig(w=w, h=h, pieces=plantilla, goal_idx=goal_idx, goal_pos=goal_pos)
            
            # 1. Creamos la semilla resuelta
            seed = generador.generate_seed(config)
            
            # 2. Expandimos el universo completo
            builder = PuzzleGraphBuilder(seed, seed.to_json())
            graph = builder.build()
            
            # 3. Evaluamos la calidad topológica de ese universo
            nota = puzzle_evaluation(graph, f"candidate_graph_{i}", save_to_disk=False)
            print(f"Universo {i}: Nota {nota}")

            # 4. El filtro de calidad
            if nota >= threshold:
                print(f"   -> ¡Supera el umbral! Extrayendo nivel maestro...")
                hardcore_puzzle = extract_hardest_puzzle_from_graph(seed, graph)
                # Guardamos la tupla (nota, puzzle)
                puzzles_aprobados.append((nota, hardcore_puzzle))
                
        except Exception as e:
            print(f"Universo {i} descartado: {e}")
            
    # Ordenamos los ganadores de mejor a peor nota
    puzzles_aprobados.sort(key=lambda x: x[0], reverse=True)
    
    print(f"\n¡Proceso terminado! Se encontraron {len(puzzles_aprobados)} puzzles maestros.")
    return puzzles_aprobados

def main():
    import os
    
    # Asegurarnos de que la carpeta existe antes de guardar múltiples archivos
    os.makedirs("graphs", exist_ok=True)
    
    # Pedimos al programa 20 intentos, y guardamos los de nota >= 3.5
    puzzles_ganadores = generate_good_puzzles(amount=20, threshold=3.5)
    
    if not puzzles_ganadores:
        print("El generador fue muy estricto hoy. Ningún puzzle superó el umbral de 3.5.")
        return

    # Guardamos cada puzzle en disco con su nota en el nombre del archivo
    for i, (nota, puzzle) in enumerate(puzzles_ganadores, start=1):
        filename = f"graphs/hardcore_{i}_nota_{nota}.json"
        
        with open(filename, mode="w", encoding="utf-8") as f:
            f.write(puzzle.to_json(indent=4))
            
        print(f"Guardado exitosamente en {filename}")

if __name__ == "__main__":
    main()