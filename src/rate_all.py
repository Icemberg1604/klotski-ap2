import os
import json
import sys
from pathlib import Path
from dotenv import load_dotenv

# Import the modules you and your partner built
import download
from puzzle import Puzzle
from graph import PuzzleGraphBuilder
from eval import puzzle_evaluation
from rate import submit_rating


def main() -> None:
    # 1. Securely load the API token
    load_dotenv()
    token = os.getenv("KLOTSKI_TOKEN")

    if not token:
        print("❌ Error: KLOTSKI_TOKEN environment variable is missing.")
        sys.exit(1)

    print("Fetching the master list of puzzles from the repository...")
    try:
        puzzle_list = download.get_puzzles()
    except Exception as e:
        print(f"❌ Failed to fetch puzzle list: {e}")
        sys.exit(1)

    # The API might return a list of strings or a list of dictionaries.
    # This safely extracts the ID regardless of the format.
    puzzle_ids = [
        p["id"] if isinstance(p, dict) and "id" in p else p for p in puzzle_list
    ]

    print(f"Found {len(puzzle_ids)} puzzles. Starting batch processing...\n")

    # 2. Iterate through every puzzle in the database
    for i, puzzle_id in enumerate(puzzle_ids, start=1):
        print(f"--- [{i}/{len(puzzle_ids)}] Processing Puzzle: {puzzle_id} ---")

        try:
            # Step A: Download the puzzle JSON
            download.download_puzzle(puzzle_id, save_folder="puzzles", name=puzzle_id)
            json_path = Path(f"puzzles/{puzzle_id}.json")

            # Step B: Read the downloaded JSON
            with open(json_path, "r", encoding="utf-8") as f:
                puzzle_data = json.load(f)

            clean_json = json.dumps(puzzle_data)

            # Step C: Build the Graph (In-Memory)
            print(f"  > Building graph space...")
            puz = Puzzle.from_json(clean_json)
            builder = PuzzleGraphBuilder(puz, clean_json)
            graph = builder.build()

            # Step D: Evaluate the Graph
            print(f"  > Calculating heuristic score...")
            raw_score = puzzle_evaluation(graph, puzzle_id)
            final_score = max(0.0, min(5.0, raw_score))

            # Step E: Submit the Rating
            submit_rating(puzzle_id, final_score, token)

        except Exception as e:
            print(f"⚠️ Skipping {puzzle_id} due to an error: {e}")
            continue  # If one puzzle fails (e.g. impossible to solve), skip to the next

        print("-" * 50)

    print("\n✅ Batch evaluation complete!")


if __name__ == "__main__":
    main()
