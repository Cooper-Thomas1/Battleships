# Battleships Project 

## Task 1 - Basic 2-Player Game with Concurrency in BEER     
Task 1-1:    
For task 1-1 we worked within the client.py file and implemented threading in order to address the issue with message synchronization. We identified the source of error as a lack of concurrency where the client reads one message from the 
server, then waits for user input, then reads the next message from the server. To resolve the issue we made use of multithreading to create a thread designated to continuously read and display server messages while the main thread handles user input and sending commands. Furthermore, we tried to increase modularity and clarity by spearating the client files functionality into two functions; main and receive_messages which is called in main to continuosly read and display messages.

Task 1-2:   
For task 1-2 we worked within the server.py file and improved the functioanality of the server to be able to accept two connections. The problem with the original functioanlity is that it didn't have the capacity to deal with more than one client accessing the server. To address this we added a while loop where each client (player) has their own rfile and wfile made, after this, we use concurrency to have a thread running for both clients (players)> We also looked to increase the modularity of the server by designing a function called handle_clients which deals specifically with calling the battleship game implementation and closing the threads once the game finishes.

Task 1-3:  
For task 1-3 we worked predominantly within the battleship.py file and implemented the run_two_player_game_online as called in the server file. For this function we tried to use the same style for our implementation of run_two_player_game_online as run_single_player_game_locally used so we maintained consistency in the codebase (i.e. using the same send, send_board and recv functions). For the actual high-level battleship mechanics, we based it off the single player implementation and simply added in a break statement when the all_ships_sunk function returned true. After the while loop was broken the program flow returns back to the server file where the corresponding sockets associated with each player are closed.

Task 1-4:  
For task 1-4, we similarly maintained the same coding conventions with our client/server messages by making use of the send function to write messages and the recv function to read messages between the server and the client (As provided in the run_single_player_game_online function). 

Task 1-5:   
For task 1-5, as our server file closes the sockets associated with each player once the game is won or a player disconnects and this functionality is already discussed in task 1-3.

# TO DO    
## Task 2 - Gameplay Quality-of-Life & Scalability     
Task 2-1:   
...
