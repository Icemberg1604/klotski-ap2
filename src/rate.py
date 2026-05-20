import os
from dotenv import load_dotenv
import urllib.request
import urllib.error
import json
import sys
from pathlib import Path
import graph_tool.all as gt  # type: ignore

# Import your evaluation and partner's generation logic
from eval import puzzle_evaluation
import download
from puzzle import Puzzle
from graph import PuzzleGraphBuilder


def submit_rating(puzzle_id: str, rating: float, token: str) -> None:
    """
    Sends the calculated rating for a specific puzzle to the server.
    """
    url = f"https://klotski.pauek.dev/api/puzzles/{puzzle_id}/votes"

    # Enforce integer rounding as required by the server API
    integer_stars = int(round(rating))
    data_payload = json.dumps({"stars": integer_stars}).encode("utf-8")

    request = urllib.request.Request(
        url,
        data=data_payload,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        },
    )

    print(f"Sending rating of {integer_stars} stars for puzzle '{puzzle_id}'...")

    try:
        with urllib.request.urlopen(request) as response:
            if response.status in [200, 201]:
                print(f"✅ Success! Rating accepted by the server.")
            else:
                print(f"⚠️ Warning: Server returned status {response.status}")

    except urllib.error.HTTPError as e:
        print(f"❌ HTTP Error: {e.code} - {e.reason}")
        error_msg = e.read().decode("utf-8")
        if error_msg:
            print(f"Server details: {error_msg}")
    except Exception as e:
        print(f"❌ An unexpected error occurred: {e}")


def main() -> None:
    # 1. SECURELY LOAD THE TOKEN
    load_dotenv()
    MY_TOKEN = os.getenv("KLOTSKI_TOKEN")

    if not MY_TOKEN:
        print("❌ Error: KLOTSKI_TOKEN environment variable is missing.")
        print("Please ensure you have a .env file with KLOTSKI_TOKEN=your_token")
        sys.exit(1)

    args_count = len(sys.argv)

    # Mode 1: Fully Manual (ID and local .graphml file provided)
    if args_count == 3:
        puzzle_id = sys.argv[1]
        graph_path_str = sys.argv[2]

        graph_path = Path(graph_path_str)
        if not graph_path.is_file():
            print(f"Error: Could not find the file {graph_path}")
            sys.exit(1)

        print(f"Loading graph {graph_path.name} from disk...")
        puzzle_graph = gt.load_graph(str(graph_path), fmt="graphml")

    # Mode 2 & 3: Dynamic Fetching (API handles the graph in memory)
    elif args_count <= 2:
        if args_count == 2:
            # Mode 2: Only ID provided
            puzzle_id = sys.argv[1]
            print(f"Fetching specific puzzle '{puzzle_id}' from the repository...")
        else:
            # Mode 3: No arguments provided (Fallback to Top Rated)
            print("No arguments provided. Fetching the #1 Top Rated puzzle...")
            try:
                puzzle_list = download.get_puzzles()
                # Safely extract the first ID, whether it's a string or dict
                top_puzzle = puzzle_list[0]
                puzzle_id = (
                    top_puzzle["id"] if isinstance(top_puzzle, dict) else top_puzzle
                )
                print(f"Top puzzle found: {puzzle_id}")
            except Exception as e:
                print(f"❌ Failed to fetch the leaderboard: {e}")
                sys.exit(1)

        # Build the graph in-memory using the downloaded JSON
        try:
            download.download_puzzle(puzzle_id, save_folder="puzzles", name=puzzle_id)
            json_path = Path(f"puzzles/{puzzle_id}.json")

            with open(json_path, "r", encoding="utf-8") as f:
                puzzle_data = json.load(f)

            clean_json = json.dumps(puzzle_data)

            print("Building graph space in memory...")
            puz = Puzzle.from_json(clean_json)
            builder = PuzzleGraphBuilder(puz, clean_json)
            puzzle_graph = builder.build()

        except Exception as e:
            print(f"❌ Failed to process puzzle '{puzzle_id}': {e}")
            sys.exit(1)

    else:
        # Too many arguments
        print("Usage Errors. Supported commands:")
        print("  python src/rate.py <puzzle_id> <path_to_graphml>  # Local graph")
        print("  python src/rate.py <puzzle_id>                    # Fetch by ID")
        print("  python src/rate.py                                # Fetch Top Rated")
        sys.exit(1)

    # 4. Calculate the score and submit
    print("Calculating heuristic score...")
    raw_score = puzzle_evaluation(puzzle_graph, puzzle_id)
    final_score = max(0.0, min(5.0, raw_score))

    submit_rating(puzzle_id, final_score, MY_TOKEN)


if __name__ == "__main__":
    main()
