import socket
from battleship import run_two_player_game_online, send, recv
import threading

HOST = '127.0.0.1'
PORT = 5000

def handle_clients(player1, player2):
    """
    Handles the game between two connected players.
    Each player is a tuple of (conn, rfile, wfile).

    Modified to handle repeat games
    """
    print("[INFO] Starting two-player game...")

    # Extract readable/writable file objects
    rfile1, wfile1 = player1[1], player1[2]
    rfile2, wfile2 = player2[1], player2[2]

    while True:
        run_two_player_game_online((rfile1, wfile1), (rfile2, wfile2))

        # Ask if they want to play again
        send(wfile1, "[INFO] Game over. Do you want to play again? (yes/no)")
        send(wfile2, "[INFO] Game over. Do you want to play again? (yes/no)")

        response1 = recv(rfile1).strip().lower()
        response2 = recv(rfile2).strip().lower()

        if response1 != "yes" or response2 != "yes":
            send(wfile1, "[INFO] Game ended. Thanks for playing!")
            send(wfile2, "[INFO] Game ended. Thanks for playing!")

            player1[0].close()
            player2[0].close()

            print("[INFO] Players disconnected.")
            break

def main():
    """
    Accepts exactly two clients, then starts the game.
    """
    print(f"[INFO] Server listening on {HOST}:{PORT}")
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((HOST, PORT))
        s.listen(2)

        players = []

        while len(players) < 2:
            conn, addr = s.accept()
            print(f"[INFO] Player {len(players) + 1} connected from {addr}")
            rfile = conn.makefile('r')
            wfile = conn.makefile('w')
            players.append((conn, rfile, wfile))

        # Start game in a separate thread (optional, makes future expansion easier)
        threading.Thread(target=handle_clients, args=(players[0], players[1])).start()

if __name__ == "__main__":
    main()
