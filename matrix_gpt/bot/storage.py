import logging
import sqlite3
from pathlib import Path
from typing import Union

logger = logging.getLogger('MatrixGPT')


class Storage:
    insert_event = "INSERT INTO `seen_events` (`event_id`) VALUES (?);"
    seen_events = set()

    def __init__(self, database_file: Union[str, Path]):
        self.conn = sqlite3.connect(database_file)
        self.cursor = self.conn.cursor()

        table_exists = self.cursor.execute("SELECT count(*) FROM sqlite_master WHERE type='table' AND name='seen_events';").fetchall()[0][0]
        if table_exists == 0:
            self.cursor.execute("CREATE TABLE `seen_events` (`event_id` text NOT NULL);")
            logger.info('Created new database file.')

        # This does not work
        # db_seen_events = self.cursor.execute("SELECT `event_id` FROM `seen_events`;").fetchall()

    def add_event_id(self, event_id):
        self.seen_events.add(event_id)

        # This makes the program exit???
        # self.cursor.execute(self.insert_event, (event_id))

    def check_seen_event(self, event_id):
        return event_id in self.seen_events
