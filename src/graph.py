import graph_tool.all as gt
import sys
import logic as lg
from typing import TypeAlias, Any
from puzzle import Puzzle, State
from collections import deque
import json
from pathlib import Path

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


def create_empty_graph(json_str: str) -> gt.Graph:

    """
    Creates the graph with the folowing properties
    Vertex properties: is_start for indicating which node is the starting state; is_goal for showing that the node is one of the 
    posible solutions. "state" saves the data as a json str that posseses the state of the graph at that vertex.
    """
    g = gt.Graph(directed=False)
    
    # v_properties
    v_is_start = g.new_vertex_property("bool")
    v_is_goal = g.new_vertex_property("bool")
    v_state = g.new_vertex_property("string")

    # e_property
    e_piece = g.new_edge_property("int")
    e_move_dir = g.new_edge_property("string")

    #g_property
    g_puzzle = g.new_graph_property("string")
    
    # We save this properties in the graph, so we can access to them later
    g.vertex_properties["is_start"] = v_is_start
    g.vertex_properties["is_goal"] = v_is_goal
    g.vertex_properties["state"] = v_state

    g.edge_properties["piece"] = e_piece
    g.edge_properties["direction"] = e_move_dir
    
    g.graph_properties["puzzle"] = g_puzzle

    g.graph_properties["puzzle"] = json_str
 
    return g

def constructive_bfs(puzzle: Puzzle, general_json: str) -> gt.Graph:

    states_graph = create_empty_graph(general_json) #creates a graph with ids for its state, and if it is a goal vertex or not.

    visited: dict[StateKey, Any] = {}  #type: ignore
    queue: deque[State] = deque()
    same_shape_pieces = equiv_shapes(puzzle=puzzle)

    def evaluate(state: State) -> Any:
        canonical_state = get_canonical_position(state, same_shape_pieces)
        if canonical_state not in visited:
            v = states_graph.add_vertex()
            visited[canonical_state] = v

            states_graph.vp["is_goal"][v] = lg.is_goal(puzzle, state)
            states_graph.vp["state"][v] = state.to_json()
            
            queue.append(state)

        return visited[canonical_state]
    
    v_start = evaluate(puzzle.start)
    states_graph.vp["is_start"][v_start] = True
   
    while queue:

        print(f"Remaining on queue: {len(queue)}")
        print(f"Nodes on graph: {states_graph.num_vertices()}")
        v_state = queue.popleft()
        possible_moves = lg.possible_moves(puzzle, v_state)
        v_curr_canonical = get_canonical_position(v_state, same_shape_pieces)
        v_curr_id = visited[v_curr_canonical]

        for move in possible_moves:
            u_state = lg.apply_move(puzzle, v_state, move)
            v_next_id = evaluate(u_state)

            if not states_graph.edge(v_curr_id, v_next_id):
                edge = states_graph.add_edge(v_curr_id, v_next_id)

                p_idx, direction, _ = move
                states_graph.ep["piece"][edge] = p_idx
                states_graph.ep["direction"][edge] = direction

    return states_graph 

def main() -> None:

    try:
        json_path = sys.argv[1]
        
    except IndexError:
        raise Exception("No valid json path. Use: python src/graph.py puzzles/name_puzzle.json")

    with open(json_path, 'r', encoding='utf-8') as file:
        json_data = json.load(file)

    #Cleaning Json data
    if "puzzle" in json_data:
        json_data = json_data["puzzle"]
    clean_json =  json.dumps(json_data)

    puzzle = Puzzle.from_json(clean_json)
    print(f"Building graph from {json_path}...")
    graph = constructive_bfs(puzzle, clean_json) 

    input_path = Path(json_path) 

    # Define and create the output directory
    output_dir = Path("graphs")
    output_dir.mkdir(exist_ok=True)

    # .stem automatically removes the '.json' extension for you!
    out_path = output_dir / f"{input_path.stem}.graphml"    

    graph.save(str(out_path))
    print(f"Graph was succesfully saved in: {out_path}")

if __name__ == "__main__":
    main()