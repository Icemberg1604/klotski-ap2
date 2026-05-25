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
    g_solution  = g.new_graph_property("string")
    
    # We save this properties in the graph, so we can access to them later
    g.vertex_properties["is_start"] = v_is_start
    g.vertex_properties["is_goal"] = v_is_goal
    g.vertex_properties["state"] = v_state

    g.edge_properties["piece"] = e_piece
    g.edge_properties["direction"] = e_move_dir
    
    g.graph_properties["puzzle"] = g_puzzle
    g.graph_properties["solution"] = g_solution
    
    g.graph_properties["puzzle"] = json_str
 
    return g


class PuzzleGraphBuilder:
    """
    Class made for building the whole graph and finding a 
    """
    puzzle: Puzzle
    graph: gt.Graph
    
    visited: dict[StateKey, Any] #Saves the value[vertex] of the key[state]
    came_from: dict[Any, Any] #saves the vertex[key] that leaded to the vertex[value]
    queue: deque[State] #queue for saving the next states of the puzzle to be processed

    v_start: int | None
    solution_found: bool

    def __init__(self, puzzle: Puzzle, general_json: str) -> None:

        self.puzzle = puzzle
        self.graph = create_empty_graph(general_json)
        self.same_shape_pieces = equiv_shapes(puzzle)

        self.visited = {}
        self.came_from = {}
        self.queue = deque()

        self.v_start = None
        self.solution_found = False

    def _register_state(self, state: State) -> tuple[int, bool]:
        """
        If a vertex has not been visited, saves the information of it in the graph
        """
        canonical_state = get_canonical_position(state, self.same_shape_pieces)
        is_new = canonical_state not in self.visited
        
        if is_new:
            v = self.graph.add_vertex()
            self.visited[canonical_state] = v
            self.graph.vp["is_goal"][v] = lg.is_goal(self.puzzle, state)
            self.graph.vp["state"][v] = state.to_json()
            self.queue.append(state)

        return self.visited[canonical_state], is_new
        
    def _reconstruct_solution(self, end_node) -> None:
        """
        Once we found the solution, recreates all the path from the 
        """
        self.solution_found = True
        path = []
        curr_node = end_node
        
        while curr_node != self.v_start:
            parent_node, piece, dir_str = self.came_from[curr_node]
            path.append([piece, dir_str])
            curr_node = parent_node
        
        path.reverse()
        self.graph.graph_properties["solution"] = json.dumps(path)


    def build(self) -> gt.Graph:
        """
        Main loop of the BFS. It creates the puzzle's graph by expanding it and saves the solution in gp["solution]
        """
        

        self.v_start, _ = self._register_state(self.puzzle.start)
        self.graph.vp["is_start"][self.v_start] = True
        
        if self.graph.vp["is_goal"][self.v_start]:
            self.graph.graph_properties["solution"] = json.dumps([])
            self.solution_found = True

        num_vertices = self.graph.num_vertices()
        remaining_vertices = len(self.queue)

        old_num_vertices = num_vertices
        old_remaining_vertices = remaining_vertices


        while self.queue and num_vertices < 700000:

            if old_remaining_vertices + 10000 < remaining_vertices or old_num_vertices + 10000 < num_vertices:
                print(remaining_vertices)
                print(num_vertices)

                old_num_vertices = num_vertices
                old_remaining_vertices = remaining_vertices
            

            v_state = self.queue.popleft()
            possible_moves = lg.possible_moves(self.puzzle, v_state)
            v_curr_canonical = get_canonical_position(v_state, self.same_shape_pieces)
            v_curr_id = self.visited[v_curr_canonical]

            #We handle the scenarios for every possible move from our starting v_state
            for move in possible_moves:
                u_state = lg.apply_move(self.puzzle, v_state, move)
                piece_idx, direction, _ = move
                v_next_id, is_new = self._register_state(u_state)

                if not self.solution_found and is_new:
                    #we save the route we came from
                    self.came_from[v_next_id] = (v_curr_id, piece_idx, direction)
 
                    if self.graph.vp["is_goal"][v_next_id]: 
                        self._reconstruct_solution(v_next_id)
                        self.came_from.clear()

                #we create the conections between nodes
                if not self.graph.edge(v_curr_id, v_next_id):
                    edge = self.graph.add_edge(v_curr_id, v_next_id)
                    self.graph.ep["piece"][edge] = piece_idx
                    self.graph.ep["direction"][edge] = direction

            #check how it is going
            num_vertices = self.graph.num_vertices()
            remaining_vertices = len(self.queue)
            
        if not self.solution_found:
            self.graph.graph_properties["solution"] = json.dumps(None)

        return self.graph
    
def build_graf_from_json(json_data)-> gt.Graph:

    if "puzzle" in json_data:
        json_data = json_data["puzzle"]

    clean_json =  json.dumps(json_data)
    puzzle = Puzzle.from_json(clean_json)
    print(f"Building graph...")

    builder =  PuzzleGraphBuilder(puzzle, clean_json)
    

    return builder.build()


def save_graph(graph: gt.Graph, json_path: str) -> None:
    """
    Saves the graph in the directory ./graphs while recieving the json_path as a str
    """
        # Define and create the output directory
    input_path = Path(json_path) 
    output_dir = Path("graphs")
    output_dir.mkdir(exist_ok=True)

    # .stem automatically removes the '.json' extension for you!
    out_path = output_dir / f"{input_path.stem}.graphml"    

    graph.save(str(out_path))
    print(f"Graph was succesfully saved in: {out_path}")
    

def main() -> None:
    """
    Saves the graph that corresponds to the puzzle
    """

    try:
        json_path = sys.argv[1]

    except IndexError:
        raise Exception("No valid json path. Use: python src/graph.py puzzles/<name_puzzle>.json")

    with open(json_path, 'r', encoding='utf-8') as file:
        json_data = json.load(file)

    graph = build_graf_from_json(json_data)
    save_graph(graph, json_path)
    
    

if __name__ == "__main__":
    main()