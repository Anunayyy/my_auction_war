import asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from upstash_redis import Redis

# Use your actual keys here
REDIS_URL = "https://prime-wildcat-14619.upstash.io"
REDIS_TOKEN = "ATkbAAIncDI5ZmE4Yjk5ZTVhYTk0OWQyYmE0NmRiOWQ0OTU4NjlhOHAyMTQ2MTk"
redis = Redis(url=REDIS_URL, token=REDIS_TOKEN)

app = FastAPI()

class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            try: await connection.send_text(message)
            except: pass

manager = ConnectionManager()
auction_timer = 30 
is_auction_active = True

# THE HEARTBEAT: This runs in the background
async def run_countdown():
    global auction_timer, is_auction_active
    while True:
        await asyncio.sleep(1)
        if is_auction_active:
            auction_timer -= 1
            # We send "Time: XX" so the HTML knows it's a timer update
            await manager.broadcast(f"Time: {auction_timer}s")
            
            if auction_timer <= 0:
                is_auction_active = False
                await manager.broadcast("SOLD!")

@app.on_event("startup")
async def startup_event():
    # This starts the clock immediately when you run uvicorn
    asyncio.create_task(run_countdown())

@app.get("/")
async def get():
    with open("index.html") as f: return HTMLResponse(f.read())

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        # Get price from Redis or set to 100 if empty
        val = redis.get("auction_price")
        price = val if val else 100
        await websocket.send_text(f"Price: ${price}")
        
        while True:
            data = await websocket.receive_text()
            if data == "BID" and is_auction_active:
                global auction_timer
                new_price = redis.incrby("auction_price", 10)
                auction_timer = 10 # Reset clock to 10
                await manager.broadcast(f"Price: ${new_price}")
                await manager.broadcast("New Bid!")
    except WebSocketDisconnect:
        manager.disconnect(websocket)