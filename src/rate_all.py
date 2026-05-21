"""Batch evaluates and rates all Klotski puzzles in the repository.

This script acts as a master loop, fetching the complete list of puzzles
from the server, downloading any missing local JSON definitions, generating
their graph representations, calculating a heuristic score, and submitting
the ratings sequentially.
"""

import argparse
import os
import sys
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

import download
from eval import extract_graph, puzzle_evaluation
from rate import submit_rating


def main() -> None:
    """Parses arguments, fetches the puzzle master list, and runs the batch evaluation."""
    parser = argparse.ArgumentParser(
        description="Batch evaluates and rates all puzzles in the repository."
    )
    parser.parse_args()

    load_dotenv()
    api_token: str | None = os.getenv("KLOTSKI_TOKEN")
    if not api_token:
        print("Error: KLOTSKI_TOKEN environment variable is missing.")
        sys.exit(1)

    print("Fetching the master list of puzzles...")
    try:
        puzzle_list: list[Any] = download.get_puzzles()
    except Exception as e:
        print(f"Failed to fetch puzzle list: {e}")
        sys.exit(1)

    # Safely extract and explicitly cast puzzle IDs to strings
    puzzle_ids: list[str] = [
        str(p["id"]) if isinstance(p, dict) and "id" in p else str(p) # type: ignore
        for p in puzzle_list
    ]
    print(f"Found {len(puzzle_ids)} puzzles. Starting batch processing...\n")

    for i, puzzle_id in enumerate(puzzle_ids, start=1):
        print(f"--- [{i}/{len(puzzle_ids)}] Processing Puzzle: {puzzle_id} ---")

        try:
            # 1. Ensure we have the JSON using OS-agnostic pathing
            json_path: Path = Path("puzzles") / f"{puzzle_id}.json"
            if not json_path.is_file():
                download.download_puzzle(
                    puzzle_id, save_folder="puzzles", name=puzzle_id
                )

            # 2. Smart load/build the graph
            graph: Any = extract_graph(json_path)

            # 3. Evaluate and Submit
            raw_score: float = float(puzzle_evaluation(graph, puzzle_id))
            final_score: float = max(0.0, min(5.0, raw_score))
            submit_rating(puzzle_id, final_score, api_token)

        except Exception as e:
            print(f"⚠️ Skipping {puzzle_id} due to an error: {e}")
            continue

        print("-" * 50)

    print("\n Batch evaluation complete!")


if __name__ == "__main__":
    main()
