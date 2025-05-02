# Computer Networks Project - Battleships
## Task   
We have been hired by Socket & Sunk to develop a networked, turn-based Battleship game named “Battleships: Engage in Explosive Rivalry”, or simply BEER. Although an early prototype exists for the client, the overall project lacks a functioning multiplayer server to orchestrate real-time gameplay across multiple connections.    

Our job is to fix these problems and develop a properly functioning multiplayer server.

## How to run   
To play a local single player battleship game using our code:     
run ```python3 battleship.py```   

To play an online two player battleship game using our code:    
run ```python3 server.py``` in one terminal, open another terminal and run ```python3 client.py``` and then open a third terminal and run ```python3 client.py```.

## Possible battleship inspo     
https://github.com/Klavionik/battleship-tui/blob/main/battleship/server/auth.py      
https://github.com/ronmelcuba10/python-online-multiplayer-battleship/blob/master/server.py    
https://github.com/harshsodi/battleship/blob/master/server.py    
https://github.com/jvillegasd/battleship-go/blob/master/networking/server.py   

## Directory Structure
```
BEER/
│
├── battleship.py
├── client.py
├── server.py
```
