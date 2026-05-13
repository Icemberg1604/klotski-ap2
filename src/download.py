import urllib.request
import json
import os
from typing import Any
import sys

BASE_URL = "https://klotski.pauek.dev"

def get_puzzles() -> Any:

    url = f"{BASE_URL}/api/puzzles"

    with urllib.request.urlopen(url) as response:
        data = response.read()
        return json.loads(data)

def download_puzzle(puzzle_id: str, save_folder="puzzles", name="") -> None:
    """
    Given an puzzle_id, downloads the puzzle with its respective id as a json format. If a name is not given
    """

    url = f"{BASE_URL}/api/puzzles/{puzzle_id}"

    with urllib.request.urlopen(url) as response:
        puzzle_data = json.loads(response.read())

    os.makedirs(save_folder, exist_ok=True)
    
    if name == "":
        name = puzzle_id

    file_path = os.path.join(save_folder, f"{name}.json")

    with open(file_path, "w") as f:
        json.dump(puzzle_data, f, indent=2)
        
    print(f"Puzzle {puzzle_id} descargado con éxito. \n")


def main()-> None:
    
    instruction = sys.argv[1]
    if instruction == "download":
        try:
            puzzle_id = sys.argv[2]

        except:
            raise Exception("No se ha puesto una id")

        name = "" if len(sys.argv) != 4 else sys.argv[3]

        download_puzzle(puzzle_id=puzzle_id, name=name)
    
    elif instruction == "get":

        puzzle_list = get_puzzles()
        print(puzzle_list)

    else:
        raise NotImplemented("No existe este comando")

    
if __name__ == '__main__':
    main()
