"""Uploads canonical JSON puzzle files to the class server.

This CLI utility reads a local Klotski puzzle JSON file and pushes it
to the central repository via an authenticated POST request. It handles
file validation, JSON serialization, and server response parsing.
"""

import os
from dotenv import load_dotenv
import urllib.request
import urllib.error
import json
import sys
import argparse
from pathlib import Path


def upload_puzzle(puzzle_file_path: Path, token: str) -> None:
    """Reads a puzzle JSON file and uploads it to the server.

    Args:
        puzzle_file_path: The local path to the JSON puzzle file.
        token: The Bearer authorization token for API access.
    """
    url = "https://klotski.pauek.dev/api/puzzles"

    try:
        with open(puzzle_file_path, "r", encoding="utf-8") as file:
            puzzle_data = json.load(file)
    except Exception as e:
        print(f"❌ Error reading file: {e}")
        sys.exit(1)

    data_payload = json.dumps(puzzle_data).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data_payload,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        },
    )

    print(f"Uploading puzzle '{puzzle_file_path.name}' to the repository...")
    try:
        with urllib.request.urlopen(request) as response:
            if response.status in [200, 201]:
                print("Success! Puzzle accepted by the server.")
                response_body = response.read().decode("utf-8")
                if response_body:
                    print(f"Server response: {response_body}")
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
    """Parses CLI arguments, validates the file path, and triggers the upload."""
    parser = argparse.ArgumentParser(
        description="Uploads a canonical JSON puzzle file to the class server.",
        epilog="Example:\n  pixi run python src/upload.py puzzles/my_new_puzzle.json",
        formatter_class=argparse.RawTextHelpFormatter,
    )

    parser.add_argument(
        "puzzle_path", type=str, help="Path to the JSON puzzle file you want to upload."
    )
    args = parser.parse_args()

    puzzle_path = Path(args.puzzle_path)
    if not puzzle_path.is_file():
        print(f"Error: Could not find the file {puzzle_path}")
        sys.exit(1)

    load_dotenv()
    MY_TOKEN = os.getenv("KLOTSKI_TOKEN1")
    if not MY_TOKEN:
        print("Error: KLOTSKI_TOKEN environment variable is missing.")
        sys.exit(1)

    upload_puzzle(puzzle_path, MY_TOKEN)


if __name__ == "__main__":
    main()
