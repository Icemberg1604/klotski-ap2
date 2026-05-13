import graph_tool.all as gt
import sys
import logic as lg
from typing import TypeAlias
from puzzle import Puzzle, State
from pathlib import Path
from collections import deque
from typing import Any
import json

StateKey: TypeAlias = tuple[tuple[int, int],...]


def state_key(puzzle: Puzzle, state_data: State | str) -> StateKey:
    if isinstance(state_data, str):
        positions = json.loads(state_data)
        return tuple(tuple(p) for p in positions)
    else:
        return state_data.positions

def create_empty_graph() -> gt.Graph:
    g = gt.Graph(directed=False)
    
    # v_property
    v_is_start = g.new_vertex_property("bool")
    v_is_goal = g.new_vertex_property("bool")
    v_state = g.new_vertex_property("string")

    # e_property
    e_move = g.new_edge_property("string")
    
    # Guardamos las propiedades en el grafo
    g.vertex_properties["is_start"] = v_is_start
    g.vertex_properties["is_goal"] = v_is_goal
    g.vertex_properties["state"] = v_state
    g.edge_properties["move"] = e_move

    return g

def constructive_bfs(puzzle: Puzzle) -> gt.Graph:
    g = create_empty_graph()
    visited: dict[State, Any] = {}
    
    # CORRECCIÓN 1: Inicializamos la cola vacía correctamente
    queue: deque[State] = deque()

    def state_eval(state: State) -> int:
        if state not in visited:

            v = g.add_vertex()
            visited[state] = v

            g.vp["is_goal"][v] = lg.is_goal(puzzle, state)
            g.vp["is_goal"][v] = state.to_json()

            queue.append(state)

        return visited[state]

    v_start_id = state_eval(puzzle.start)
    g.vp["is_start"][g.vertex(v_start_id)] = True

    # BFS
    while queue:
        current_state = queue.popleft()
        v_curr = visited[current_state]

        for move in lg.possible_moves(puzzle, current_state):
            new_state = lg.apply_move(puzzle, current_state, move)
            v_next = state_eval(new_state)

            # Si la conexión no existe (para evitar aristas duplicadas al volver atrás)
            if not g.edge(v_curr, v_next):
                e = g.add_edge(v_curr, v_next)
                p_idx, direction, _ = move
                g.ep["move"][e] = f"{p_idx},{direction}" 

    return g

def main() -> None:
    if len(sys.argv) < 2:
        print("Use: python src/graph.py puzzles/nombre_puzzle.json")
        sys.exit(1)

    json_path = Path(sys.argv[1])
    puzzle = Puzzle.from_json(json_path.read_text())
    
    graph = constructive_bfs(puzzle) 
    
    out_path = json_path.with_suffix('.graphml')
    graph.save(str(out_path))
    
    print(f"Grafo terminado: {graph.num_vertices()} estados.")
    print(f"Guardado exitosamente en: {out_path}")

if __name__ == "__main__":
    main()
