import os
import urllib.request
import urllib.error
import json
import sys
import argparse
from pathlib import Path
from dotenv import load_dotenv
import graph_tool.all as gt  # type: ignore

from eval import puzzle_evaluation
import download
from puzzle import Puzzle
from graph import PuzzleGraphBuilder


def submit_rating(puzzle_id: str, rating: float, token: str) -> None:
    """
    Sends the calculated rating for a specific puzzle to the server.
    """
    url = f"https://klotski.pauek.dev/api/puzzles/{puzzle_id}/votes"

    # Package the rating into a JSON payload.
    rating = int(rating)
    data_payload = json.dumps({"stars": rating}).encode("utf-8")

    # Build the HTTP request with the necessary headers
    request = urllib.request.Request(
        url,
        data=data_payload,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        },
    )

    print(f"Sending rating of {rating} stars for puzzle '{puzzle_id}'...")

    try:
        # Fire the request
        with urllib.request.urlopen(request) as response:
            if response.status in [200, 201]:
                print(f"✅ Success! Rating accepted by the server.")
            else:
                print(f"⚠️ Warning: Server returned status {response.status}")

    except urllib.error.HTTPError as e:
        print(f"❌ HTTP Error: {e.code} - {e.reason}")
        # If you get a 401, it means your token is invalid or missing.
        # If you get a 400, the server didn't like the JSON format.
    except Exception as e:
        print(f"❌ An unexpected error occurred: {e}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evaluates a Klotski puzzle and submits the rating to the server.",
        epilog="""
Examples:
  pixi run python src/rate.py                            (Fetches & rates the #1 top puzzle)
  pixi run python src/rate.py 0b1339cc...                (Fetches & rates a specific puzzle)
  pixi run python src/rate.py 0b1339cc... -g path.graphml (Rates using a local graph file)
        """,
        formatter_class=argparse.RawTextHelpFormatter,
    )

    # Define our expected arguments
    parser.add_argument(
        "puzzle_id",
        nargs="?",
        default="TOP",
        help="The ID of the puzzle (Leave blank to auto-fetch the top rated)",
    )
    parser.add_argument(
        "-g",
        "--graph",
        type=str,
        help="Optional: Path to a pre-computed .graphml file to save processing time",
    )

    args = parser.parse_args()

    # 2. SECURELY LOAD THE TOKEN
    load_dotenv()
    MY_TOKEN = os.getenv("KLOTSKI_TOKEN")

    if not MY_TOKEN:
        print("❌ Error: KLOTSKI_TOKEN environment variable is missing.")
        sys.exit(1)

    # 3. DETERMINE THE TARGET PUZZLE
    if args.puzzle_id == "TOP":
        print(
            "No ID provided. Fetching the #1 Top Rated puzzle from the repository..."
        )
        try:
            puzzle_list = download.get_puzzles()
            top_puzzle = puzzle_list[0]
            puzzle_id = top_puzzle["id"] if isinstance(top_puzzle, dict) else top_puzzle
            print(f"Target Locked: {puzzle_id}")
        except Exception as e:
            print(f"❌ Failed to fetch the leaderboard: {e}")
            sys.exit(1)
    else:
        puzzle_id = args.puzzle_id
        print(f"Target Locked: {puzzle_id}")

    # 4. LOAD OR BUILD THE GRAPH
    if args.graph:
        # User provided a specific file via the -g flag
        graph_path = Path(args.graph)
        if not graph_path.is_file():
            print(f"Error: Could not find the graph file at '{graph_path}'")
            sys.exit(1)

        print(f"Loading pre-computed graph from {graph_path.name}...")
        puzzle_graph = gt.load_graph(str(graph_path), fmt="graphml")
    else:
        # Build it in memory using the API
        print(f"Downloading JSON to build graph space in memory...")
        try:
            download.download_puzzle(puzzle_id, save_folder="puzzles", name=puzzle_id)
            json_path = Path(f"puzzles/{puzzle_id}.json")

            with open(json_path, "r", encoding="utf-8") as f:
                puzzle_data = json.load(f)

            clean_json = json.dumps(puzzle_data)
            puz = Puzzle.from_json(clean_json)
            builder = PuzzleGraphBuilder(puz, clean_json)

            print("Processing Breadth-First Search...")
            puzzle_graph = builder.build()
        except Exception as e:
            print(f"❌ Failed to process puzzle: {e}")
            sys.exit(1)

    # 5. CALCULATE & SUBMIT
    print("Calculating heuristic score...")
    raw_score = puzzle_evaluation(puzzle_graph, puzzle_id)
    final_score = max(0.0, min(5.0, raw_score))

    submit_rating(puzzle_id, final_score, MY_TOKEN)


if __name__ == "__main__":
    main()
