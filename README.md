# Klotski Puzzle Solver & Evaluation Pipeline

An automated data engineering pipeline designed to generate, solve, evaluate, and rate canonical Klotski sliding-block puzzles. The system features a custom graph-theoretic evaluation engine using `graph_tool`, lazy-loaded state space caching, and an automated multi-tenant API synchronization client. 

**What this README is:** 

A concise developer guide for the code we implemented, how to run it locally, what each script does, and how to contribute or reproduce results.

## Requirements and Execution

### Prerequisites
- Pixi installed (`curl -fsSL https://pixi.sh/install.sh | sh`) and project dependencies installed with `pixi install`.
- A POSIX-like environment (Linux, WSL, macOS). `graph-tool` requires Linux/WSL for native support.

### Activate Environment

Run either:

```bash
pixi shell
# then, inside the shell
python src/<script>.py [args]
```

Or run one-off commands:

```bash
pixi run python src/<script>.py [args]
```

### Primary Scripts
- **Download catalog & puzzles:** [src/download.py](src/download.py) — fetch top puzzles and individual puzzle JSONs from the server.
- **Build graph:** [src/graph.py](src/graph.py) — construct the state-space graph for a puzzle and save it as a `.graphml` in the `graphs/` folder.
- **Solve puzzles:** [src/solve.py](src/solve.py) — find a sequence of piece moves from `start` to `goals` using graph search; outputs `.sol.json` move sequences.
- **Evaluate / score:** [src/eval.py](src/eval.py) — compute heuristic metrics from the graph and return a score in the [0.0, 5.0] range.
- **Rate / upload:** [src/rate.py](src/rate.py), [src/upload.py](src/upload.py) — send votes or new puzzles to the remote repository (requires `KLOTSKI_TOKEN` in your environment).
- **Batch rating:** [src/rate_all.py](src/rate_all.py) — optionally re-rate the catalog with your scoring function.
- **Generate puzzles:** [src/generate.py](src/generate.py) — randomized puzzle generator with post-filtering via `eval.py`.
- **Utilities & viewers:** [src/image.py](src/image.py), [src/movie.py](src/movie.py), [src/3D_view.py](src/3D_view.py), [src/play.py](src/play.py).

### Common Commands

Fetch top list and download a puzzle:

```bash
pixi run python src/download.py get
pixi run python src/download.py download 4b7569816b92...
```

Build graph and evaluate:

```bash
pixi run python src/graph.py puzzles/your_puzzle.json
pixi run python src/eval.py puzzles/your_puzzle.json
```

Solve and visualise solution as a gif:

```bash
pixi run python src/solve.py puzzles/your_puzzle.json
pixi run python src/movie.py puzzles/your_puzzle.json solution.sol.json
```

Upload or rate (requires tokens in environment):

```bash
pixi run python src/rate.py 4b7569816b9252a4...
pixi run python src/upload.py puzzles/new_puzzle.json
```

Note: Leaving the `<puzzle_id>` parameter blank when executing `rate.py` triggers a smart fallback that automatically fetches, processes, and rates the #1 Top-Rated puzzle on the server leaderboard.

## Architecture & Pipeline Topography

### Design Notes & Key Decisions
- **Graph cap**: to keep graph construction tractable we cap exploration (empirically) to ~700k vertices; graphs exceeding the cap are handled carefully to avoid memory blowups.
- **Canonicalization**: puzzles are canonicalized (piece order, coordinates, walls) so generated puzzles are comparable and deduplicated before upload.
- **Evaluation heuristics**: our score combines path length, branching, dead-end ratio and centrality/bottleneck measures. See `src/eval.py` for exact formula and normalization.

### Pipeline Overview

The system is split into two distinct layers: an In-Memory Graph State Space Generator and a Multi-Tenant API Sync Client.
```bash
[ Server API ]  (Global Puzzle Repository)
         │  ▲
  Get/DL │  │ POST Uploads / Votes
         ▼  │
  ┌──────────────┐          Smart Cache Check
  │ download.py  │ ─────────────────────────────────┐
  └──────────────┘                                  │
         │                                          ▼
         ▼                                  ┌──────────────┐
  ┌──────────────┐   Builds State Space     │   eval.py    │
  │ generate.py │ ───────────────────────> │(Lazy Loader) │
  └──────────────┘                          └──────────────┘
                                                    │
         ┌──────────────────────────────────────────┤
         ▼                                          ▼
  ┌──────────────┐                          ┌──────────────┐
  │   graph.py   │                          │   rate.py /  │
  │ (BFS Engine) │                          │  rate_all.py │
  └──────────────┘                          └──────────────┘
         │                                          │
         ▼                                          ▼
  [ graphs/*.graphml ]                      [ .env Matrix ] 
```

### Data Pipeline Modules

- **`download.py`**: Interacts with the remote server endpoints to stream either individual puzzle definitions or the global master catalog ledger.
- **`graph.py`**: The core graph constructor. Implements a canonical state hashing system to identify identical piece shapes, builds legal game state spaces via an optimized Breadth-First Search (BFS), and reconstructs shortest-path solutions.
- **`eval.py`**: The puzzle scoring engine. Acts as a **Smart Cache / Lazy Loader**. It checks your disk for an existing `.graphml` matrix; if missing, it prompts `graph.py` to build it on the fly and saves it for zero-overhead re-runs.
- **`rate.py` / `rate_all.py`**: The execution clients. They consume graph metrics, compress floating-point difficulty heuristics into API-compliant integer bounds, and broadcast the payload sequentially across multiple accounts.
- **`upload.py`**: Reads local canonical JSON maps and handles network handshakes to deploy unique puzzles onto the production repository.
- **`generate.py`**: The adversarial puzzle generator. Creates a random valid *solved* seed board and executes a reverse graph-theoretic BFS dummy-vertex execution loop to harvest the absolute hardest possible starting position. After that, it creates the new graph in this position and evaluates using the **`eval.py`** to filter the ones that are simpler and saving the puzzles with harder difficulty and with the highest number of steps needed to achieve the goal.

## Heuristic Evaluation Matrix

The evaluation script scores puzzles dynamically from 0.0 to 5.0 based on topological complexity rather than mere board size, weighting four key graph-theory vectors:

| **Heuristic Metric** | **Algorithmic Evaluation Method** | **Structural Importance** |
| --- | --- | --- |
| **Path Score** | Shortest-path BFS depth normalized against log-transformed vertex scales. | Prevents huge, simple-to-solve graphs from skewing difficulty scores. |
| **Dead-Ends Ratio** | Array summation matching out-degrees exactly equal to 1. | Measures the frequency of mathematical "traps" designed to stall solvers. |
| **Branching Factor** | Mean ramification density of nodes with multiple options. | Evaluates choices; higher choices increase the decision tree breadth. |
| **Centrality Peaks** | Fast Pivot Approximation sampling vertex betweenness over specified iterations. | Identifies bottleneck states through which a user is forced to navigate. |

## Multitenant Architecture & API Sync Client

The rating system supports parallel bulk synchronization for collaborative engineering teams. By configuring a credential matrix within your local, un-tracked .env file, the pipeline automatically detects active tokens and replicates metrics across all accounts sequentially:

### .env configuration 

```bash
# .env Configuration Framework
KLOTSKI_TOKEN1=personal_bearer_token_here
KLOTSKI_TOKEN2=second_bearer_token_here
```

When rating payloads are executed, the system wraps transactions securely, hiding internal authentication credentials while echoing the round-trip database updates back to your console:

```bash
System initialized with 2 active credential(s).
Target Locked: 4b7569816b9252a4e...
Calculating heuristic score...
 Sending rating of 4 stars for puzzle '4b7569...' [Token 1: ...7f9452]...
  Success! Rating accepted for Token 1.
 Sending rating of 4 stars for puzzle '4b7569...' [Token 2: ...e0889c]...
  Success! Rating accepted for Token 2.
```
## Details Over the Functionality of the Project

The project has successfully accomplished the given tasks. The different programs are able to perform the purposes they were build for, and give results that fits the project’s original scope. However, there are some technical details and design desicions that should be considered when reviewing the code.

### 1. The `graph.py`  limit of vertices.

One of the biggest challenges during the graph creation process was the size some puzzles could achieve. The decision taken was to continue the graph building process up until it reached the margin of 700 000 vertices. Larger graphs are problematic not only because you need to explore the nodes, but mainly since it is also needed to process the nodes and save them.  Through different experiments, this 700,000 cap proved to be the sweet spot, allowing us to evaluate puzzles faster while still accurately approximating their difficulty rate.

### 2. The `generate.py`  functionality

This script has mainly 4 parts:

- **The Definition of the Pieces:** Trying to randomly build the different pieces is inefficient, as many of the choices would be discarded for not following a valid polyomino structure. The solution was grouping a valid sequence of pieces by area, which not only solves the aforementioned issue, but also increased the chances of choosing a piece that perfectly fits the remaining space, decreasing the number of errors during the generation.
- **The “Canonicalizer”**: It is a class that helps with the job of creating a valid format of the puzzle, enabling the program to use the `Puzzle`  class and as a result, to create its respective graph which will be used in later steps.
- **The Generating Logic**: The core engine of the program. In brief, it creates a boolean matrix which will be “filled” with the different pieces that were made in the Definition’s phase to create a Goal State. At the start, by using the `random` module the pieces are selected based on the area they use, until a point that some squares are not filled in order to being able to move them. Afterwards, the matrix and with the selected ones,`try_place`  looks options in which the pieces fit.  Once the template is done, the structure is canonicalized and sent to be processed as a Puzzle.
- **The Puzzle’s  Extraction and Evaluation**: First, the puzzle's graph is created. We then attach a "dummy" node connected to all the goals. Through a native BFS distance calculation from this dummy vertex, the program finds the node that is absolute furthest from all goal states. This node, representing the hardest possible state, is assigned as the new starting point of the puzzle. The updated puzzle is later evaluated and saved if it meets the required threshold.

**Performance Trade-off Note:** 

The final part of the program has a problem in its performance. It creates 2 graphs per iteration  (one for the Extraction part and one for the Evaluation one). This happens because the graphs are capped at 700 000 nodes. When the starting point changes in this phase, the Puzzle’s graph of the evaluation does too, giving different scores. 

In order to remain consistent with the marks, 2 graphs are needed, and as a result, the process of generating Puzzles is slow, but effective at the same time. This issue could have been bypassed by discarding puzzles that exceed the node limit, but that would mean throwing away perfectly valid and challenging puzzles, so the dual-graph generation process was kept as an acceptable trade-off.

**Authors & acknowledgements**
- Miguel Pacheco Daneri 
- Marcos Ariza Nieves

©️ **Universitat Politècnica de Catalunya**, 2026