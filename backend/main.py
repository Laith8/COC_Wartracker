import dotenv, os
dotenv.load_dotenv('./backend/.env')
from fastapi import FastAPI
from coc_client import ClashClient
from database import Base, engine, init_db
from models import Clan, Player, PlayerClanHistory, War, WarParticipant, Attack
from contextlib import asynccontextmanager
import asyncio
from refresh import refresh_loop
from db_client import DbClient

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    task = asyncio.create_task(refresh_loop())
    yield
    task.cancel()

app = FastAPI(lifespan=lifespan)

client = ClashClient()

@app.get('/clans')
async def read_clans():
    dbclient = DbClient()
    response = await dbclient.get_tracked_clans()
    return response

@app.get('/test/addmyclan')
async def test_add():
    dbclient = DbClient()
    await dbclient.upsert_clan('#2JV9LCUVC','urgeschichte',True)

@app.get("/members")
async def read_members():
    response = await client.get_members('#2JV9LCUVC')
    return response

@app.get("/")
@app.get("/dashboard")
async def read_dashboard():
    response = await client.get_members('#2JV9LCUVC')
    members = {
        item["name"]: item["role"]
        for item in response["items"]
    }

    return members

@app.get("/items/{item_id}")
def read_item(item_id: int, q: str | None = None):
    return {"item_id": item_id, "q": q}
