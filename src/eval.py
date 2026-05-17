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

def evaluate_paths(graph: gt.Graph) -> float:
    """
    Calculates the value of "dead ends"
    """
    total_vertices = graph.num_vertices()
    if total_vertices == 0:
        return 0.0
    
    out_degrees = graph.get_out_degrees(graph.get_vertices())

    dead_ends = sum(out_degrees == 1)

    return dead_ends /total_vertices

def evaluate_centrality(graph: gt.Graph, iterations: int = 5) -> float:
    """
    Calculates the bottle-necks of the graph using a fast pivot approximation.
    Returns the value with the biggest centrality. Centrality basically measures the overall flux of 
    one vertex to every other one, meaning that there is a particular state you need to achieve to access every other state
    """
    total_vertices = graph.num_vertices()
    if total_vertices < 3:
        return 0.0
    
    # 1. CASO GRAFOS PEQUEÑOS: Cálculo exacto de un solo impacto
    if total_vertices <= 100:
        vertex_betweenness, _ = gt.betweenness(graph)
        return float(max(vertex_betweenness.a))

    # 2. CASO GRAFOS GRANDES: Aproximación por Montecarlo
    num_pivots = 100
    suma_maximos = 0.0
    
    for _ in range(iterations):
        pivots = random.sample(range(total_vertices), num_pivots)
        vertex_betweenness, _ = gt.betweenness(graph, pivots=pivots)
        suma_maximos += max(vertex_betweenness.a)
        
    promedio_centralidad = suma_maximos / iterations
    
    return float(promedio_centralidad)

def proportion_goals(graph: gt.Graph) -> float:
    """
    Gets the proportion of the amount of goals in comparison of the amount of vertices
    """
    total_vertices = graph.num_vertices()

    if total_vertices == 0:
        return 0.0
    
    total_goals = sum(graph.vp["is_goal"].a)
   
    return float(total_goals/total_vertices)



def puzzle_evaluation(graph: gt.Graph, graph_name: str) -> float:

    num_vertices = graph.num_vertices()
    if num_vertices < 2: 
        return 0.0

    # Getting the raw values
    total_distance = evaluate_shortest_distance(graph, graph_name)
    dead_ends = evaluate_paths(graph)
    bottleneck = evaluate_centrality(graph) 
    proportion_of_goal = proportion_goals(graph)

    #normalization
    
    path_score = min(1.0, total_distance / (math.log(num_vertices) * 2)) 
    
    score_metas_escasas = 1.0 - proportion_of_goal


    path_weight = 1.5
    laberinth_weight = 1.0
    centralization_weight = 2.0
    presition_weight = 0.5

    # Final step
    interest_score = (
        (path_score * path_weight) +
        (dead_ends * laberinth_weight) +
        (bottleneck * centralization_weight) +
        (score_metas_escasas * presition_weight)
    )

    # Redondeamos a 2 decimales para que se vea limpio (ej: 4.25)
    return round(interest_score, 2)


def main() -> None:
    try:
        graph_path_str = sys.argv[1]
    except:
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