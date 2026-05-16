import graph_tool.all as gt
import sys
from pathlib import Path
from puzzle import Puzzle, State
import logic as lg
from collections import deque
from typing import TypeAlias
import json

SimpleMove: TypeAlias = tuple[int, str]


def solution_bfs(graph: gt.Graph) -> list[SimpleMove]:
    start_vertex = gt.find_vertex(graph, graph.vp["is_start"], True)[0]
    goal_nodes = gt.find_vertex(graph,  graph.vp["is_goal"], True)

    if not goal_nodes:
        raise Exception("Goal vertices not found")
    
    
    if graph.vp["is_goal"][start_vertex]:
        return []
    
    node_queue = deque([(start_vertex, [])])
    visited = {start_vertex}
    
    while node_queue:
        current_v, current_path = node_queue.popleft()
        for edge in current_v.out_edges():
            _, destiny_node = edge
        
            if destiny_node not in visited:
                if graph.vp["is_goal"][destiny_node]:
                    final_path_edges = current_path + [edge]
                    return [(graph.ep["piece"][e], graph.ep["direction"][e]) for e in final_path_edges]
                visited.add(destiny_node)
                node_queue.append((destiny_node, current_path + [edge]))
    
    raise Exception("There is no path to the goal in this graph")

def main() -> None:
    
    if len(sys.argv) < 2:
        raise Exception("Not valid argument. Use: python ./src/solve ./graphs/<puzzle_graph>.graphml")
    
    graph_path = sys.argv[1]
    graph = gt.load_graph(file_name=graph_path, fmt="graphml")
    graph_path = Path(graph_path)
    movement_solution = solution_bfs(graph)

    name_dir = "json-solutions"
    sol_dir = Path(name_dir)
    sol_dir.mkdir(parents = True, exist_ok = True)
    sol_path = sol_dir / f"{graph_path.stem}.sol.json"

    with open(sol_path, 'w', encoding='utf-8') as f:
        json.dump(movement_solution, f, indent=4)
        
    print(f"Archivo de solución guardado en: {sol_path}")



    

if __name__ == '__main__':
    main()