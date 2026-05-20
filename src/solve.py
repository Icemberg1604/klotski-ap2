import graph_tool.all as gt
import sys
from pathlib import Path
from typing import TypeAlias
import json

SimpleMove: TypeAlias = tuple[int, str]


def solution_bfs(graph: gt.Graph) -> list[SimpleMove]:

    json_str = graph.gp["solution"]
    
    #from the json property, we load the solution path
    moves = json.loads(json_str)
    

    #if there was no solution
    if moves is None:
        return []
        
    #we get the tuple version of this
    return [(piece, direction) for piece, direction in moves]

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