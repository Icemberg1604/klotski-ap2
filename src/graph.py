import graph_tool.all as gt
import sys
import logic as lg
from typing import TypeAlias, Any
from puzzle import Puzzle, State
from collections import deque
import json

Coord: TypeAlias = tuple[int, int]
StateKey: TypeAlias = tuple[Coord,...]


def equiv_shapes(puzzle: Puzzle) -> tuple[tuple[int,...],...]:
    
    goal_pieces: set[int] = {goal[0] for goal in puzzle.goals}
    dict_equiv_shapes: dict[StateKey, list[int]] = {}

    for index, piece in enumerate(puzzle.pieces):
        if index not in goal_pieces:
            shape = piece.coords
            if shape not in dict_equiv_shapes:
                dict_equiv_shapes[shape] =  []
            dict_equiv_shapes[shape].append(index)
        
    return tuple(tuple(indexes) for indexes in dict_equiv_shapes.values() if len(indexes) > 1)

def get_canonical_position(state_data: State, identical_pieces: tuple[tuple[int,...],...]) -> StateKey:
    pos_l = list(state_data.positions)
    for group in identical_pieces:
        new_coords = sorted([state_data.positions[piece_index] for piece_index in group ])
        for index, coord in zip(group, new_coords):
            pos_l[index] = coord

    return tuple(pos_l)

def state_key(puzzle: Puzzle, state: State | str) -> StateKey:
    """
    Adapting function for 3D_view.py. 
    Cleans the entry data and uses the calculations of get_canonical_position to return the StateKey.
    """
    identical_pieces = equiv_shapes(puzzle)

    if isinstance(state, str):
        parsed_positions = tuple(tuple(p) for p in json.loads(state))
        clean_state = State(parsed_positions)
        
    else:
        clean_state = state

    return get_canonical_position(clean_state, identical_pieces)


def create_empty_graph() -> gt.Graph:
    g = gt.Graph(directed=False)
    
    # v_properties
    v_is_start = g.new_vertex_property("bool")
    v_is_goal = g.new_vertex_property("bool")
    v_state = g.new_vertex_property("string")

    # e_property
    e_move = g.new_edge_property("string")
    
    # We save this properties in the graph, so we can access to them later
    g.vertex_properties["is_start"] = v_is_start
    g.vertex_properties["is_goal"] = v_is_goal
    g.vertex_properties["state"] = v_state
    g.edge_properties["move"] = e_move

    return g

def constructive_bfs(puzzle: Puzzle) -> gt.Graph:

    g = create_empty_graph() #creates a graph with ids for its state, and if it is a goal vertex or not.

    visited: dict[StateKey, Any] = {}  #type: ignore
    queue: deque[State] = deque()
    same_shape_pieces = equiv_shapes(puzzle=puzzle)

    start_canonical = get_canonical_position(puzzle.start, same_shape_pieces)
    v1 = g.add_vertex()
    visited[start_canonical] = v1
    queue.append(puzzle.start)

    g.vp["state"][v1] = puzzle.start.to_json()
    g.vp["is_start"][v1] = True
    g.vp["is_goal"][v1] = lg.is_goal(puzzle, puzzle.start)




    def evaluate(state: State, visited: dict[StateKey, Any], same_shape) -> Any:
        canonical_state = get_canonical_position(state, same_shape)
        if canonical_state not in visited:
            v = g.add_vertex()
            visited[canonical_state] = v

            g.vp["is_goal"][v] = lg.is_goal(puzzle, state)
            g.vp["state"][v] = state.to_json()
            
            queue.append(state)

        return visited[canonical_state]
    
    while queue:

        v_state = queue.popleft()
        possible_moves = lg.possible_moves(puzzle, v_state)
        v_curr_canonical = get_canonical_position(v_state, same_shape_pieces)
        v_curr_id = visited[v_curr_canonical]

        for move in possible_moves:
            u_state = lg.apply_move(puzzle, v_state, move)
            v_next_id = evaluate(u_state, visited, same_shape_pieces)

            if not g.edge(v_curr_id, v_next_id):
                e = g.add_edge(v_curr_id, v_next_id)
                p_idx, direction, _ = move
                g.ep["move"][e] = f"{p_idx},{direction}"

    return g 

def main() -> None:
    try:
        json_path = sys.argv[1]

    except IndexError:
        raise Exception("No se ha puesto la ruta del archivo JSON. Uso: python graph.py puzzles/nombre_puzzle.json")

    with open(json_path, 'r', encoding='utf-8') as file:
        json_text = file.read()
        
    puzzle = Puzzle.from_json(json_text)
    print(f"Building graph for {json_path}...")
    graph = constructive_bfs(puzzle) 
    
    graph.gp["puzzle"] = graph.new_graph_property("string")
    graph.gp["puzzle"] = json_text

    if json_path.endswith(".json"):
        out_path = json_path[:-5] + ".graphml"  # Le quitamos los últimos 5 caracteres (".json")

    else:
        out_path = json_path + ".graphml"       # Por si acaso le pasan un archivo sin extensión

    graph.save(out_path)
    print(f"Grafo guardado exitosamente en: {out_path}")

if __name__ == "__main__":
    main()