from peewee import Model
from playhouse.sqlite_ext import SqliteExtDatabase

_database = None

def loadPersistantDb(path: str):
    _database = SqliteExtDatabase(path, pragmas=(
        ('check_same_thread', False),
        ('journal_mode', 'wal'),  # Use WAL-mode (you should always use this!).
        ('foreign_keys', 1)))  # Enforce foreign-key constraints.


class BaseModel(Model):
    class Meta:
        database = _database


