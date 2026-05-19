from pathlib import Path
import sys
import graph_tool.all as gt
import json
from solve import solution_bfs, SimpleMove
import math
import random

def get_solution(graph: gt.Graph, graph_name: str) -> list[SimpleMove]:
    """
    Busca la solución en la carpeta json-solutions. Si se encuentra, se importa. Si no se encuentra, se crea.
    """
    sol_dir = Path("json-solutions")
    sol_path = sol_dir / f"{graph_name}.sol.json"

    if sol_path.is_file():
        with open(file=sol_path, mode='r', encoding='utf-8') as file:
            return json.load(file)
        
    else:
        movememts = solution_bfs(graph)
        sol_dir.mkdir(parents=True, exist_ok=True)

        with open(sol_path, mode="w", encoding="utf-8") as f:
            json.dump(movememts, f, indent=4)
        
        return movememts
    
def evaluate_shortest_distance(graph: gt.Graph, graph_name: str) -> int:
    """
    Returns the lenght of the solution
    """
    shortest_solution = get_solution(graph, graph_name)
    return len(shortest_solution)

def evaluate_topology(graph: gt.Graph) -> tuple[float, float]:
    """
    Evaluates the proportion of traps (dead ends) and the mean ramification factor (). 
    Uses arrays to speed up the process
    """
    total_vertices = graph.num_vertices()
    if total_vertices == 0:
        return 0.0, 0.0
    
    out_degrees = graph.degree_property_map("out").a
    
    #check the amount of dead_ends
    dead_ends = (out_degrees == 1).sum()
    proportion_dead_ends = float(dead_ends / total_vertices)
    
    #check the levels of ramifications
    nodes_with_options = out_degrees[out_degrees > 1]
    
    if len(nodes_with_options) > 0:
        mean_branch = nodes_with_options.mean() 
        #devide by 5.0 to give a standard
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
    
    #The theoretical maximum of posible paths
    max_posible_paths  = (total_vertices - 1) * (total_vertices - 2) // 2
    
    #for tiny graphs
    if total_vertices <= 100:
        # norm=False nos asegura que devuelve el recuento crudo, no porcentajes extraños
        vertex_betweenness, _ = gt.betweenness(graph, norm=False)
        maxim_peak = float(vertex_betweenness.a.max())
        return min(1.0, maxim_peak / max_posible_paths )

    #case for bigger graphs
    num_pivots = 100
    suma_maximos = 0.0
    
    for _ in range(iterations):
        pivots = random.sample(range(total_vertices), num_pivots)
        # norm=False lets to normalize ourselves the parameter
        vertex_betweenness, _ = gt.betweenness(graph, pivots=pivots, norm=False)
        suma_maximos += vertex_betweenness.a.max()
        
    promedio_centralidad = suma_maximos / iterations
    
    #normalization
    score_normalizado = promedio_centralidad / max_posible_paths 
    
    return float(min(1.0, score_normalizado))

def proportion_goals(graph: gt.Graph) -> float:
    """
    Gets the proportion of the amount of goals in comparison of the amount of vertices
    """
    total_vertices = graph.num_vertices()

    if total_vertices == 0:
        return 0.0
    
    total_goals = graph.vp["is_goal"].a.sum()
   
    return float(total_goals/total_vertices)



def puzzle_evaluation(graph: gt.Graph, graph_name: str) -> float:

    num_vertices = graph.num_vertices()
    if num_vertices < 2: 
        return 0.0

    # Getting the raw values
    total_distance = evaluate_shortest_distance(graph, graph_name)
    dead_ends, branching_score = evaluate_topology(graph)
    bottleneck = evaluate_centrality(graph) 
    proportion_of_goal = proportion_goals(graph)

    #normalization
    
    path_score = min(1.0, total_distance / (math.log(num_vertices) * 2)) 
    #divide by log for reducing the importance on small differences of sizes bewteen graphs
    
    amount_of_goals_indicator = 1.0 - proportion_of_goal


    path_weight = 2.0
    laberinth_weight = 0.5
    branching_weight = 1.0
    centralization_weight = 1.0
    presition_weight = 0.5

    interest_score = (
        (path_score * path_weight) +
        (dead_ends * laberinth_weight) +
        (branching_score * branching_weight) +
        (bottleneck * centralization_weight) +
        (amount_of_goals_indicator * presition_weight)
    )

    return round(interest_score, 2)


def main() -> None:
    try:
        graph_path_str = sys.argv[1]
    except IndexError:
        raise Exception("Use: python ./src/eval.py ./graphs/<puzzle_graph>.graphml")
    
    graph_path = Path(graph_path_str)

    if not graph_path.is_file():
        raise FileNotFoundError(f"Error: No se encontró el archivo {graph_path}")
    
    graph_name = str(graph_path.stem)
    puzzle_graph = gt.load_graph(graph_path_str, fmt="graphml")
    score = puzzle_evaluation(puzzle_graph, graph_name)
    print(f"The score of {graph_name} is: {score}")

if __name__ == '__main__':
    main()