import socket
from battleship import run_two_player_game_online, send, recv
import threading

HOST = '127.0.0.1'
PORT = 5000

lobby = []  # List to hold players waiting for a game
spectators = [] # List to hold spectators
lobby_lock = threading.Lock()  # Ensure only one thread accesses the lobby at a time
game_lock = threading.Lock()  # Ensure only one active game at a time

def handle_clients(player1, player2):
    """
    Handles the game between two connected players.
    Ends the game if a client disconnects.
    """
    with game_lock:  # aquire lock to ensure one game at a time
        print("[INFO] Starting two-player game...")

        conn1, rfile1, wfile1 = player1
        conn2, rfile2, wfile2 = player2

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
            for conn, rfile, wfile in [player1, player2]:
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


def lobby_manager(conn, addr):
    """
    Manages lobby for players waiting to join a game. 
    """
    print(f"[INFO] New client connected from {addr}")
    rfile = conn.makefile('r')
    wfile = conn.makefile('w')

    with lobby_lock: 
        if len(lobby) < 2 and not game_lock.locked():
            lobby.append((conn, rfile, wfile))
            send(wfile, "[INFO] You are in the lobby")

        else:
            spectators.append((conn, rfile, wfile))
            send(wfile, "[INFO] Lobby is full. You are now a spectator.")

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
