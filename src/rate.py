import os
from dotenv import load_dotenv
import urllib.request
import urllib.error
import json
import sys
from pathlib import Path
import graph_tool.all as gt  # type: ignore

# Import your evaluation logic
from eval import puzzle_evaluation


def submit_rating(puzzle_id: str, rating: float, token: str) -> None:
    """
    Sends the calculated rating for a specific puzzle to the server.
    """
    url = f"https://klotski.pauek.dev/api/puzzles/{puzzle_id}/votes"

    # Package the rating into a JSON payload.
    data_payload = json.dumps({"vote": rating}).encode("utf-8")

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
    # Expecting: python src/rate.py <puzzle_id> <path_to_graphml>
    if len(sys.argv) != 3:
        print("Usage: python src/rate.py <puzzle_id> <path_to_graphml>")
        sys.exit(1)

    puzzle_id = sys.argv[1]
    graph_path_str = sys.argv[2]

    # 1. Load the graph
    graph_path = Path(graph_path_str)
    if not graph_path.is_file():
        print(f"Error: Could not find the file {graph_path}")
        sys.exit(1)

    print(f"Loading graph {graph_path.name}...")
    puzzle_graph = gt.load_graph(str(graph_path), fmt="graphml")

    # 2. Calculate the score
    raw_score = puzzle_evaluation(puzzle_graph, graph_path.stem)
    final_score = max(0.0, min(5.0, raw_score))

    # 3. SECURELY LOAD THE TOKEN
    load_dotenv()
    MY_TOKEN = os.getenv("KLOTSKI_TOKEN")

    # Fail gracefully if the token is missing
    if not MY_TOKEN:
        print("❌ Error: KLOTSKI_TOKEN environment variable is missing.")
        print("Please ensure you have a .env file with KLOTSKI_TOKEN=your_token")
        sys.exit(1)

    # 4. Submit to the API
    submit_rating(puzzle_id, final_score, MY_TOKEN)


if __name__ == "__main__":
    main()
