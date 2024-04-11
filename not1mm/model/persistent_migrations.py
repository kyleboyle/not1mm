# TODO in the future it might be necessary to change persistent schema
# https://docs.peewee-orm.com/en/latest/peewee/playhouse.html#schema-migrations
from peewee import Database

from not1mm import fsutils


def v001_add_contest_meta(db: Database):
    # populate the db with contest definitions
    cursor = db.execute_sql("select count(*) from contestmeta")
    result = cursor.fetchall()
    if result[0][0] == 0:
        for line in (fsutils.APP_DATA_PATH / 'contests.sql').read_text().split("\n"):
            if line:
                db.execute_sql(line)


funcs = [v001_add_contest_meta,
         ]
