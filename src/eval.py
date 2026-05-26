from pathlib import Path
import sys
import graph_tool.all as gt
import json
from solve import solution_bfs, SimpleMove
import math
import random
from graph import build_graf_from_json, save_graph

def get_solution(graph: gt.Graph, graph_name: str, save_to_disk: bool = True) -> list[SimpleMove]:
    """
    Gets the solution path from the graph. If the file is already created, it uses it. Else, it searches for the 
    solution of the graph. If save_to_disk is True, it saves this solution on a json-solutions directory.
    """
    sol_dir = Path("json-solutions")
    sol_path = sol_dir / f"{graph_name}.sol.json"

    if sol_path.is_file():
        with open(file=sol_path, mode='r', encoding='utf-8') as file:
            return json.load(file)
        
    else:
        movements = solution_bfs(graph)
        
        # Save the solution in a json file
        if save_to_disk:
            sol_dir.mkdir(parents=True, exist_ok=True)
            with open(sol_path, mode="w", encoding="utf-8") as f:
                json.dump(movements, f, indent=4)

        return movements
    
def evaluate_shortest_distance(graph: gt.Graph, graph_name: str, save_to_disk: bool) -> int:
    """
    Returns the length of the solution.
    """
    return len(get_solution(graph, graph_name, save_to_disk))

def evaluate_topology(graph: gt.Graph) -> tuple[float, float]:
    """
    Evaluates the proportion of traps (dead ends) and the mean ramification factor. 
    Uses arrays to speed up the process.
    """
    total_vertices = graph.num_vertices()
    if total_vertices == 0:
        return 0.0, 0.0
    
    out_degrees = graph.degree_property_map("out").a
    
    # Check the amount of dead ends
    dead_ends = (out_degrees == 1).sum()
    proportion_dead_ends = float(dead_ends / total_vertices)
    
    # Check the levels of ramifications
    nodes_with_options = out_degrees[out_degrees > 1]
    
    if len(nodes_with_options) > 0:
        mean_branch = nodes_with_options.mean() 
        # Divide by 5.0 to give a standard
        branch_score = min(1.0, float(mean_branch / 5.0))

    else:
        branch_score = 0.0
        
    return proportion_dead_ends, branch_score

def evaluate_centrality(graph: gt.Graph, iterations: int = 5) -> float:
    """
    Calculates the bottle-necks of the graph using a fast pivot approximation.
    Returns the normalized value (0.0 to 1.0).
    """
    total_vertices = graph.num_vertices()
    if total_vertices < 3:
        return 0.0
    
    # The theoretical maximum of possible paths
    max_possible_paths  = (total_vertices - 1) * (total_vertices - 2) // 2
    
    # For tiny graphs
    if total_vertices <= 100:
        # norm=False assures us that the values are raw counts, not percentages or something else
        vertex_betweenness, _ = gt.betweenness(graph, norm=False)
        maximum_peak = float(vertex_betweenness.a.max())
        return min(1.0, maximum_peak / max_possible_paths )

    # Case for bigger graphs
    num_pivots = 100
    sum_maximums = 0.0
    
    for _ in range(iterations):
        pivots = random.sample(range(total_vertices), num_pivots)
        # norm=False lets us normalize the parameter ourselves
        vertex_betweenness, _ = gt.betweenness(graph, pivots=pivots, norm=False)
        sum_maximums += vertex_betweenness.a.max()
        
    average_centrality = sum_maximums / iterations
    
    # Normalization
    normalized_score = average_centrality / max_possible_paths 
    
    return float(min(1.0, normalized_score))


def puzzle_evaluation(graph: gt.Graph, graph_name: str, save_to_disk: bool = True) -> float:

    num_vertices = graph.num_vertices()
    if num_vertices < 2: 
        return 0.0

    # Getting the raw values
    total_distance = evaluate_shortest_distance(graph, graph_name, save_to_disk)
    dead_ends, branching_score = evaluate_topology(graph)
    bottleneck = evaluate_centrality(graph) 

    # Normalization
    
    path_score = min(1.0, total_distance / (math.log(num_vertices) * 2)) 
    # Divide by log for reducing the importance on small differences of sizes between graphs

    dif_path_weight = 2.0
    dead_ends_weight = 0.5
    branching_weight = 1.0
    bottleneck_weight = 1.5

    interest_score = (
        (path_score * dif_path_weight) +
        (dead_ends * dead_ends_weight) +
        (branching_score * branching_weight) +
        (bottleneck * bottleneck_weight)
    )

    # Strong penalty for puzzles with very few movements (< 25)
    # Example: If solved in 2 movements, the score is multiplied by (2/25)^2 = 0.006
    # If solved in 24 movements, the score is multiplied by (24/25)^2 = 0.92
    if total_distance < 25:
        penalty_factor = (max(total_distance, 1) / 25.0) ** 2
        interest_score *= penalty_factor

    return round(interest_score, 2)


def extract_graph(puzzle_path: Path) -> gt.Graph:
    """
    Tries to load the graph from the graphs file. If it is not found, 
    it will create the graph, save it, and return it.
    """
    graph_path = Path("graphs") / f"{puzzle_path.stem}.graphml"
    
    if graph_path.is_file():
        print(f"-> Loading graph from {graph_path}...")
        return gt.load_graph(str(graph_path), fmt="graphml")
    
    print(f"-> Graph not found, creating one for {puzzle_path.name}...")
    
    with open(puzzle_path, mode='r', encoding='utf-8') as f:
        json_str = f.read()
        json_data = json.loads(json_str)
        
    graph = build_graf_from_json(json_data)
    
    save_graph(graph, str(puzzle_path))
    
    return graph
    

def main() -> None:

    try:
        puzzle_path_str = sys.argv[1]

    except IndexError:
        raise Exception("Usage: python ./src/eval.py ./puzzles/<puzzle>.json")


    puzzle_path = Path(puzzle_path_str)
    puzzle_name = str(puzzle_path.stem)
    graph = extract_graph(puzzle_path)
    score = puzzle_evaluation(graph, puzzle_name)
    
    print(f"The score of {puzzle_name} is: {score}")

if __name__ == '__main__':
    main()