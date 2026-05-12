import urllib.request
import json
import os
from typing import Any
BASE_URL = "https://klotski.pauek.dev"

def get_puzzles() -> Any:
    url = f"{BASE_URL}/api/puzzles"
    with urllib.request.urlopen(url) as response:
        data = response.read()
        return json.loads(data)

def download_puzzle(puzzle_id: str, save_folder="puzzles") -> None:
    url = f"{BASE_URL}/api/puzzles/{puzzle_id}"
    with urllib.request.urlopen(url) as response:
        puzzle_data = json.loads(response.read())
    os.makedirs(save_folder, exist_ok=True)
    name = input("Escribe el nombre:\n")
    file_path = os.path.join(save_folder, f"{name}.json")
    with open(file_path, "w") as f:
        json.dump(puzzle_data, f, indent=2)
        
    print(f"Puzzle {puzzle_id} descargado con éxito.")


def main()-> None:
    instruction = input("Selecciona que quieres hacer: download o get: \n")
    if instruction == "download":
        puzzle_id = input("Escribe la id del puzzle: \n")
        download_puzzle(puzzle_id=puzzle_id)
    
    elif instruction == "get":

        puzzle_list = get_puzzles()
        print(puzzle_list)

    else:
        raise NotImplemented("No existe este comando\n")

    
if __name__ == '__main__':
    main()
