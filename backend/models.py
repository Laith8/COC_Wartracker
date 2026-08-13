from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum as SQLEnum,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    CheckConstraint,
    ForeignKeyConstraint,
)

from sqlalchemy.orm import relationship, foreign

from database import Base


def utcnow():
    return datetime.now(timezone.utc)


# ----------------------------------------------------
# ENUMS
# ----------------------------------------------------

class WarType(str, Enum):
    RANDOM = "random"
    FRIENDLY = "friendly"
    CWL = "cwl"


class WarResult(str, Enum):
    WIN = "win"
    LOSS = "loss"
    DRAW = "draw"


# ----------------------------------------------------
# CLAN
# ----------------------------------------------------

class Clan(Base):
    __tablename__ = "clans"

    id = Column(Integer, primary_key=True)
    tag = Column(String, unique=True, nullable=False, index=True)
    name = Column(String, nullable=False)

    badge_url = Column(String, nullable=True)
    clan_level = Column(Integer, nullable=False)
    war_wins = Column(Integer, nullable=False)
    war_draws = Column(Integer, nullable=False)
    war_losses = Column(Integer, nullable=False)

    is_tracked = Column(Boolean, default=False, nullable=False)

    created_at = Column(DateTime, default=utcnow, nullable=False)
    last_synced_at = Column(DateTime, default=utcnow, nullable=False)

    players = relationship("Player", back_populates="clan")

    wars_as_our_clan = relationship(
        "War",
        back_populates="our_clan",
        foreign_keys="War.our_clan_tag",
    )
    wars_as_enemy_clan = relationship(
        "War",
        back_populates="enemy_clan",
        foreign_keys="War.enemy_clan_tag",
    )

    @property
    def member_count(self):
        return len(self.players)


# ----------------------------------------------------
# PLAYER
# ----------------------------------------------------

class Player(Base):
    __tablename__ = "players"

    id = Column(Integer, primary_key=True)

    tag = Column(String, unique=True, nullable=False, index=True)
    name = Column(String, nullable=False)

    town_hall = Column(Integer, nullable=False)

    clan_tag = Column(String, ForeignKey("clans.tag"), index=True, nullable=True)

    king = Column(Integer, default=0, nullable=False)
    queen = Column(Integer, default=0, nullable=False)
    minion = Column(Integer, default=0, nullable=False)
    warden = Column(Integer, default=0, nullable=False)
    champion = Column(Integer, default=0, nullable=False)
    duke = Column(Integer, default=0, nullable=False)

    clan = relationship("Clan", back_populates="players")

    participations = relationship("WarParticipant", back_populates="player")


class PlayerClanHistory(Base):
    __tablename__ = "player_clan_history"

    id = Column(Integer, primary_key=True)

    player_tag = Column(String, ForeignKey("players.tag"), nullable=False, index=True)
    clan_tag = Column(String, ForeignKey("clans.tag"), nullable=False, index=True)

    joined_at = Column(DateTime, nullable=False)
    left_at = Column(DateTime, nullable=True)

    player = relationship("Player")
    clan = relationship("Clan")

# ----------------------------------------------------
# WAR
# ----------------------------------------------------

class War(Base):
    __tablename__ = "wars"

    id = Column(Integer, primary_key=True)

    war_type = Column(SQLEnum(WarType), nullable=False)

    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=False)

    our_clan_tag = Column(String, ForeignKey("clans.tag"), nullable=False, index=True)
    enemy_clan_tag = Column(String, ForeignKey("clans.tag"), nullable=False, index=True)

    size = Column(Integer, nullable=False)
    attacks_allowed = Column(Integer, default=2, nullable=False)

    result = Column(SQLEnum(WarResult), nullable=True)

    our_clan = relationship(
        "Clan", back_populates="wars_as_our_clan", foreign_keys=[our_clan_tag]
    )
    enemy_clan = relationship(
        "Clan", back_populates="wars_as_enemy_clan", foreign_keys=[enemy_clan_tag]
    )

    participants = relationship(
        "WarParticipant",
        back_populates="war",
        cascade="all",
    )

    attacks = relationship(
        "Attack",
        back_populates="war",
        cascade="all"
    )

    @property
    def our_stars(self):
        return sum(
            attack.stars
            for attack in self.attacks
            if attack.attacker.clan_tag == self.our_clan_tag
        )

    @property
    def enemy_stars(self):
        return sum(
            attack.stars
            for attack in self.attacks
            if attack.attacker.clan_tag == self.enemy_clan_tag
        )

    @property
    def our_destruction(self):
        return sum(
            attack.destruction
            for attack in self.attacks
            if attack.attacker.clan_tag == self.our_clan_tag
        )

    @property
    def enemy_destruction(self):
        return sum(
            attack.destruction
            for attack in self.attacks
            if attack.attacker.clan_tag == self.enemy_clan_tag
        )

    __table_args__ = (
        UniqueConstraint("our_clan_tag", "enemy_clan_tag", "end_time"),
    )

# ----------------------------------------------------
# WAR PARTICIPANTS
# ----------------------------------------------------

class WarParticipant(Base):
    __tablename__ = "war_participants"

    id = Column(Integer, primary_key=True)

    war_id = Column(Integer, ForeignKey("wars.id"), nullable=False, index=True)
    player_tag = Column(String, ForeignKey("players.tag"), nullable=False, index=True)
    clan_tag = Column(String, ForeignKey("clans.tag"), nullable=False, index=True)

    map_position = Column(Integer, nullable=False)
    town_hall = Column(Integer, nullable=False)

    king = Column(Integer, default=0, nullable=False)
    queen = Column(Integer, default=0, nullable=False)
    minion = Column(Integer, default=0, nullable=False)
    warden = Column(Integer, default=0, nullable=False)
    champion = Column(Integer, default=0, nullable=False)
    duke = Column(Integer, default=0, nullable=False)

    war = relationship("War", back_populates="participants")
    player = relationship("Player", back_populates="participations")
    clan = relationship("Clan")

    attacks_made = relationship(
        "Attack",
        primaryjoin=lambda: (
            (WarParticipant.war_id == Attack.war_id)
            & (WarParticipant.player_tag == foreign(Attack.attacker_id))
        ),
        back_populates="attacker",
    )

    attacks_received = relationship(
        "Attack",
        primaryjoin=lambda: (
            (WarParticipant.war_id == Attack.war_id)
            & (WarParticipant.player_tag == foreign(Attack.defender_id))
        ),
        back_populates="defender",
    )

    clan = relationship("Clan")

    @property
    def attacks_used(self):
        return len(self.attacks_made)

    @property
    def stars_gained(self):
        return sum(a.stars for a in self.attacks_made)

    @property
    def destruction_gained(self):
        return sum(a.destruction for a in self.attacks_made)

    @property
    def stars_lost(self):
        return sum(a.stars for a in self.attacks_received)

    @property
    def destruction_lost(self):
        return sum(a.destruction for a in self.attacks_received)

    @property
    def missed_attacks(self):
        return max(self.war.attacks_allowed - self.attacks_used, 0)

    __table_args__ = (
        UniqueConstraint("war_id", "player_tag"),
    )


# ----------------------------------------------------
# ATTACK
# ----------------------------------------------------

class Attack(Base):
    __tablename__ = "attacks"

    id = Column(Integer, primary_key=True)

    war_id = Column(Integer, ForeignKey("wars.id"), nullable=False, index=True)
    attacker_tag = Column(String, nullable=False, index=True)
    defender_tag = Column(String, nullable=False, index=True)
    attack_number = Column(Integer, nullable=False)

    stars = Column(Integer, nullable=False)
    destruction = Column(Integer, nullable=False)

    fresh_hit = Column(Boolean, default=False, nullable=False)
    cleanup = Column(Boolean, default=False, nullable=False)

    duration_seconds = Column(Integer, default=0, nullable=False)

    war = relationship("War", back_populates="attacks")

    attacker = relationship(
        "WarParticipant",
        primaryjoin=lambda: (
            (Attack.war_id == WarParticipant.war_id)
            & (Attack.attacker_tag == foreign(WarParticipant.player_tag))
        ),
        viewonly=True,
    )

    defender = relationship(
        "WarParticipant",
        primaryjoin=lambda: (
            (Attack.war_id == WarParticipant.war_id)
            & (Attack.defender_tag == foreign(WarParticipant.player_tag))
        ),
        viewonly=True,
    )

    __table_args__ = (
        UniqueConstraint(
            "war_id", "attacker_tag", "attack_number",
            name="uq_attack_war_attacker_number",
        ),
        ForeignKeyConstraint(
            ["war_id", "attacker_tag"],
            ["war_participants.war_id", "war_participants.player_tag"],
        ),
        ForeignKeyConstraint(
            ["war_id", "defender_tag"],
            ["war_participants.war_id", "war_participants.player_tag"],
        ),
    )