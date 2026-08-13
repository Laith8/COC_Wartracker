from __future__ import annotations
from datetime import datetime, timezone
from models import WarResult, WarType
from dataclasses import dataclass
from urllib.parse import quote
import httpx, os, asyncio, time

def parse_coc_datetime(value: str) -> datetime:
    return datetime.strptime(
        value,
        "%Y%m%dT%H%M%S.%fZ",
    ).replace(tzinfo=timezone.utc)

@dataclass
class ClashClan:
    tag: str
    name: str
    player_tags: list[str]

    @classmethod
    def from_api(cls, data: dict) -> ClashClan:
        return cls(
            tag=data['tag'], 
            name=data['name'],
            player_tags = [
                player['tag']
                for player in data['memberList']
            ]
        )

@dataclass
class ClashPlayer:
    tag: str
    name: str
    town_hall: int
    clan_tag: str | None
    king: int = 0
    queen: int = 0
    minion: int = 0
    warden: int = 0
    champion: int = 0
    duke: int = 0

    @classmethod
    def from_api(cls, data: dict) -> ClashPlayer:
        heroes = {
            hero['name']: hero['level']
            for hero in data.get('heroes', [])
        }
        return cls(
            tag=data['tag'],
            name=data['name'],
            town_hall=data['townHallLevel'],
            clan_tag=((data.get('clan')['tag']) or None),
            king=heroes.get("Barbarian King", 0),
            queen=heroes.get("Archer Queen", 0),
            minion=heroes.get("Minion Prince", 0),
            warden=heroes.get("Grand Warden", 0),
            champion=heroes.get("Royal Champion", 0),
            duke=heroes.get("Dragon Duke", 0),
        )

@dataclass
class ClashWar:
    our_clan_tag: str
    enemy_clan_tag: str
    enemy_clan_name: str
    end_time: datetime
    start_time: datetime
    war_type: WarType
    size: int
    result: WarResult
    participants: list[ClashWarParticipant]

    @classmethod
    def from_api(cls, data: dict) -> ClashWar:
        our_participants = [
            ClashWarParticipant.from_api(participant, data['clan']['tag'])
            for participant in data['clan']['members']
        ]
        enemy_participants = [
            ClashWarParticipant.from_api(participant, data['opponent']['tag'])
            for participant in data['opponent']['members']
        ]
        return cls(
            our_clan_tag=data["clan"]["tag"],
            enemy_clan_tag=data["opponent"]["tag"],
            enemy_clan_name=data['opponent']['name'],
            end_time=parse_coc_datetime(data["endTime"]),
            start_time=parse_coc_datetime(data["startTime"]),
            war_type=WarType.RANDOM,
            size=data["teamSize"],
            result=WarResult.ENDED_UNKNOWN if data['state'] == 'ended' else WarResult.PENDING,
            participants=[*our_participants, *enemy_participants]
        )

@dataclass
class ClashAttack:
    attacker_tag: str
    defender_tag: str
    attack_number: int
    stars: int
    destruction: int
    fresh_hit: bool
    cleanup: bool
    attack_time: int

    @classmethod
    def from_api(cls, data: dict) -> ClashAttack:
        return cls(
            attacker_tag=data['attackerTag'],
            defender_tag=data['defenderTag'],
            attack_number=data['order'],
            stars=data['stars'],
            destruction=data['destructionPercentage'],
            fresh_hit=True if data['order'] == 1 else False,
            cleanup=True if data['order'] > 1 else False,
            attack_time=data['duration'],
        )

@dataclass
class ClashWarParticipant:
    player_tag: str
    map_position: int
    town_hall: int
    clan_tag: str
    attacks: list[ClashAttack]

    @classmethod
    def from_api(cls, data: dict, clan_tag: str) -> ClashWarParticipant:
        return cls(
            player_tag=data['tag'],
            map_position=data['mapPosition'],
            town_hall=data['townhallLevel'],
            clan_tag=clan_tag,
            attacks=[
                ClashAttack.from_api(attack)
                for attack in data.get("attacks", [])
            ],
        )

class RateLimitedClient:
    def __init__(
        self,
        calls_per_second: float = 9,
        max_concurrent: int = 5,
        client_options: dict | None = None
    ):
        if calls_per_second <= 0:
            raise ValueError("calls_per_second must be > 0")

        if max_concurrent <= 0:
            raise ValueError("max_concurrent must be > 0")

        self.client = httpx.AsyncClient(**(client_options or {}))

        self.interval = 1 / calls_per_second
        self.semaphore = asyncio.Semaphore(max_concurrent)

        self.last_call = 0.0
        self.rate_lock = asyncio.Lock()

    async def get(self, url: str) -> httpx.Response:
        async with self.semaphore:

            async with self.rate_lock:
                now = time.monotonic()

                wait = self.interval - (now - self.last_call)

                if wait > 0:
                    await asyncio.sleep(wait)

                self.last_call = time.monotonic()

            return await self.client.get(url)

    async def close(self):
        await self.client.aclose()

class ClashClient:
    def __init__(self):
        self.client = RateLimitedClient(
            client_options={
                "headers":{
                    "Authorization": f"Bearer {os.getenv('COC_API_TOKEN')}"
                }
            }
        )

    async def _request(self, url: str):
        response = await self.client.get(url)
        response.raise_for_status()
        return response.json()

    async def get_clan(self, clan_tag: str):
        url = f'https://api.clashofclans.com/v1/clans/{quote(clan_tag)}/'
        data = await self._request(url)
        return ClashClan.from_api(data)

    async def get_player(self, player_tag: str):
        url = f'https://api.clashofclans.com/v1/players/{quote(player_tag)}'
        data = await self._request(url)
        return ClashPlayer.from_api(data)

    async def get_war(self, clan_tag: str):
        url = f'https://api.clashofclans.com/v1/clans/{quote(clan_tag)}/currentwar'
        data = await self._request(url)
        return ClashWar.from_api(data)

    async def close(self):
        await self.client.close()