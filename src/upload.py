import os
from dotenv import load_dotenv
import urllib.request
import urllib.error
import json
import sys
from pathlib import Path


def upload_puzzle(puzzle_file_path: Path, token: str) -> None:
    """
    Reads a canonical JSON puzzle from disk and uploads it to the server.
    """
    url = "https://klotski.pauek.dev/api/puzzles"

    # 1. Safely read and parse the JSON file
    try:
        with open(puzzle_file_path, "r", encoding="utf-8") as file:
            puzzle_data = json.load(file)
    except json.JSONDecodeError:
        print(f"❌ Error: {puzzle_file_path.name} is not a valid JSON file.")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error reading file: {e}")
        sys.exit(1)

    # 2. Package the data for transit
    data_payload = json.dumps(puzzle_data).encode("utf-8")

    # 3. Build the request
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

    # 4. Fire the request
    try:
        with urllib.request.urlopen(request) as response:
            if response.status in [200, 201]:
                print("✅ Success! Puzzle accepted by the server.")

                # The server might send back the new ID or confirmation data
                response_body = response.read().decode("utf-8")
                if response_body:
                    print(f"Server response: {response_body}")
            else:
                print(f"⚠️ Warning: Server returned status {response.status}")

    except urllib.error.HTTPError as e:
        print(f"❌ HTTP Error: {e.code} - {e.reason}")
        # If the server rejects the puzzle (e.g., it's not canonical), it often sends an explanation
        error_msg = e.read().decode("utf-8")
        if error_msg:
            print(f"Server details: {error_msg}")

    except Exception as e:
        print(f"❌ An unexpected error occurred: {e}")


def main() -> None:

    if len(sys.argv) != 2:
        print("Usage: python src/upload.py <path_to_puzzle.json>")
        sys.exit(1)

    puzzle_path_str = sys.argv[1]
    puzzle_path = Path(puzzle_path_str)

    if not puzzle_path.is_file():
        print(f"Error: Could not find the file {puzzle_path}")
        sys.exit(1)

    # Securely load the token
    load_dotenv()
    MY_TOKEN = os.getenv("KLOTSKI_TOKEN")

    if not MY_TOKEN:
        print("❌ Error: KLOTSKI_TOKEN environment variable is missing.")
        sys.exit(1)

    upload_puzzle(puzzle_path, MY_TOKEN)


if __name__ == "__main__":
    main()
