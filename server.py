import socket
from battleship import run_two_player_game_online, send, recv
import threading
import time
import uuid
import json
import os
import shutil

HOST = '127.0.0.1'
PORT = 5000
RECONNECT_TIMEOUT = 60

lobby = []  # List to hold players waiting for a game
spectators = [] # List to hold spectators
active_clients = {}
disconnected_clients = {}  # Store temporarily disconnected clients
games = {}
lobby_lock = threading.Lock()  # Ensure only one thread accesses the lobby at a time
game_lock = threading.Lock()  # Ensure only one active game at a time
client_lock = threading.Lock()

def cleanup_expired_clients():
    now = time.time()
    expired = [cid for cid, data in active_clients.items()
               if now - data['timestamp'] > RECONNECT_TIMEOUT]
    for cid in expired:
        del active_clients[cid]

def cleanup_client_ids_folder():
    if os.path.exists("client_ids"):
        shutil.rmtree("client_ids")
        print("[INFO] Cleared all client ID files.")

def wait_for_reconnect(client_id, opponent_data):
    print(f"[INFO] Waiting for {client_id} to reconnect...")
    start_time = time.time()
    while time.time() - start_time < RECONNECT_TIMEOUT:
        cleanup_expired_clients()
        if client_id in active_clients:
            print(f"[INFO] {client_id} reconnected.")
            return active_clients[client_id]['conn_data']
        time.sleep(1)
    print(f"[ERROR] {client_id} failed to reconnect.")
    return None

def handle_clients(player1, player2):
    """
    Handles the game between two connected players.
    Ends the game if a client disconnects.
    """
    with game_lock:  # aquire lock to ensure one game at a time
        print("[INFO] Starting two-player game...")

        conn1, rfile1, wfile1, client_id1 = player1
        conn2, rfile2, wfile2, client_id2 = player2

        with client_lock:
            games[client_id1] = (client_id2, player1)
            games[client_id2] = (client_id1, player2)

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
            disconnected, other = (client_id1, player2) if not conn1.fileno() else (client_id2, player1)
            other_conn, other_rfile, other_wfile, other_id = other

            send(other_wfile, "[INFO] Opponent disconnected. Waiting for reconnection...")

            with client_lock:
                disconnected_clients[disconnected] = {
                    "timestamp": time.time(),
                    "opponent": other_id,
                    "player_data": player1 if disconnected == client_id1 else player2
                }

            new_conn_data = wait_for_reconnect(disconnected, other)
            if new_conn_data:
                new_conn, new_rfile, new_wfile, _ = new_conn_data
                if disconnected == client_id1:
                    conn1, rfile1, wfile1 = new_conn, new_rfile, new_wfile
                    player1 = (conn1, rfile1, wfile1, client_id1)
                else:
                    conn2, rfile2, wfile2 = new_conn, new_rfile, new_wfile
                    player2 = (conn2, rfile2, wfile2, client_id2)

                send(new_wfile, "[INFO] Reconnected. Resuming game...")
                send(other_wfile, "[INFO] Opponent reconnected. Resuming game...")
                handle_clients(player1, player2)  # resume game
                return

        finally:
            # Always clean up sockets and files
            for conn, rfile, wfile, cid in [player1, player2]:
                try: rfile.close()
                except: pass
                try: wfile.close()
                except: pass
                try: conn.close()
                except: pass
                with client_lock:
                    active_clients.pop(cid, None)
                    disconnected_clients.pop(cid, None)
                    games.pop(cid, None)
            print("[INFO] Game session closed.")
    launch_game_if_ready()


def broadcast_to_spectators(game_state):
    """
    Sends the current game state to all connected spectators.
    """
    with lobby_lock:
        for conn, rfile, wfile, client_id in spectators[:]:
            try:
                send(wfile, f"[SPECTATOR] Game state update:\n{game_state}")
            except:
                # Remove disconnected spectators
                spectators.remove((conn, rfile, wfile, client_id))


def handle_spectator_input(rfile, wfile, client_id):
    """
    Handles input from spectators. Any input is ignored or produces an error message.
    """
    try:
        while True:
            command = rfile.readline().strip()
            if command:
                send(wfile, "[ERROR] Spectators cannot issue commands.")
    except:
        pass


def lobby_manager(conn, addr):
    """
    Manages lobby for players waiting to join a game. 
    """
    print(f"[INFO] New client connected from {addr}")
    rfile = conn.makefile('r')
    wfile = conn.makefile('w')

    client_id = recv(rfile).strip()

    if not client_id:
        client_id = str(uuid.uuid4())
        send(wfile, client_id)
    else:
        print("client_id", client_id)
        send(wfile, client_id)

    with client_lock:
        cleanup_expired_clients()
        conn_data = (conn, rfile, wfile, client_id)
        active_clients[client_id] = {
            "timestamp": time.time(),
            "conn_data": conn_data
        }

        if client_id in disconnected_clients:
            game_data = disconnected_clients.pop(client_id)
            active_clients[client_id]["conn_data"] = conn_data
            print(f"[INFO] Client {client_id} attempting reconnection")
            wait_for_reconnect(client_id, game_data)
            return  # wait_for_reconnect will handle resumption

    with lobby_lock: 
        if len(lobby) < 2 and not game_lock.locked():
            lobby.append((conn, rfile, wfile, client_id))
            send(wfile, "[INFO] You are in the lobby")

        else:
            spectators.append((conn, rfile, wfile, client_id))
            send(wfile, "[INFO] Lobby is full. You are now a spectator.")

            # Start a thread to handle spectator input (ignored or produces an error)
            threading.Thread(target=handle_spectator_input, args=(rfile, wfile, client_id), daemon=True).start()
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
                cleanup_client_ids_folder()
                break 

if __name__ == "__main__":
    main()
