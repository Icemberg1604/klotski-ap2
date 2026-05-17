# Explanations over why we have chosen the BFS algotithm

### The Graph Tool algorithms:

#### The basics

- DFS `gt.seach.dfs_search`: The DFS algorithm does not guarantee the shortest path, so this option is not optimal.

- BFS `gt.seach.bfs_search` : This algorithm lets us inject visitors from python. This visitors are a designed class that activates at each iteration and uses the conditions we state while exploring the graph in C++. However, the constant change between both languages slows our execution.

#### Shortest Path 

- Dijksra `shortest_distance`: Calculates the distance from a node tp the whole graph. The problem is that this functions does not have an early exit, meaning it will explore until all the `goal_nodes` are visited.

- `shortest_path`: This fuction returns the exact route from one node to another. However, it only recieves one goal vertex.

- `astar_search`: Searches by the heuristic-

### Explanation over a Python BFS as the chosen algorithm. 

A* might seem as the most powerful one among all of the others. However, the heuristica of Manhattan will try all the moves that are the closest to target before realizing that you need to do other paths that may get the piece a bit further away than it was before. This in sum of having to use a priotity queue which has a cost of $O(n)$ are the reasons we did not choose this one.

Against the others, is more based on the situation of being able to do an early return. 

