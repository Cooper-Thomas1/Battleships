"""
battleship.py

Contains core data structures and logic for Battleship, including:
 - Board class for storing ship positions, hits, misses
 - Utility function parse_coordinate for translating e.g. 'B5' -> (row, col)
 - A test harness run_single_player_game() to demonstrate the logic in a local, single-player mode

"""

import random
import threading
import queue
from crypto_utils import decrypt_message

BOARD_SIZE = 10
SHIPS = [
    ("Carrier", 5),
    ("Battleship", 4),
    ("Cruiser", 3),
    ("Submarine", 3),
    ("Destroyer", 2)
]
TIMEOUT = 30 # seconds 

class Board:
    """
    Represents a single Battleship board with hidden ships.
    We store:
      - self.hidden_grid: tracks real positions of ships ('S'), hits ('X'), misses ('o')
      - self.display_grid: the version we show to the player ('.' for unknown, 'X' for hits, 'o' for misses)
      - self.placed_ships: a list of dicts, each dict with:
          {
             'name': <ship_name>,
             'positions': set of (r, c),
          }
        used to determine when a specific ship has been fully sunk.

    In a full 2-player networked game:
      - Each player has their own Board instance.
      - When a player fires at their opponent, the server calls
        opponent_board.fire_at(...) and sends back the result.
    """

    def __init__(self, size=BOARD_SIZE):
        self.size = size
        # '.' for empty water
        self.hidden_grid = [['.' for _ in range(size)] for _ in range(size)]
        # display_grid is what the player or an observer sees (no 'S')
        self.display_grid = [['.' for _ in range(size)] for _ in range(size)]
        self.placed_ships = []  # e.g. [{'name': 'Destroyer', 'positions': {(r, c), ...}}, ...]

    def place_ships_randomly(self, ships=SHIPS):
        """
        Randomly place each ship in 'ships' on the hidden_grid, storing positions for each ship.
        In a networked version, you might parse explicit placements from a player's commands
        (e.g. "PLACE A1 H BATTLESHIP") or prompt the user for board coordinates and placement orientations; 
        the self.place_ships_manually() can be used as a guide.
        """
        for ship_name, ship_size in ships:
            placed = False
            while not placed:
                orientation = random.randint(0, 1)  # 0 => horizontal, 1 => vertical
                row = random.randint(0, self.size - 1)
                col = random.randint(0, self.size - 1)

                if self.can_place_ship(row, col, ship_size, orientation):
                    occupied_positions = self.do_place_ship(row, col, ship_size, orientation)
                    self.placed_ships.append({
                        'name': ship_name,
                        'positions': occupied_positions
                    })
                    placed = True


    def place_ships_manually(self, ships=SHIPS):
        """
        Prompt the user for each ship's starting coordinate and orientation (H or V).
        Validates the placement; if invalid, re-prompts.
        """
        print("\nPlease place your ships manually on the board.")
        for ship_name, ship_size in ships:
            while True:
                self.print_display_grid(show_hidden_board=True)
                print(f"\nPlacing your {ship_name} (size {ship_size}).")
                coord_str = input("  Enter starting coordinate (e.g. A1): ").strip()
                orientation_str = input("  Orientation? Enter 'H' (horizontal) or 'V' (vertical): ").strip().upper()

                try:
                    row, col = parse_coordinate(coord_str)
                except ValueError as e:
                    print(f"  [!] Invalid coordinate: {e}")
                    continue

                # Convert orientation_str to 0 (horizontal) or 1 (vertical)
                if orientation_str == 'H':
                    orientation = 0
                elif orientation_str == 'V':
                    orientation = 1
                else:
                    print("  [!] Invalid orientation. Please enter 'H' or 'V'.")
                    continue

                # Check if we can place the ship
                if self.can_place_ship(row, col, ship_size, orientation):
                    occupied_positions = self.do_place_ship(row, col, ship_size, orientation)
                    self.placed_ships.append({
                        'name': ship_name,
                        'positions': occupied_positions
                    })
                    break
                else:
                    print(f"  [!] Cannot place {ship_name} at {coord_str} (orientation={orientation_str}). Try again.")


    def can_place_ship(self, row, col, ship_size, orientation):
        """
        Check if we can place a ship of length 'ship_size' at (row, col)
        with the given orientation (0 => horizontal, 1 => vertical).
        Returns True if the space is free, False otherwise.
        """
        if orientation == 0:  # Horizontal
            if col + ship_size > self.size:
                return False
            for c in range(col, col + ship_size):
                if self.hidden_grid[row][c] != '.':
                    return False
        else:  # Vertical
            if row + ship_size > self.size:
                return False
            for r in range(row, row + ship_size):
                if self.hidden_grid[r][col] != '.':
                    return False
        return True

    def do_place_ship(self, row, col, ship_size, orientation):
        """
        Place the ship on hidden_grid by marking 'S', and return the set of occupied positions.
        """
        occupied = set()
        if orientation == 0:  # Horizontal
            for c in range(col, col + ship_size):
                self.hidden_grid[row][c] = 'S'
                occupied.add((row, c))
        else:  # Vertical
            for r in range(row, row + ship_size):
                self.hidden_grid[r][col] = 'S'
                occupied.add((r, col))
        return occupied

    def fire_at(self, row, col):
        """
        Fire at (row, col). Return a tuple (result, sunk_ship_name).
        Possible outcomes:
          - ('hit', None)          if it's a hit but not sunk
          - ('hit', <ship_name>)   if that shot causes the entire ship to sink
          - ('miss', None)         if no ship was there
          - ('already_shot', None) if that cell was already revealed as 'X' or 'o'

        The server can use this result to inform the firing player.
        """
        cell = self.hidden_grid[row][col]
        if cell == 'S':
            # Mark a hit
            self.hidden_grid[row][col] = 'X'
            self.display_grid[row][col] = 'X'
            # Check if that hit sank a ship
            sunk_ship_name = self._mark_hit_and_check_sunk(row, col)
            if sunk_ship_name:
                return ('hit', sunk_ship_name)  # A ship has just been sunk
            else:
                return ('hit', None)
        elif cell == '.':
            # Mark a miss
            self.hidden_grid[row][col] = 'o'
            self.display_grid[row][col] = 'o'
            return ('miss', None)
        elif cell == 'X' or cell == 'o':
            return ('already_shot', None)
        else:
            # In principle, this branch shouldn't happen if 'S', '.', 'X', 'o' are all possibilities
            return ('already_shot', None)

    def _mark_hit_and_check_sunk(self, row, col):
        """
        Remove (row, col) from the relevant ship's positions.
        If that ship's positions become empty, return the ship name (it's sunk).
        Otherwise return None.
        """
        for ship in self.placed_ships:
            if (row, col) in ship['positions']:
                ship['positions'].remove((row, col))
                if len(ship['positions']) == 0:
                    return ship['name']
                break
        return None

    def all_ships_sunk(self):
        """
        Check if all ships are sunk (i.e. every ship's positions are empty).
        """
        for ship in self.placed_ships:
            if len(ship['positions']) > 0:
                return False
        return True

    def print_display_grid(self, show_hidden_board=False):
        """
        Print the board as a 2D grid.
        
        If show_hidden_board is False (default), it prints the 'attacker' or 'observer' view:
        - '.' for unknown cells,
        - 'X' for known hits,
        - 'o' for known misses.
        
        If show_hidden_board is True, it prints the entire hidden grid:
        - 'S' for ships,
        - 'X' for hits,
        - 'o' for misses,
        - '.' for empty water.
        """
        # Decide which grid to print
        grid_to_print = self.hidden_grid if show_hidden_board else self.display_grid

        # Column headers (1 .. N)
        print("  " + "".join(str(i + 1).rjust(2) for i in range(self.size)))
        # Each row labeled with A, B, C, ...
        for r in range(self.size):
            row_label = chr(ord('A') + r)
            row_str = " ".join(grid_to_print[r][c] for c in range(self.size))
            print(f"{row_label:2} {row_str}")


def parse_coordinate(coord_str):
    """
    Convert something like 'B5' into zero-based (row, col).
    Example: 'A1' => (0, 0), 'C10' => (2, 9)
    HINT: you might want to add additional input validation here...
    """
    coord_str = coord_str.strip().upper()
    row_letter = coord_str[0]
    col_digits = coord_str[1:]

    row = ord(row_letter) - ord('A')
    col = int(col_digits) - 1  # zero-based

    return (row, col)


def run_single_player_game_locally():
    """
    A test harness for local single-player mode, demonstrating two approaches:
     1) place_ships_manually()
     2) place_ships_randomly()

    Then the player tries to sink them by firing coordinates.
    """

    def timed_input(prompt):
        def get_input():
            global user_input
            user_input = input(prompt)

        thread = threading.Thread(target=get_input, daemon=True)
        thread.start()
        thread.join(TIMEOUT)

        if thread.is_alive():
            return None # timout reached
        else: 
            return user_input

    board = Board(BOARD_SIZE)

    # Ask user how they'd like to place ships
    choice = input("Place ships manually (M) or randomly (R)? [M/R]: ").strip().upper()
    if choice == 'M':
        board.place_ships_manually(SHIPS)
    else:
        board.place_ships_randomly(SHIPS)

    print("\nNow try to sink all the ships!")
    moves = 0
    while True:
        board.print_display_grid()
        guess = timed_input("\nEnter coordinate to fire at (or 'quit'): ")
        
        if guess is None:
            print("\nGame Over! You took too long to respond.")
            return # end game
        
        guess = guess.strip()

        if guess.lower() == 'quit':
            print("Thanks for playing. Exiting...")
            return

        try:
            row, col = parse_coordinate(guess)
            result, sunk_name = board.fire_at(row, col)
            moves += 1

            if result == 'hit':
                if sunk_name:
                    print(f"  >> HIT! You sank the {sunk_name}!")
                else:
                    print("  >> HIT!")
                if board.all_ships_sunk():
                    board.print_display_grid()
                    print(f"\nCongratulations! You sank all ships in {moves} moves.")
                    break
            elif result == 'miss':
                print("  >> MISS!")
            elif result == 'already_shot':
                print("  >> You've already fired at that location. Try again.")

        except ValueError as e:
            print("  >> Invalid input:", e)


def run_single_player_game_online(rfile, wfile):
    """
    A test harness for running the single-player game with I/O redirected to socket file objects.
    Expects:
      - rfile: file-like object to .readline() from client
      - wfile: file-like object to .write() back to client
    
    #####
    NOTE: This function is (intentionally) currently somewhat "broken", which will be evident if you try and play the game via server/client.
    You can use this as a starting point, or write your own.
    #####
    """
    def send(msg):
        wfile.write(msg + '\n')
        wfile.flush()

    def send_board(board):
        wfile.write("GRID\n")
        wfile.write("  " + " ".join(str(i + 1).rjust(2) for i in range(board.size)) + '\n')
        for r in range(board.size):
            row_label = chr(ord('A') + r)
            row_str = " ".join(board.display_grid[r][c] for c in range(board.size))
            wfile.write(f"{row_label:2} {row_str}\n")
        wfile.write('\n')
        wfile.flush()

    def recv():
        return rfile.readline().strip()

    board = Board(BOARD_SIZE)
    board.place_ships_randomly(SHIPS) 

    send("Welcome to Online Single-Player Battleship! Try to sink all the ships. Type 'quit' to exit.")

    moves = 0
    while True:
        send_board(board)
        send("Enter coordinate to fire at (e.g. B5):")
        guess = recv()
        if guess.lower() == 'quit':
            send("Thanks for playing. Goodbye.")
            return

        try:
            row, col = parse_coordinate(guess)
            result, sunk_name = board.fire_at(row, col)
            moves += 1

            if result == 'hit':
                if sunk_name:
                    send(f"HIT! You sank the {sunk_name}!")
                else:
                    send("HIT!")
                if board.all_ships_sunk():
                    send_board(board)
                    send(f"Congratulations! You sank all ships in {moves} moves.")
                    return
            elif result == 'miss':
                send("MISS!")
            elif result == 'already_shot':
                send("You've already fired at that location.")
        except ValueError as e:
            send(f"Invalid input: {e}")

def send(wfile, msg):
    wfile.write(msg + '\n')
    wfile.flush()

def recv(rfile):
    return rfile.readline().strip()

def send_board(wfile, board):
    wfile.write("GRID\n")
    wfile.write("  " + " ".join(str(i + 1).rjust(2) for i in range(board.size)) + '\n')
    for r in range(board.size):
        row_label = chr(ord('A') + r)
        row_str = " ".join(board.display_grid[r][c] for c in range(board.size))
        wfile.write(f"{row_label:2} {row_str}\n")
    wfile.write('\n')
    wfile.flush()

def timed_input(rfile, timeout=TIMEOUT):
    result = {}
    def worker():
        try:
            raw_data = rfile.readline().strip()
            encrypted_msg = raw_data.split('|')[1]
            decrypted_msg = decrypt_message(encrypted_msg)
            result['data'] = decrypted_msg
        except Exception:
            result['data'] = None

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    thread.join(timeout)

    if thread.is_alive():
        return None # timeout reaches
    else:
        return result.get('data', None)

def broadcast_game_state_to_spectators(players, message, broadcast_callback):
    """
    Broadcast the current game state to all spectators.
    """
    game_state = []
    for p in players:
        board_state = f"{p['name']}'s Board:\n"
        board_state += "  " + " ".join(str(i + 1).rjust(2) for i in range(p["board"].size)) + '\n'
        for r in range(p["board"].size):
            row_label = chr(ord('A') + r)
            row_str = " ".join(p["board"].display_grid[r][c] for c in range(p["board"].size))
            board_state += f"{row_label:2} {row_str}\n"
        game_state.append(board_state)
    
    full_message = f"{message}\n\n" + "\n\n".join(game_state)
    broadcast_callback(full_message)

def run_two_player_game_online(player1_io, player2_io, broadcast_callback, save_state_callback, player1_id, player2_id, initial_state=None):
    """
    Runs a turn-based Battleship game between two online players.
    Each player_io is a tuple of (rfile, wfile) file-like objects.
    """

    rfile1, wfile1 = player1_io
    rfile2, wfile2 = player2_io

    if initial_state:
        board1 = initial_state['board1']    
        board2 = initial_state['board2']         
        current = initial_state['turn']     
        moves = [                                     
            initial_state['moves']['Player 1'], 
            initial_state['moves']['Player 2'] 
        ]

    else:
        board1 = Board(BOARD_SIZE)
        board2 = Board(BOARD_SIZE)
        board1.place_ships_randomly(SHIPS)
        board2.place_ships_randomly(SHIPS)
        current = 0  # Index of current player
        moves = [0, 0]  # Track moves per player

    players = [
        {"name": "Player 1", "r": rfile1, "w": wfile1, "board": board2}, # Fires at player 2’s board
        {"name": "Player 2", "r": rfile2, "w": wfile2, "board": board1} # Fires at player 1’s board
    ]

    if not initial_state:
        for p in players:
            send(p["w"], f"Welcome {p['name']}! Game is starting now. Type 'quit' to exit.\n")
        broadcast_game_state_to_spectators(players, "Game started. Here are the initial boards:", broadcast_callback)

    while True: # Outer loop: Manages the game flow
        p = players[current]
        opponent = players[1 - current]

        send(p["w"], "It's your turn! Enter a coordinate to fire at (e.g., B5):")
        send(opponent["w"], f"Waiting for {p['name']} to take their turn...")

        send_board(p["w"], p["board"])

        while True: # Inner loop: Handles input and game logic
            guess = timed_input(p["r"])
            
            if guess is None:
                send(p["w"], "Time's up! You took too long to respond.\n")
                send(opponent["w"], f"{p['name']} took too long.\n")
                broadcast_game_state_to_spectators(players, f"{p['name']} took too long. Turn forfeited.", broadcast_callback)
                break  # forfeit turn
            
            if not guess:
                send(p["w"], "No input received. Please enter a coordinate like B5.")
                continue

            if guess.lower() == 'quit':
                send(p["w"], "\nYou forfeited the game.")
                send(opponent["w"], "\nOpponent forfeited. You win!")
                
                # Send final boards to both players
                send_board(p["w"], p["board"])
                send_board(opponent["w"], opponent["board"])

                broadcast_game_state_to_spectators(players, "Game over. A player forfeited.", broadcast_callback)

                game_data = {
                    'board1': p["board"],  # Player 1's board
                    'board2': opponent["board"],  # Player 2's board
                    'turn': current,  # Current player turn
                    'moves': moves  # Moves count
                }

                return
            try:
                row, col = parse_coordinate(guess)
                result, sunk_name = p["board"].fire_at(row, col)
                moves[current] += 1

                if result == 'hit':
                    if sunk_name:
                        hit_message = f"HIT! {p['name']} sank the {sunk_name}!"
                        send(p["w"], hit_message)
                        send(opponent["w"], f"{p['name']} sank your {sunk_name}!")
                    else:
                        hit_message = "HIT!"
                        send(p["w"], hit_message)
                        send(opponent["w"], f"{p['name']} hit one of your ships!")
                    
                    broadcast_game_state_to_spectators(players, hit_message, broadcast_callback)

                    if p["board"].all_ships_sunk():
                        send(p["w"], f"Congratulations! You sank all ships in {moves[current]} moves.")
                        send(opponent["w"], "All your ships are sunk. You lose.")

                        # Send final boards to both players
                        send_board(p["w"], p["board"])
                        send_board(opponent["w"], opponent["board"])

                        broadcast_game_state_to_spectators(players, "Game over. All ships have been sunk!", broadcast_callback)
                        
                        game_data = {
                            'board1': p["board"],  # Player 1's board
                            'board2': opponent["board"],  # Player 2's board
                            'turn': current,  # Current player turn
                            'moves': moves  # Moves count
                        }

                        return # Ends the game if all ships are sunk
                    
                elif result == 'miss':
                    miss_message = "MISS!"
                    send(p["w"], miss_message)
                    send(opponent["w"], f"{p['name']} missed.")
                    broadcast_game_state_to_spectators(players, miss_message, broadcast_callback)

                elif result == 'already_shot':
                    send(p["w"], "You've already fired at that location. Try again.")
                    continue # Lets the player try again
                
                break
            except ValueError as e:
                send(p["w"], f"Invalid input: {e}")
        
        game_data = {
                    'board1': board1,
                    'board2': board2,
                    'turn': 1 - current,
                    'moves': {'Player 1': moves[0], 'Player 2': moves[1]}
                }
        save_state_callback(player1_id, player2_id, game_data)
    
        current = 1 - current  # Switches turns after each valid shot

def main():
    while True:
        run_single_player_game_locally()
        
        response = input("Play again? (yes/no): ").strip().lower()
        if response != 'yes':
            print("Thanks for playing!")
            break


if __name__ == "__main__":
    # Optional: run this file as a script to test single-player mode
    main()
