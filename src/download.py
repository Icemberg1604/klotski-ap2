"""
Klotski Puzzle Downloader

This module interacts with the Klotski API to retrieve the master list of
available puzzles and download specific puzzle data in canonical JSON format.
It can be imported as a module by other scripts or run directly via the CLI.
"""

import urllib.request
import urllib.error
import json
import sys
import argparse
from pathlib import Path
from typing import Any, List, Dict, Union

BASE_URL = "https://klotski.pauek.dev"


def get_puzzles() -> List[Union[str, Dict[str, Any]]]:
    """
    Fetches the master list of all available puzzles from the repository.

    Returns:
        A list containing puzzle IDs (or dictionaries containing puzzle data)
        retrieved from the server.
    """
    url = f"{BASE_URL}/api/puzzles"

    try:
        with urllib.request.urlopen(url) as response:
            data = response.read()
            return json.loads(data)
    except urllib.error.URLError as e:
        print(f"Failed to connect to the Klotski API: {e}")
        sys.exit(1)


def download_puzzle(
    puzzle_id: str, save_folder: str = "puzzles", name: str = ""
) -> None:
    """
    Downloads a specific puzzle from the API and saves it locally as a JSON file.

    Args:
        puzzle_id: The unique identifier of the puzzle to download.
        save_folder: The directory where the file will be saved. Defaults to 'puzzles'.
        name: An optional custom name for the file (without the .json extension).
              If not provided, defaults to the puzzle_id.
    """
    url = f"{BASE_URL}/api/puzzles/{puzzle_id}"

    try:
        with urllib.request.urlopen(url) as response:
            puzzle_data = json.loads(response.read())
    except urllib.error.HTTPError as e:
        print(f"HTTP Error {e.code}: Could not find puzzle '{puzzle_id}'")
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"Network Error: {e}")
        sys.exit(1)

    folder_path = Path(save_folder)
    folder_path.mkdir(parents=True, exist_ok=True)

    file_name = name if name else puzzle_id
    file_path = folder_path / f"{file_name}.json"

    # Extract the core puzzle dictionary if the server wrapped it
    if "puzzle" in puzzle_data:
        puzzle_data = puzzle_data["puzzle"]

    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(puzzle_data, f, indent=2)

    print(f"Puzzle '{puzzle_id}' downloaded successfully to {file_path}")


def main() -> None:
    """
    Parses command-line arguments and executes the appropriate download or retrieval task.
    """
    parser = argparse.ArgumentParser(
        description="Fetch and download Klotski puzzles from the class repository.",
        epilog="""
Examples:
  pixi run python src/download.py get                      (Lists all available puzzles)
  pixi run python src/download.py download 0b1339cc...     (Downloads a specific puzzle)
  pixi run python src/download.py download 0b13... -n test (Downloads and renames the file)
        """,
        formatter_class=argparse.RawTextHelpFormatter,
    )

    # Create sub-commands for 'get' and 'download'
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Parser for the "get" command
    subparsers.add_parser("get", help="List all puzzles available on the server")

    # Parser for the "download" command
    dl_parser = subparsers.add_parser(
        "download", help="Download a specific puzzle by ID"
    )
    dl_parser.add_argument(
        "puzzle_id", type=str, help="The ID of the puzzle to download"
    )
    dl_parser.add_argument(
        "-n",
        "--name",
        type=str,
        default="",
        help="Optional: Save the file with a custom name instead of the ID",
    )

    args = parser.parse_args()

    # Handle the case where no arguments are passed
    if args.command is None:
        parser.print_help()
        sys.exit(1)

    # Route to the appropriate function
    if args.command == "get":
        puzzle_list = get_puzzles()
        print(f"--- Found {len(puzzle_list)} puzzles ---")
        for index, puzzle in enumerate(puzzle_list, start=1):
            print(f"{index}: {puzzle}")

    elif args.command == "download":
        download_puzzle(puzzle_id=args.puzzle_id, name=args.name)


if __name__ == "__main__":
    main()
