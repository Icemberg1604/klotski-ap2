"""Evaluates Klotski puzzles and submits their heuristic ratings to the server.

This module acts as a CLI utility to either fetch the top-rated puzzle or
evaluate a specific puzzle by ID. It downloads missing puzzle JSON files,
extracts their graph structures, computes a heuristic score, and submits
the rounded result to the Klotski API.
"""

import os
import urllib.request
import urllib.error
import json
import sys
import argparse
from pathlib import Path
from typing import Any
from dotenv import load_dotenv

# Puzzle download and evaluation logic
from eval import puzzle_evaluation, extract_graph
import download


def submit_rating(puzzle_id: str, rating: float, tokens: list[str]) -> None:
    """Sends the calculated rating for a specific puzzle to the server.

    Args:
        puzzle_id: The unique identifier of the target puzzle.
        rating: The calculated raw score (float). This will be rounded
            to the nearest integer star rating before submission.
        tokens: A list of the Bearer authorization token for API access.
    """
    url = f"https://klotski.pauek.dev/api/puzzles/{puzzle_id}/votes"
    integer_stars = int(round(rating))
    data_payload = json.dumps({"stars": integer_stars}).encode("utf-8")

    for idx, token in enumerate(tokens, start=1):
        request = urllib.request.Request(
            url,
            data=data_payload,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {token}",
            },
        )

        print(
            f"Sending rating of {integer_stars} stars for puzzle '{puzzle_id}'with token {idx}..."
        )

        try:
            with urllib.request.urlopen(request) as response:
                if response.status in [200, 201]:
                    print(f"Rating accepted by the server for Token {idx}.")
                else:
                    print(f"Warning: Server returned status {response.status}")
        except urllib.error.HTTPError as e:
            print(f"HTTP Error: {e.code} - {e.reason}")
            error_msg = e.read().decode("utf-8")
            if error_msg:
                print(f"Server details: {error_msg}")
        except Exception as e:
            print(f"An unexpected error occurred: {e}")


def main() -> None:
    """Parses arguments, orchestrates the puzzle evaluation, and triggers submission."""

    # 1. SETUP THE COMMAND LINE INTERFACE
    parser = argparse.ArgumentParser(
        description="Evaluates a Klotski puzzle and submits the rating to the server for all configured tokens.",
        epilog=(
            """Examples:
                pixi run python src/rate.py                (Fetches & rates the #1 top puzzle)
                pixi run python src/rate.py 0b1339cc...    (Rates a specific puzzle, automatically using/building its graph)"""
        ),
        formatter_class=argparse.RawTextHelpFormatter,
    )

    parser.add_argument(
        "puzzle_id",
        nargs="?",
        default="TOP",
        help="The ID of the puzzle (Leave blank to auto-fetch the top rated)",
    )

    args = parser.parse_args()

    # 2. SECURELY LOAD THE TOKEN
    load_dotenv()

    active_tokens: list[str] = []
    token1 = os.getenv("KLOTSKI_TOKEN")
    token2 = os.getenv("FRIEND_KLOTSKI_TOKEN")

    if token1:
        active_tokens.append(token1)
    if token2:
        active_tokens.append(token2)

    if not active_tokens:
        print("Error: KLOTSKI_TOKEN environment variable is missing.")
        sys.exit(1)

    print(f"System initialized with {len(active_tokens)} active credential(s).")

    # 3. DETERMINE THE TARGET PUZZLE
    puzzle_id: str = ""
    if args.puzzle_id == "TOP":
        print("No ID provided. Fetching the #1 Top Rated puzzle...")
        try:
            puzzle_list: list[Any] = download.get_puzzles()
            top_puzzle: Any = puzzle_list[0]
            # Handle whether top_puzzle is a dictionary or just a string ID
            puzzle_id = str(top_puzzle["id"]) if isinstance(top_puzzle, dict) else str(top_puzzle)  # type: ignore
            print(f"Target Locked: {puzzle_id}")
        except Exception as e:
            print(f"Failed to fetch leaderboard: {e}")
            sys.exit(1)
    else:
        puzzle_id = str(args.puzzle_id)
        print(f"Target Locked: {puzzle_id}")

    # 4. GET THE JSON (Download if we don't have it locally)
    json_path = Path(f"puzzles/{puzzle_id}.json")
    if not json_path.is_file():
        print("JSON not found locally. Downloading...")
        download.download_puzzle(puzzle_id, save_folder="puzzles", name=puzzle_id)

    # 5. SMART GRAPH EXTRACTION
    try:
        puzzle_graph = extract_graph(json_path)
    except Exception as e:
        print(f"Failed to process graph: {e}")
        sys.exit(1)

    # 6. CALCULATE & SUBMIT
    print("Calculating heuristic score...")
    raw_score = puzzle_evaluation(puzzle_graph, puzzle_id)
    final_score = max(0.0, min(5.0, raw_score))

    submit_rating(puzzle_id, final_score, active_tokens)


if __name__ == "__main__":
    main()
