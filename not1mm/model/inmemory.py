from __future__ import annotations
from datetime import datetime, UTC, timedelta
import re

from peewee import Model, CharField, BigIntegerField, DateTimeField, SqliteDatabase, SQL

_database = SqliteDatabase(":memory:", pragmas=(
        #('check_same_thread', False),
        ('journal_mode', 'wal'),  # Use WAL-mode (you should always use this!).
        ('foreign_keys', 1)))  # Enforce foreign-key constraints.

class BaseModel(Model):
    class Meta:
        database = _database

class Spot(BaseModel):

    callsign = CharField(max_length=20, index=True)
    ts = DateTimeField(index=True)
    freq_hz = BigIntegerField(index=True)
    mode = CharField(max_length=10, null=True)
    spotter = CharField(max_length=20, null=True)
    comment = CharField(max_length=50, null=True)

    def __str__(self):
        return f"Spot<call={self.callsign},ts={self.ts},freq_hz={self.freq_hz}>"

    @staticmethod
    def get_like_calls(search: str) -> list[str]:
        safe = re.sub('[^a-zA-Z0-9/?]', '', search.upper())
        return Spot.select(Spot.callsign.distinct()).where(SQL(f"callsign like '%{safe.replace('?', '_')}%'"))

    @staticmethod
    def delete_before(minutes_ago: int):
        sql = Spot.delete().where(SQL("ts < datetime('now', ?)", (f"-{minutes_ago} minutes",)))
        return sql.execute()


_database.create_tables([Spot])

if __name__ == '__main__':

    Spot(callsign="VE9KZ", ts=datetime.now(UTC) - timedelta(minutes=10), freq_hz=1000).save()
    Spot(callsign="VE9FI", ts=datetime.now(UTC), freq_hz=1200).save()
    Spot(callsign="ON3SF", ts=datetime.now(UTC), freq_hz=1200).save()

    print(Spot.get_like_calls('ve9k'))
    print(Spot.get_like_calls('f'))
    print(f"deleted {Spot.delete_before(5)}")
    print(list(Spot.select()))



