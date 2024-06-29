import sqlite3
import logging
from  threading import RLock
from config import DATABASE_PATH
from datetime import datetime, timedelta, timezone
from typing import List, Tuple
from enum import Enum


class settings (Enum):
    DEST_ID = "destination_chat_id"


class Database(object):

    DB_LOCATION = DATABASE_PATH

    def __init__(self):
        """Initialize db class variables"""
        try:
            self.lock = RLock()
            self.connection = sqlite3.connect(Database.DB_LOCATION, check_same_thread=False)
            self.cur = self.connection.cursor()

            self._ensure_schema()
        except sqlite3.Error as e:
            logging.error(f"Database error: {e}")
            raise e # Initialization errors are catastrophic and should be reraised

    def __enter__(self):
        return self

    def __exit__(self, ext_type, exc_value, traceback):
        if exc_value is not None:
            # If there's an exception, roll back any changes made during the transaction.
            try:
                self.connection.rollback()
                logging.info(f"Database transaction rolled back due to an exception: {exc_value}")
            except sqlite3.Error as e:
                logging.error(f"Database transaction rolled back due to an exception: {exc_value} \n \
                              The following exception occured during rollback: {e}")
        else:
            # If no exception occurred, commit the changes.
            try:
                self.connection.commit()
                logging.info("Database transaction committed successfully.")
            except sqlite3.Error as e:
                logging.error(f"Database error during commit: {e}")

        # Attempt to close the connection
        self._close()


    def _ensure_schema(self):
        """create a database table if it does not exist already"""
        self.cur.execute("""
            CREATE TABLE IF NOT EXISTS users_requesting_entry (
                user_id INTEGER,
                full_name STRING,
                username STRING,
                last_accessed_bot TIMESTAMP,
                last_uploaded_video TIMESTAMP,
                number_videos_uploaded INTEGER DEFAULT 0,
                access_granted TIMESTAMP,
                invite_link STRING,
                link_used TIMESTAMP,         
                chat_id INTEGER,
                PRIMARY KEY (user_id)
            )
        """
        )

        self.cur.execute(f"PRAGMA table_info(users_requesting_entry)")
        columns = [column[1] for column in self.cur.fetchall()]

        if 'chat_id' not in columns:
            # If the column doesn't exist, add it to the table
            self.cur.execute(f"ALTER TABLE users_requesting_entry ADD COLUMN chat_id INTEGER")


        self.cur.execute("""
            CREATE TABLE IF NOT EXISTS active_chats (
                chat_id INT PRIMARY KEY,
                chat_name STRING
            )
        """
        )


        self.cur.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                setting STRING PRIMARY KEY,
                value VARCHAR(255)
            )
        """
        )

        self._commit()

    def _close(self):
        """close sqlite3 connection"""
        try:
            with self.lock:
                if not self.connection.closed:
                    self.connection.close()
        except sqlite3.Error as e:
            logging.error(f"Database error: {e}")


    def _execute(self, query, params=None):
        """Execute a row of data to current cursor with detailed error handling."""
        try:
            with self.lock:
                if params is None:
                    self.cur.execute(query)
                else:
                    self.cur.execute(query, params)
                return True
        except sqlite3.Error as e:
            logging.error(f"Database error during execute: {e} - Query: {query}")
            # You could optionally include more information about the error
            error_info = {
                'error': str(e),
                'query': query,
                'params': params
            }
            # Consider throwing a custom exception or return error information
            raise Exception(f"Database operation failed: {error_info}")
            # Alternatively, you can return False and error details
            # return False, error_info


    def _commit(self):
        """commit changes to database"""
        with self.lock:
            self.connection.commit()


    def record_bot_user(self, user_id, full_name, username, chat_id) -> bool:
        """record bot access time for user"""
        query = """
                INSERT INTO users_requesting_entry (user_id, full_name, username, last_accessed_bot, chat_id)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE
                SET last_accessed_bot = EXCLUDED.last_accessed_bot,
                    chat_id = EXCLUDED.chat_id
                """
        params =  (user_id, full_name, username, datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f"), chat_id)
        success = self._execute(query, params)
        if success:
            self._commit()
        else:
            raise Exception("Error recording bot access time")
        return success


    def delete_user(self, user_id) -> bool:
        """delete user from database"""
        query = """
                DELETE FROM users_requesting_entry
                WHERE user_id = ?
                """
        params = (user_id,)
        success = self._execute(query, params)
        if success:
            self._commit()
        else:
            raise Exception("Error deleting user")
        return success
    
    
    def record_video_upload(self, user_id) -> bool:

        ## NOTE Add coalesce for times uploaded
        """record video upload time for user"""
        query = """
                INSERT INTO users_requesting_entry (user_id, last_uploaded_video, number_videos_uploaded)
                VALUES (?, ?, 1)
                ON CONFLICT(user_id) DO UPDATE
                SET last_uploaded_video = EXCLUDED.last_uploaded_video,
                    number_videos_uploaded = users_requesting_entry.number_videos_uploaded + 1
                """
        params =  (user_id, datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f"))
        success = self._execute(query, params)
        if success:
            self._commit()
            fetch_query = "SELECT number_videos_uploaded FROM users_requesting_entry WHERE user_id = ?"
            self.cur.execute(fetch_query, (user_id,))
            number_videos_uploaded = self.cur.fetchone()[0]     
        else:
            raise Exception("Error recording video upload time")
        return number_videos_uploaded
    

    def record_access_granted(self, user_id, invite_link) -> bool:
        """record access granted time for user"""
        query = """
                INSERT INTO users_requesting_entry (user_id, access_granted, invite_link)
                VALUES (?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE
                SET access_granted = EXCLUDED.access_granted,
                    invite_link = EXCLUDED.invite_link,
                    link_used = NULL
                """
        params =  (user_id, datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f"), invite_link)
        success = self._execute(query, params)
        if success:
            self._commit()
        else:
            raise Exception("Error recording access granted time")
        return success
    

    def record_link_used(self, user_id) -> bool:
        """record link used time for user"""
        query = """
                INSERT INTO users_requesting_entry (user_id, link_used)
                VALUES (?, ?)
                ON CONFLICT(user_id) DO UPDATE
                SET link_used = EXCLUDED.link_used
                """
        params =  (user_id, datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f"))
        success = self._execute(query, params)
        if success:
            self._commit()
        else:
            raise Exception("Error recording link used time")
        return success  
    

    def record_active_chat(self, chat_id, chat_name) -> bool:
        """record active chat in database"""
        query = """
                INSERT INTO active_chats (chat_id, chat_name)
                VALUES (?, ?)
                ON CONFLICT(chat_id) DO UPDATE
                SET chat_name = EXCLUDED.chat_name
                """
        params =  (chat_id, chat_name)
        success = self._execute(query, params)
        if success:
            self._commit()
        else:
            raise Exception("Error recording active chat")
        return success
    

    def return_all_active_chats(self) -> dict:
        """return all active chats in database"""
        query = """
                SELECT * FROM active_chats
                """
        success = self._execute(query)
        reply = self.cur.fetchall()
        if success:
            chat_dict = {}
            for chat in reply:
                chat_dict[chat[0]] = chat[1]
            return chat_dict
        else:
            raise Exception("Error returning all active chats")
    

    def update_settings(self, setting, value) -> bool:
        """record settings in database"""
        query = """
                INSERT INTO settings (setting, value)
                VALUES (?, ?)
                ON CONFLICT(setting) DO UPDATE
                SET value = EXCLUDED.value
                """
        params =  (setting, value)
        success = self._execute(query, params)
        if success:
            self._commit()
        else:
            raise Exception("Error recording settings")
        return success
    

    def lookup_setting(self, setting) -> Tuple:
        """lookup setting in database"""
        query = """
                SELECT value FROM settings
                WHERE setting = ?
                """
        params = (setting,)
        success = self._execute(query, params)
        if success:
            result = self.cur.fetchone()
            return result[0] if result else None
        else:
            raise Exception("Error looking up setting")
        

    def lookup_invite_link(self, invite_link) -> Tuple:
        """lookup invite link in database"""
        query = """
                SELECT * FROM users_requesting_entry
                WHERE invite_link = ?
                """
        params = (invite_link,)
        success = self._execute(query, params)
        if success:
            return self.cur.fetchone()
        else:
            raise Exception("Error looking up invite link")
    
    
    def lookup_user(self, user_id) -> Tuple:
        """lookup user in database"""
        query = """
                SELECT * FROM users_requesting_entry
                WHERE user_id = ?
                """
        params = (user_id,)
        success = self._execute(query, params)
        if success:
            return self.cur.fetchone()
        else:
            raise Exception("Error looking up user")
        
        
    def lookup_active_chat_title_with_id(self, chat_id) -> Tuple:
        """lookup active chat in database"""
        query = """
                SELECT chat_name FROM active_chats
                WHERE chat_id = ?
                """
        params = (chat_id,)
        success = self._execute(query, params)
        result = self.cur.fetchone()
        if success:
            return result[0] if result[0] else None
        else:
            raise Exception("Error looking up active chat")
        
    
    def return_all_users(self) -> List[Tuple]:
        """return all users in database"""
        query = """
                SELECT * FROM users_requesting_entry
                """
        success = self._execute(query)
        if success:
            return self.cur.fetchall()
        else:
            raise Exception("Error returning all users")
        

    def return_users_for_chat(self, chat_id) -> List[Tuple]:
        """return all users in database"""
        query = """
                SELECT * FROM users_requesting_entry
                WHERE chat_id = ?
                """
        params = (chat_id,)
        success = self._execute(query, params)
        if success:
            return self.cur.fetchall()
        else:
            raise Exception("Error returning all users")



    def delete_active_chat(self, chat_id) -> bool:      
        """delete active chat from database"""
        query = """
                DELETE FROM active_chats
                WHERE chat_id = ?
                """
        params = (chat_id,)
        success = self._execute(query, params)
        if success:
            self._commit()
        else:
            raise Exception("Error deleting active chat")
        return success
    

    def delete_users_for_chat(self, chat_id) -> bool:
        """delete user from database"""
        query = """
                DELETE FROM users_requesting_entry
                WHERE chat_id = ?
                """
        params = (chat_id,)
        success = self._execute(query, params)
        if success:
            self._commit()
        else:
            raise Exception("Error deleting user")
        return success
        

    def drop_table(self):
        """drop table from database"""
        query = """
                DROP TABLE IF EXISTS users_requesting_entry
                """
        success = self._execute(query)
        if success:
            self._commit()
        else:
            raise Exception("Error dropping table")
