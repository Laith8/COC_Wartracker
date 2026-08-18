from coc_client import ClashClient
from db_client import DbClient
import os, httpx, sys, asyncio

async def refresh():
    cclient = ClashClient()
    dbclient = DbClient()

    tracked_clans = [
        clan.tag
        for clan in await dbclient.get_tracked_clans()
    ]
    if len(tracked_clans) < 1: return

    clansdata = await asyncio.gather(
        *[cclient.get_clan(tag) for tag in tracked_clans]
    )
    playertags = [
        playertag
        for clan in clansdata
        for playertag in clan.player_tags
    ]
    players = await asyncio.gather(
        *[cclient.get_player(tag) for tag in playertags]
    )
    await asyncio.gather(
        *[
            dbclient.upsert_player(
                tag=player.tag,
                name=player.name,
                town_hall=player.town_hall,
                clan_tag=player.clan_tag,
                king=player.king,
                queen=player.queen,
                minion=player.minion,
                warden=player.warden,
                champion=player.champion,
                duke=player.duke,
            )
            for player in players
        ]
    )
    wars = await asyncio.gather(*[cclient.get_war(tag) for tag in tracked_clans])

    enemy_clan_tags = [
        war.enemy_clan_tag
        for war in wars
    ]

    enemy_clandata = await asyncio.gather(
        *[cclient.get_clan(tag) for tag in enemy_clan_tags]
    )

    await asyncio.gather(*[
        dbclient.upsert_clan(
            tag=clan.tag,
            name=clan.name,
            badge_url=clan.badge_url,
            clan_level=clan.clan_level,
            war_wins=clan.war_wins,
            war_draws=clan.war_draws,
            war_losses=clan.war_losses,
        )
        for clan in enemy_clandata
    ])

    db_wars = await asyncio.gather(*[
        dbclient.upsert_war(
            our_clan_tag=war.our_clan_tag,
            enemy_clan_tag=war.enemy_clan_tag,
            end_time=war.end_time,
            start_time=war.start_time,
            war_type=war.war_type,
            size=war.size,
            result=war.result,
        )
        for war in wars
    ])

    enemy_playerdata = await asyncio.gather(*[
        cclient.get_player(participant.player_tag)
        for war in wars
        for participant in war.participants
        if participant.clan_tag == war.enemy_clan_tag
    ])

    await asyncio.gather(*[
        dbclient.upsert_player(
            tag=player.tag,
            name=player.name,
            town_hall=player.town_hall,
            clan_tag=player.clan_tag,
            king=player.king,
            queen=player.queen,
            minion=player.minion,
            warden=player.warden,
            champion=player.champion,
            duke=player.duke,
        )
        for player in enemy_playerdata
    ])

    await asyncio.gather(*[
        dbclient.upsert_war_participant(
            war_id=db_war.id,
            player_tag=participant.player_tag,
            clan_tag=participant.clan_tag,
            map_position=participant.map_position,
            town_hall=participant.town_hall,
        )
        for war, db_war in zip(wars, db_wars)
        for participant in war.participants
    ])

    await asyncio.gather(*[
        dbclient.upsert_attack(
            war_id=db_war.id,
            attacker_tag=attack.attacker_tag,
            defender_tag=attack.defender_tag,
            attack_number=attack.attack_number,
            stars=attack.stars,
            destruction=attack.destruction,
            fresh_hit=attack.fresh_hit,
            cleanup=attack.cleanup,
            duration_seconds=attack.duration_seconds,
        )
        for war, db_war in zip(wars, db_wars)
        for participant in war.participants
        for attack in participant.attacks
    ])
    await dbclient.resolve_war_statuses()

async def refresh_loop():
    try:
        while True:
            print('start refresh')
            try:
                await refresh()
            except httpx.HTTPStatusError:
                sys.exit(1)
            print('finish refresh')
            await asyncio.sleep(int(os.getenv('PASSIVE_REFRESH_SECONDS',100)))
    except asyncio.CancelledError:
        print("Stopping refresh loop...")