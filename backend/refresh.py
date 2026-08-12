import asyncio
from coc_client import ClashClient
from db_client import DbClient
import os
from models import utcnow, WarType, WarResult
from datetime import datetime, timezone

def get_hero_level(player_data: dict, hero_name: str) -> int | None:
    for hero in player_data.get("heroes", []):
        if hero["name"] == hero_name:
            return hero["level"]

    return 0 # as in level 0, not unlocked

def parse_coc_datetime(value: str) -> datetime:
    return datetime.strptime(
        value,
        "%Y%m%dT%H%M%S.%fZ",
    ).replace(tzinfo=timezone.utc)

async def refresh():
    cclient = ClashClient()
    dbclient = DbClient()
    tracked_clandata = [
        {'id':i.id,
        'tag':i.tag}
        for i in await dbclient.get_tracked_clans()
    ]
    if len(tracked_clandata) < 1:
        return
    tracked_clantags = [i['tag'] for i in tracked_clandata]
    clanslistwithmembers = await (
        asyncio.gather(
            *[cclient.get_members(tag) for tag in tracked_clantags]
        )
    )
    playertags = []
    for i in clanslistwithmembers:
        for j in i['items']:
            playertags.append(j['tag'])
    playerdata = await (
        asyncio.gather(
            *[cclient.get_player(tag) for tag in playertags]
        )
    )
    for i in playerdata:
        await dbclient.upsert_player(
            tag=i['tag'],
            name=i['name'],
            town_hall=i['townHallLevel'],
            clan_tag=i['clan']['tag'],
            king=get_hero_level(i,'Barbarian King'),
            queen=get_hero_level(i,'Archer Queen'),
            minion=get_hero_level(i, 'Minion Prince'),
            warden=get_hero_level(i, 'Grand Warden'),
            champion=get_hero_level(i, 'Royal Champion'),
            duke=get_hero_level(i, 'Dragon Duke')
        )
    wardata = await asyncio.gather(*[cclient.get_wardata(tag) for tag in tracked_clantags])
    for war in wardata:
        await dbclient.upsert_clan(
            tag=war['opponent']['tag'],
            name=war['opponent']['name'],
        )
        war_instance = await dbclient.upsert_war(
            our_clan_tag=war['clan']['tag'],
            enemy_clan_tag=war['opponent']['tag'],
            end_time=parse_coc_datetime(war['endTime']),
            start_time=parse_coc_datetime(war['startTime']),
            war_type=WarType.RANDOM,
            size=war['teamSize'],
            result=WarResult.PENDING if war['state'] in ('preparation', 'inMatchmaking', 'war', 'inWar', 'matched') else WarResult.ENDED_UNKNOWN,
        )
        enemy_playertags = [player['tag'] for player in (await cclient.get_members(war['opponent']['tag']))['items']]
        enemy_playerdata = [await cclient.get_player(tag) for tag in enemy_playertags]
        for i in enemy_playerdata:
            await dbclient.upsert_player(
                tag=i['tag'],
                name=i['name'],
                town_hall=i['townHallLevel'],
                clan_tag=i['clan']['tag'],
                king=get_hero_level(i,'Barbarian King'),
                queen=get_hero_level(i,'Archer Queen'),
                minion=get_hero_level(i, 'Minion Prince'),
                warden=get_hero_level(i, 'Grand Warden'),
                champion=get_hero_level(i, 'Royal Champion'),
                duke=get_hero_level(i, 'Dragon Duke')
            )
        attacks = []
        for participant in war['opponent']['members']:
            participant_instance = await dbclient.upsert_war_participant(
                war_id=war_instance.id,
                player_tag=participant['tag'],
                clan_tag=war['opponent']['tag'],
                map_position=participant['mapPosition'],
                town_hall=participant['townhallLevel'],
                attacks_allowed=war['attacksPerMember']
            )
        for participant in war['clan']['members']:
            participant_instance = await dbclient.upsert_war_participant(
                war_id=war_instance.id,
                player_tag=participant['tag'],
                clan_tag=war['clan']['tag'],
                map_position=participant['mapPosition'],
                town_hall=participant['townhallLevel'],
                attacks_allowed=war['attacksPerMember']
            )
        for participant in [*war['clan']['members'], *war['opponent']['members']]:
            attacks = participant.get('attacks')
            if not attacks:
                continue
            for i in attacks:
                await dbclient.upsert_attack(
                    war_id=war_instance.id,
                    attacker_id=i['attackerTag'],
                    defender_id=i['defenderTag'],
                    attack_number=i['order'],
                    stars=i['stars'],
                    destruction=i['destructionPercentage'],
                    fresh_hit=True if i['order'] == 1 else False,
                    cleanup=True if i['order'] > 1 else False,
                    attack_time=i['duration'],
                )
    return

async def refresh_loop():
    try:
        while True:
            await asyncio.sleep(5)
            print('start refresh')
            await refresh()
            print('finish refresh')
            await asyncio.sleep(60)
    except asyncio.CancelledError:
        print("Stopping refresh loop...")
        raise