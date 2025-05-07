import socket
from battleship import run_two_player_game_online, send, recv
import threading
import time
import uuid

HOST = '127.0.0.1'
PORT = 5000
RECONNECT_TIMEOUT = 60  # 60 seconds for reconnection window

lobby = []  # List to hold players waiting for a game
spectators = [] # List to hold spectators
active_players = {}  # Dictionary to store active players' details (ID, username, still_active)
game_states = {}
lobby_lock = threading.Lock()  # Ensure only one thread accesses the lobby at a time
game_lock = threading.Lock()  # Ensure only one active game at a time

def save_game_state(player1_id, player2_id, game_data):
    """
    Saves the game state for a match (e.g., game boards, turn information).
    """
    game_states[player1_id] = game_data
    game_states[player2_id] = game_data

def handle_reconnection(conn, rfile, wfile, player_id, username):
    """
    Allows a player to reconnect to their previous game if it exists and they are still within the reconnection window.
    """
    with lobby_lock:
        player = active_players.get(player_id)
        if player and not player['still_active']:
            last_disconnect_time = player['disconnect_time']
            if time.time() - last_disconnect_time <= RECONNECT_TIMEOUT:
                # Player is eligible to reconnect
                active_players[player_id]['still_active'] = True

                # Dummy boards (e.g., 5x5 grid with '~' for water)
                dummy_board = [['~' for _ in range(5)] for _ in range(5)]

                # Check if there's a saved game state for this player
                game_state = game_states.get(player_id, {})
                board1 = game_state.get('board1', dummy_board)
                board2 = game_state.get('board2', dummy_board)
                turn = game_state.get('turn', 1)

                send(wfile, "[INFO] Reconnection successful. Resuming your previous game.")
                send(wfile, "[INFO] Game state restored.")
                send(wfile, f"[INFO] Board 1: {board1}")
                send(wfile, f"[INFO] Board 2: {board2}")
                send(wfile, f"[INFO] It's player {turn}'s turn.")

                return True
    return False

def handle_clients(player1, player2):
    """
    Handles the game between two connected players.
    Ends the game if a client disconnects.
    """
    with game_lock:  # aquire lock to ensure one game at a time
        print("[INFO] Starting two-player game...")

        conn1, rfile1, wfile1, player1_id, username1 = player1
        conn2, rfile2, wfile2, player2_id, username2 = player2

        active_players[player1_id] = {'username': username1, 'still_active': True, 'disconnect_time': None}
        active_players[player2_id] = {'username': username2, 'still_active': True, 'disconnect_time': None}

        player1_board = []  # Replace with actual initialization logic for player 1's board
        player2_board = []  # Replace with actual initialization logic for player 2's board
        turn = 1  # Player 1 starts

        game_data = {
            'board1': player1_board,  # Player 1's board
            'board2': player2_board,  # Player 2's board
            'turn': turn,  # Whose turn it is
        }

        save_game_state(player1_id, player2_id, game_data)

        try:
            while True:
                run_two_player_game_online((rfile1, wfile1), (rfile2, wfile2), broadcast_to_spectators)

                send(wfile1, "[INFO] Game over. Do you want to play again? (yes/no)")
                send(wfile2, "[INFO] Game over. Do you want to play again? (yes/no)")

                response1 = recv(rfile1).strip().lower()
                response2 = recv(rfile2).strip().lower()

                if response1 != "yes" or response2 != "yes":
                    send(wfile1, "[INFO] Game ended. Thanks for playing!")
                    send(wfile2, "[INFO] Game ended. Thanks for playing!")
                    break

        except (ConnectionResetError, BrokenPipeError, OSError):
            print("[WARNING] A player disconnected unexpectedly. Ending game.")

            # Mark the disconnected player as inactive
            active_players[player1_id]['still_active'] = False
            active_players[player2_id]['still_active'] = True

            disconnect_time = time.time()
            active_players[player1_id]['disconnect_time'] = disconnect_time
            active_players[player2_id]['disconnect_time'] = None

            time.sleep(RECONNECT_TIMEOUT)

            if not active_players[player1_id]['still_active']:
                send(wfile2, "[INFO] Player1 didn't reconnect in time. You win!")
                send(wfile1, "[INFO] You lost the game as your opponent did not reconnect in time.")
            
            send(wfile1, "[INFO] Game over.")
            send(wfile2, "[INFO] Game over.")

            try:
                send(wfile1, "[ERROR] Opponent disconnected. Game over.")
            except:
                pass
            try:
                send(wfile2, "[ERROR] Opponent disconnected. Game over.")
            except:
                pass

        finally:
            # Always clean up sockets and files
            for conn, rfile, wfile, player_id, _ in [player1, player2]:
                try: rfile.close()
                except: pass
                try: wfile.close()
                except: pass
                try: conn.close()
                except: pass
            print("[INFO] Game session closed.") # current game ends, but server continues to run
        
        # release lock automatically (to let a new game start)

    # try launching next game if enough players are waiting
    launch_game_if_ready()


def broadcast_to_spectators(game_state):
    """
    Sends the current game state to all connected spectators.
    """
    with lobby_lock:
        for conn, rfile, wfile in spectators:
            try:
                send(wfile, f"[SPECTATOR] Game state update:\n{game_state}")
            except:
                # Remove disconnected spectators
                spectators.remove((conn, rfile, wfile))


def handle_spectator_input(rfile, wfile):
    """
    Handles input from spectators. Any input is ignored or produces an error message.
    """
    try:
        while True:
            command = rfile.readline().strip()
            if command:
                send(wfile, "[ERROR] Spectators cannot issue commands.")
    except Exception:
        pass


def lobby_manager(conn, addr):
    """
    Manages lobby for players waiting to join a game. 
    """
    print(f"[INFO] New client connected from {addr}")
    rfile = conn.makefile('r')
    wfile = conn.makefile('w')

    player_id = str(uuid.uuid4())  # Generate a unique ID using UUID
    send(wfile, "[INFO] Welcome! Please enter your username:")
    username = recv(rfile).strip()

    # Handle reconnecting players
    send(wfile, "[INFO] Checking for any ongoing games...")
    player_reconnected = False
    for player_id in active_players:
        if handle_reconnection(conn, rfile, wfile, player_id, username):
            player_reconnected = True
            break
    
    if not player_reconnected:
        with lobby_lock: 
            if len(lobby) < 2 and not game_lock.locked():
                lobby.append((conn, rfile, wfile, player_id, username))
                send(wfile, "[INFO] You are in the lobby")

            else:
                spectators.append((conn, rfile, wfile, player_id, username))
                send(wfile, "[INFO] Lobby is full. You are now a spectator.")

                # Start a thread to handle spectator input (ignored or produces an error)
                threading.Thread(target=handle_spectator_input, args=(rfile, wfile), daemon=True).start()

    # Try to start a new game if possible
    launch_game_if_ready()

def launch_game_if_ready():
    with lobby_lock:
        if len(lobby) >= 2 and not game_lock.locked():
            player1 = lobby.pop(0)
            player2 = lobby.pop(0)
            threading.Thread(target=handle_clients, args=(player1, player2), daemon=True).start()
            
def main():
    """
    Continuously accepts clients and assigns them into games.
    """
    print(f"[INFO] Server listening on {HOST}:{PORT}")
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((HOST, PORT))
        s.listen() # continuously listen for new connections (rm backlog=2)

        while True:
            try:
                conn, addr = s.accept()
                threading.Thread(target=lobby_manager, args=(conn, addr), daemon=True).start()
            except KeyboardInterrupt:
                print("\n[INFO] Server shutting down.")
                break

if __name__ == "__main__":
    main()
