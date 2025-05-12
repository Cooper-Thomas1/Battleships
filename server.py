import socket
from battleship import run_two_player_game_online, send, recv
import threading
import time

HOST = '127.0.0.1'
PORT = 5000
RECONNECT_TIMEOUT = 60  # 60 seconds for reconnection window

lobby = []  # List to hold players waiting for a game
active_players = {}  # Dictionary to store active players' details (ID, username, still_active)
game_states = {}
current_match = {}    # username -> (player1_tuple, player2_tuple)

lobby_lock = threading.Lock()  # Ensure only one thread accesses the lobby at a time
game_lock = threading.Lock()  # Ensure only one active game at a time

spectator_threads = {}


def save_game_state(p1, p2, game_data):
    """Called by battleship after each turn to persist state."""
    game_states[p1] = game_data
    game_states[p2] = game_data


def handle_reconnection(player):
    """
    Allows a player to reconnect to their previous game if it exists and they are still within the reconnection window.
    """
    conn1, rfile1, wfile1, username1 = player

    with lobby_lock:
        player = active_players.get(username1, None)
        if player and not player['still_active']:
            last_disconnect_time = player['disconnect_time']
            if time.time() - last_disconnect_time <= RECONNECT_TIMEOUT:
                active_players[username1]['still_active'] = True
                send(wfile1, "[INFO] Reconnection successful. Restoring your game state...")
                return True  
    return False


def handle_clients(player1, player2):
    """
    Handles the game between two connected players.
    Ends the game if a client disconnects.
    """
    print("[INFO] LET'S PLAY!")

    with game_lock:  # aquire lock to ensure one game at a time
        conn1, rfile1, wfile1, username1 = player1
        conn2, rfile2, wfile2, username2 = player2
        
        did_resume = False

        current_match[username1] = (player1, player2)
        current_match[username2] = (player1, player2)

        active_players[username1] = {'still_active': True, 'disconnect_time': None}
        active_players[username2] = {'still_active': True, 'disconnect_time': None}

        initial_state = game_states.get(username1)
      
        try:
            while True:
                run_two_player_game_online((rfile1, wfile1), (rfile2, wfile2), broadcast_to_spectators, save_game_state,
                username1, username2, initial_state=initial_state)

                send(wfile1, "[INFO] Game over. Do you want to play again? (yes/no)")
                send(wfile2, "[INFO] Game over. Do you want to play again? (yes/no)")

                response1 = recv(rfile1).strip().lower()
                response2 = recv(rfile2).strip().lower()

                if response1 == "yes" and response2 == "yes":
                    send(wfile1, "[INFO] Game ended. Thanks for playing!")
                    send(wfile2, "[INFO] Game ended. Thanks for playing!")
                    game_states.pop(username1, None)
                    game_states.pop(username2, None)
                    continue
                else:
                    send(wfile1, "[INFO] Game ended. Returning to lobby." if response1 == "yes" else "[INFO] Goodbye!")
                    send(wfile2, "[INFO] Game ended. Returning to lobby." if response2 == "yes" else "[INFO] Goodbye!")

                    # Re-add players who want to play again to the lobby
                    with lobby_lock:
                        if response1 == "yes":
                            lobby.append(player1)
                        if response2 == "yes":
                            lobby.append(player2)
                    break

        except (KeyboardInterrupt, ConnectionResetError, BrokenPipeError, OSError):
            print("[WARNING] A player disconnected unexpectedly. Handling disconnection...")
            disconnected, opponent = None, None

            try:
                send(wfile1, "[PING]")
                player1_connected = True
            except:
                player1_connected = False

            try:
                send(wfile2, "[PING]")
                player2_connected = True
            except:
                player2_connected = False

            if not player1_connected:
                disconnected, opponent = username1, (conn2, rfile2, wfile2, username2)
            else:
                disconnected, opponent = username2, (conn1, rfile1, wfile1, username1)

            active_players[disconnected]['still_active'] = False
            active_players[disconnected]['disconnect_time'] = time.time()

            for _ in range(RECONNECT_TIMEOUT):
                time.sleep(1)
                if active_players[disconnected]['still_active']:
                    print(f"[INFO] {disconnected} has reconnected. Resuming game.")
                    did_resume = True
                    re_p1, re_p2 = current_match[disconnected]
                    # Determine which I/O tuple belongs to reconnecting player
                    if re_p1[3] == disconnected:
                        player1, player2 = (rfile1, wfile1), (rfile2, wfile2)
                    else:
                        player1, player2 = (rfile2, wfile2), (rfile1, wfile1)

                    run_two_player_game_online(player1, player2, broadcast_to_spectators, save_game_state, 
                                               username1, username2,
                                               initial_state=game_states.get(disconnected))
                    break

            print(f"[INFO] {disconnected} failed to reconnect. {opponent[3]} wins by default.")
            send(opponent[2], f"[INFO] {disconnected} failed to reconnect in time. You win!")

        finally:
            if not did_resume:
                for p in (player1, player2):
                    conn  = p[0]
                    rfile = p[1] if len(p) > 1 else None
                    wfile = p[2] if len(p) > 2 else None

                    if rfile:
                        try: rfile.close()
                        except: pass
                    if wfile:
                        try: wfile.close()
                        except: pass
                    try:
                        conn.close()
                    except:
                        pass
                active_players.pop(username1, None)
                active_players.pop(username2, None)
                game_states.pop(username1, None)
                game_states.pop(username2, None)

    launch_game_if_ready()


def broadcast_to_spectators(game_state):
    """
    Sends the current game state to all connected spectators.
    """
    with lobby_lock:
        for entry in list(lobby):
            conn, rfile, wfile, user = entry
            try:
                send(wfile, f"[SPECTATOR] Game state update:\n{game_state}")
            except:
                lobby.remove(entry)


def handle_spectator_input(rfile, wfile, stop_event):
    """
    Handles input from spectators. Any input is ignored or produces an error message.
    """
    try:
        send(wfile, "[SPECTATOR] You are in the lobby. Waiting for your turn...\n")
        while not stop_event.is_set():  # Stop when the event is set
            time.sleep(1)
    except Exception as e:
        print(f"[ERROR] Spectator input error: {e}")

def stop_spectator_thread(username):
    """
    Signals the spectator thread to stop so it doesn't continue processing input.
    """
    if username in spectator_threads:
        spectator_threads[username].set()  # Signal to stop the spectator thread
        spectator_threads.pop(username)


def lobby_manager(conn, addr):
    """
    Manages lobby for players waiting to join a game. 
    """
    print(f"[INFO] New client connected from {addr}")
    rfile = conn.makefile('r')
    wfile = conn.makefile('w')

    while True:
        send(wfile, "[INFO] Welcome! Please enter your username:")
        username = recv(rfile).strip()

        if any(username == entry[3] for entry in lobby) or username in active_players:
            send(wfile, "[ERROR] This username is already taken. Please choose a different one.")
        else:
            break

    # Handle reconnecting players
    send(wfile, "[INFO] Checking for any ongoing games...")
    if username in active_players and not active_players[username]['still_active'] and game_lock.locked():
        if username not in game_states:
            send(wfile, "[INFO] Your previous game has already ended. You will return to the lobby.")
        
        else:
            print(f"[INFO] {username} attempting to reconnect...")
            active_players[username]['still_active'] = True
            p1, p2 = current_match[username]

            # determine which tuple is theirs
            if p1[3] == username:
                resume_self, resume_opp = (conn, rfile, wfile, username), p2
            else:
                resume_self, resume_opp = (conn, rfile, wfile, username), p1

            send(wfile, "[INFO] Reconnected! Waiting for game to resume...")
            threading.Thread(target=run_two_player_game_online,
                args=((resume_self[1], resume_self[2]), (resume_opp[1], resume_opp[2]),
                    broadcast_to_spectators,
                    save_game_state,
                    p1[3], p2[3]
                ),
                kwargs={'initial_state': game_states.get(username)},
                daemon=True
            ).start()
            return
        
   
    with lobby_lock: 
        if len(lobby) < 2 and not game_lock.locked():
            send(wfile, "[INFO] You are in the lobby")
            lobby.append((conn, rfile, wfile, username))
        else:
            send(wfile, "[INFO] Game is full. You are now a spectator.")
            stop_event = threading.Event()
            spectator_threads[username] = stop_event
            lobby.append((conn, rfile, wfile, username))
            threading.Thread(target=handle_spectator_input, args=(rfile, wfile, stop_event), daemon=True).start()
    launch_game_if_ready()


def launch_game_if_ready():
    with lobby_lock:
        if len(lobby) >= 2 and not game_lock.locked():
            player1 = lobby.pop(0)
            player2 = lobby.pop(0)

            for entry in [player1, player2]:
                conn, rfile, wfile, user = entry
                send(wfile, f"[INFO] {player1[3]} and {player2[3]} will be playing the next game!")

            stop_spectator_thread(player1[3])
            stop_spectator_thread(player2[3])

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
