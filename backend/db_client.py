from models import Clan, Player, PlayerClanHistory, War, WarParticipant, Attack, WarResult, WarType
from datetime import datetime, timezone
from database import SessionLocal
from sqlalchemy import select

class _Unset:
    pass

_UNSET = _Unset()

def utcnow():
    return datetime.now(timezone.utc)

class DbClient:
    async def upsert_clan(
        self,
        tag: str,
        name: str | None = None,
        badge_url: str | None = None,
        clan_level: int | None = None,
        war_wins: int | None = None,
        war_draws: int | None = None,
        war_losses: int | None = None,
        is_tracked: bool | None = None,
    ) -> Clan:
        async with SessionLocal() as session:
            clan = await session.scalar(select(Clan).where(Clan.tag == tag))

            clan_fields = {
                "name": name,
                "badge_url": badge_url,
                "clan_level": clan_level,
                "war_wins": war_wins,
                "war_draws": war_draws,
                "war_losses": war_losses,
                "is_tracked": is_tracked,
            }

            if clan:
                for field, value in clan_fields.items():
                    if value is not None:
                        setattr(clan, field, value)
                clan.last_synced_at = utcnow()
            else:
                required_fields = {"name", "clan_level", "war_wins", "war_draws", "war_losses"}
                missing_required = [f for f in required_fields if clan_fields[f] is None]
                if missing_required:
                    raise ValueError(f'required field(s) {missing_required} is "None" on insertion')
                filtered_fields = {k: v for k, v in clan_fields.items() if v is not None}
                clan = Clan(tag=tag, is_tracked=is_tracked or False, **filtered_fields)
                session.add(clan)

            await session.commit()
            await session.refresh(clan)
        return clan

    async def upsert_player(
        self,
        tag: str,
        name: str | None = None,
        town_hall: int | None = None,
        clan_tag: str | None | _Unset = _UNSET,
        king: int | None = None,
        queen: int | None = None,
        minion: int | None = None,
        warden: int | None = None,
        champion: int | None= None,
        duke: int | None = None,
    ) -> Player:
        async with SessionLocal() as session:
            player = await session.scalar(select(Player).where(Player.tag == tag))
            player_fields = {
                "name": name,
                "town_hall": town_hall,
                "king": king,
                "queen": queen,
                "minion": minion,
                "warden": warden,
                "champion": champion,
                "duke": duke,
            }
            hero_defaults = {"king", "queen", "minion", "warden", "champion", "duke"}
            required_fields = {"name", "town_hall"}

            if player:
                for field, value in player_fields.items():
                    if value is not None:
                        setattr(player, field, value)

                # Only touch clan status if the caller actually passed clan_tag.
                # clan_tag=None here means "player explicitly has no clan" (they left).
                if clan_tag is not _UNSET and player.clan_tag != clan_tag:
                    old_clanentry = await session.scalar(
                        select(PlayerClanHistory).where(
                            PlayerClanHistory.left_at == None,
                            PlayerClanHistory.player_tag == player.tag,
                        )
                    )
                    if old_clanentry:
                        old_clanentry.left_at = utcnow()
                    if clan_tag is not None:
                        session.add(PlayerClanHistory(
                            player_tag=player.tag,
                            clan_tag=clan_tag,
                            joined_at=utcnow(),
                        ))
                    player.clan_tag = clan_tag
            else:
                missing_required = [f for f in required_fields if player_fields[f] is None]
                if missing_required:
                    raise ValueError(f'required field(s) {missing_required} is "None" on insertion')
                for f in hero_defaults:
                    if player_fields[f] is None:
                        player_fields[f] = 0

                resolved_clan_tag = None if clan_tag is _UNSET else clan_tag
                player = Player(tag=tag, **player_fields, clan_tag=resolved_clan_tag)
                session.add(player)
                if resolved_clan_tag is not None:
                    session.add(PlayerClanHistory(
                        player_tag=player.tag,
                        clan_tag=resolved_clan_tag,
                        joined_at=utcnow(),
                    ))
            await session.commit()
            await session.refresh(player)
        return player

    async def upsert_war(
        self,
        our_clan_tag: str,
        enemy_clan_tag: str,
        end_time: datetime,
        start_time: datetime | None = None,
        war_type: WarType | None = None,
        size: int | None = None,
        attacks_allowed: int | None = None,
        result: WarResult | None = None,
    ) -> War:
        async with SessionLocal() as session:
            war = await session.scalar(
                select(War).where(
                    War.our_clan_tag == our_clan_tag,
                    War.enemy_clan_tag == enemy_clan_tag,
                    War.end_time == end_time,
                )
            )

            war_fields = {
                "start_time": start_time,
                "war_type": war_type,
                "size": size,
                "attacks_allowed": attacks_allowed,
                "result": result,
            }

            if war:
                for field, value in war_fields.items():
                    if value is not None:
                        setattr(war, field, value)
            else:
                required_fields = {"start_time", "size", "war_type"}
                missing_required = [f for f in required_fields if war_fields[f] is None]
                if missing_required:
                    raise ValueError(f'required field(s) {missing_required} is "None" on insertion')
                filtered_fields = {k: v for k, v in war_fields.items() if v is not None}
                war = War(
                    our_clan_tag=our_clan_tag,
                    enemy_clan_tag=enemy_clan_tag,
                    end_time=end_time,
                    **filtered_fields,
                )
                session.add(war)

            await session.commit()
            await session.refresh(war)

        return war

    async def upsert_war_participant(
        self,
        war_id: int,
        player_tag: str,
        clan_tag: str | None = None,
        map_position: int | None = None,
        town_hall: int | None = None,
    ) -> WarParticipant:
        async with SessionLocal() as session:
            participant = await session.scalar(
                select(WarParticipant).where(
                    WarParticipant.war_id == war_id,
                    WarParticipant.player_tag == player_tag,
                )
            )

            participant_fields = {
                "clan_tag": clan_tag,
                "map_position": map_position,
                "town_hall": town_hall,
            }

            if participant:
                for field, value in participant_fields.items():
                    if value is not None:
                        setattr(participant, field, value)
            else:
                required_fields = {"clan_tag", "map_position", "town_hall"}
                missing_required = [f for f in required_fields if participant_fields[f] is None]
                if missing_required:
                    raise ValueError(f'required field(s) {missing_required} is "None" on insertion')

                player = await session.scalar(
                    select(Player).where(Player.tag == player_tag)
                )
                if player is None:
                    raise ValueError(f'no player found with tag "{player_tag}" on insertion')

                filtered_fields = {k: v for k, v in participant_fields.items() if v is not None}
                participant = WarParticipant(
                    war_id=war_id,
                    player_tag=player_tag,
                    king=player.king,
                    queen=player.queen,
                    minion=player.minion,
                    warden=player.warden,
                    champion=player.champion,
                    duke=player.duke,
                    **filtered_fields,
                )
                session.add(participant)

            await session.commit()
            await session.refresh(participant)

        return participant

    async def upsert_attack(
        self,
        war_id: int,
        attacker_tag: str,
        defender_tag: str,
        attack_number: int,
        stars: int | None = None,
        destruction: int | None = None,
        fresh_hit: bool | None = None,
        cleanup: bool | None = None,
        duration_seconds: int | None = None,
    ) -> Attack:
        async with SessionLocal() as session:
            attack = await session.scalar(
                select(Attack).where(
                    Attack.war_id == war_id,
                    Attack.attacker_tag == attacker_tag,
                    Attack.attack_number == attack_number,
                )
            )

            attack_fields = {
                "stars": stars,
                "destruction": destruction,
                "fresh_hit": fresh_hit,
                "cleanup": cleanup,
                "duration_seconds": duration_seconds,
            }

            if attack:
                for field, value in attack_fields.items():
                    if value is not None:
                        setattr(attack, field, value)
            else:
                required_fields = {"stars", "destruction"}
                missing_required = [f for f in required_fields if attack_fields[f] is None]
                if missing_required:
                    raise ValueError(f'required field(s) {missing_required} is "None" on insertion')
                filtered_fields = {k: v for k, v in attack_fields.items() if v is not None}
                attack = Attack(
                    war_id=war_id,
                    attacker_tag=attacker_tag,
                    defender_tag=defender_tag,
                    attack_number=attack_number,
                    **filtered_fields,
                )
                session.add(attack)

            await session.commit()
            await session.refresh(attack)

        return attack

    async def get_tracked_clans(self) -> list[Clan]:
        q = select(Clan).where(Clan.is_tracked.is_(True))
        async with SessionLocal() as session:
            result = await session.scalars(q)
            response = result.all()
        return response

    async def resolve_war_statuses(self) -> None:
        q = select(War).where(War.result.is_(None))
        async with SessionLocal() as session:
            result = await session.scalars(q)
            response = result.all()
            for war in response:
                if war.our_stars > war.enemy_stars:
                    war.result = WarResult.WIN
                elif war.our_stars < war.enemy_stars:
                    war.result = WarResult.LOSS
                else:
                    if war.our_destruction > war.enemy_destruction:
                        war.result = WarResult.WIN
                    elif war.our_destruction < war.enemy_destruction:
                        war.result = WarResult.LOSS
                    else:
                        war.result = WarResult.DRAW
            await session.commit()