import httpx
from urllib.parse import quote
from models import Clan, Player, PlayerClanHistory, War, WarParticipant, Attack
from sqlalchemy import select
from database import get_db, engine, SessionLocal
from sqlalchemy.orm import Session
import os
from db_client import DbClient

class ClashClient:
    def __init__(self):
        self.httpclient = httpx.AsyncClient(
            headers={
                "Authorization": f"Bearer {os.getenv('COC_API_TOKEN')}"
            }
        )

    @staticmethod
    def _request():
        pass


    async def get_clan(self, clan_tag):
        clan_tag = quote(clan_tag)
        url = f'https://api.clashofclans.com/v1/clans/{clan_tag}/'
        response = await self.httpclient.get(url)
        if response and response.status_code > 200:
            print('conn cl', response.status_code)
        return response.json()

    async def get_members(self, clan_tag):
        clan_tag = quote(clan_tag)
        url = f'https://api.clashofclans.com/v1/clans/{clan_tag}/members'
        response = await self.httpclient.get(url)
        if response and response.status_code > 200:
            print('conn mm', response.status_code)
        return response.json()

    async def get_player(self, tag):
        tag = quote(tag)
        url = f'https://api.clashofclans.com/v1/players/{tag}'
        response = await self.httpclient.get(url)
        if response and response.status_code > 200:
            print('conn pl', response.status_code)
        return response.json()

    async def get_wardata(self, clan_tag):
        clan_tag = quote(clan_tag)
        url = f'https://api.clashofclans.com/v1/clans/{clan_tag}/currentwar'
        response = await self.httpclient.get(url)
        return response.json()