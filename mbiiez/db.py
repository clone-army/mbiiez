import sqlite3
import datetime
import threading
import time

from sqlite3 import Error

from mbiiez import settings
from mbiiez.helpers import helpers

class db:

    _cleanup_interval_seconds = 6 * 60 * 60  # every 6 hours
    _last_cleanup = 0.0
    _cleanup_lock = threading.Lock()

    def __init__(self):
        """ generates schema if not already created """
        self.generate_schema()
        self.enable_wal()
        self._maybe_cleanup()



    def enable_wal(self):
        
        try:
            conn = self.connect()
            c = conn.cursor()
            c.execute('PRAGMA journal_mode=WAL;')
        except Error as e:
            print(e)
        finally:
            if conn:
                conn.close()
    def dict_factory(self, cursor, row):
        d = {}
        for idx, col in enumerate(cursor.description):
            d[col[0]] = row[idx]
        return d

    """ Create a database connection to a SQLite database """    
    def connect(self):
        conn = None
        try:
            conn = sqlite3.connect(settings.database.database)
            conn.row_factory = self.dict_factory
            return conn
        except Error as e:
            print(e)

    """ Execute a statement """    
    def execute(self, q):
        conn = None
        try:
            conn = self.connect()
            cur = conn.cursor()
            cur.execute(q)
            conn.commit()
        except Error as e:
            print(e)
        finally:
            if conn:
                conn.close()
            
    """ Create a table using SQL """
    def create_table(self, create_table_sql):
     
        try:
            conn = self.connect()
            c = conn.cursor()
            c.execute(create_table_sql)
        except Error as e:
            print(e)
        finally:
            if conn:
                conn.close()
                            
    """ Create a table using SQL """
    def create_view(self, name, sql):
     
        try:
            conn = self.connect()
            c = conn.cursor()
            #c.execute("DROP VIEW IF EXISTS {}".format(name))
            c.execute("CREATE VIEW IF NOT EXISTS {} AS {}".format(name, sql))
        except Error as e:
            print(e)
        finally:
            if conn:
                conn.close()
                                       

    """ Delete from a table using ID Column """   
    def delete(self, table, id):
       
        try:
            sql = ''' DELETE FROM ''' + table + ''' Where id == "''' + str(id) + '''"'''
            conn = self.connect()
            cur = conn.cursor()
            cur.execute(sql)
            conn.commit()
        except Error as e:
            print(e)        
        finally:
            if conn:
                conn.close()
                
    """ create an entry to given table using a data dictionary """            
    def insert(self, table, d):
        f = ''
        v = []
        q = ""
        
        d["added"] = str(datetime.datetime.now())
        
        for key in d.keys():
            f = "{},{}".format(f, key)
            v.append(helpers().ansi_strip(str(d[key])))
            q = "{},{}".format(q,"?")
            
       
        f = f[1:] #""" Keys """
        q = q[1:] #""" Place Holders """  
        v = tuple(v)     #""" Turple of values """   
          
        sql = ''' INSERT INTO ''' + table + '''(''' + f + ''')
                  VALUES(''' + q + ''') '''
                  
        conn = self.connect()
        cur = conn.cursor()
        cur.execute(sql, v)
        conn.commit()
        
        if conn:
            conn.close()
                    
        return cur.lastrowid 
        
    """ Table exists without locking """           
    def table_exists(self, table):
        d = self.select("sqlite_master", {"type": "table", "name": table})
        if(len(d) > 0):
            return True
        else:
            return False
            
    """ View exists without locking """           
    def view_exists(self, view):
        d = self.select("sqlite_master", {"type": "view", "name": view})
        if(len(d) > 0):
            return True
        else:
            return False
              
  
    """ Use a dictionary to find matching entries """    
    def select(self, table, d):
    
        w = ''
        v = []
        conn = self.connect()
        cur = conn.cursor()

        for key in d.keys():
            w = w + "{}=? AND ".format(key)
            v.append(helpers().ansi_strip(d[key]))

        v = tuple(v)     #""" Turple of values """   
        w = w[:-4] #""" Keys """    
        q = ''' SELECT * FROM ''' + table + ''' WHERE ''' + w
        cur.execute(q, v)
        rows = cur.fetchall()
    
        if conn:
            conn.close()
                        
        return rows
        
    def clean_up(self):
        conn = self.connect()
        if not conn:
            return

        try:
            cur = conn.cursor()
            retention_days = {
                "logs": 7,
                "chatter": 7,
                "connections": 14,
                "player_info": 14,
                "frags": 30,
                "processes": 3,
            }

            for table, days in retention_days.items():
                try:
                    cur.execute(
                        f"DELETE FROM {table} WHERE added < datetime('now', '-{days} day')"
                    )
                except Exception as table_err:
                    print(f"Cleanup warning on table {table}: {table_err}")

            conn.commit()

            try:
                cur.execute("VACUUM")
            except Exception as vacuum_err:
                print(f"Cleanup vacuum warning: {vacuum_err}")

        except Error as e:
            print(f"Cleanup error: {e}")
        finally:
            if conn:
                conn.close()

    def _maybe_cleanup(self):
        now = time.time()
        if now - db._last_cleanup < db._cleanup_interval_seconds:
            return

        with db._cleanup_lock:
            # Re-check inside lock to avoid duplicate work
            now = time.time()
            if now - db._last_cleanup < db._cleanup_interval_seconds:
                return

            try:
                self.clean_up()
            finally:
                db._last_cleanup = time.time()
        
    def temp_get_player_id(self, player):
        conn = self.connect()
        cur = conn.cursor()
        player = helpers().ansi_strip(player)     
        q = ''' SELECT * FROM connections where player = "''' + player + '''" and type = "CONNECT" ORDER BY added DESC LIMIT 1; '''
        cur.execute(q)
        rows = cur.fetchall()
        if conn:
            conn.close()
            
        return rows       
        
    def get_latest_player_info_change(self, player_id):
        conn = self.connect()
        cur = conn.cursor()
        player = helpers().ansi_strip(player)     
        q = ''' SELECT * FROM logs where log LIKE "ClientUserinfoChanged: ''' + str(player_id) + '''" ORDER BY added DESC LIMIT 1; '''
        cur.execute(q)
        result = cur.fetchone()
        
        if conn:
            conn.close()        
        
        return result           
        
    def generate_schema(self):
        
        # Stores only in-game chatter from log file
        if(not self.table_exists("chatter")):
            self.create_table("""
            CREATE TABLE IF NOT EXISTS chatter (
                id integer PRIMARY KEY AUTOINCREMENT,
                added datetime,
                player text,
                instance text,
                type text,
                message varchar
            );""")
        
        # Overall log holder, auto cleared to remove older log lines
        if(not self.table_exists("logs")):        
            self.create_table("""
            CREATE TABLE IF NOT EXISTS logs (
                id integer PRIMARY KEY AUTOINCREMENT,
                added datetime,
                log text,
                instance text
            );""")        
        
        # Tracks all frags / kills by a client
        if(not self.table_exists("frags")):        
            self.create_table("""
            CREATE TABLE IF NOT EXISTS frags (
                id integer PRIMARY KEY AUTOINCREMENT,
                added datetime,
                instance text,
                fragger text,
                fragged text,
                weapon text
            );""")
        
        # Tracks all connects and disconnects by a client
        if(not self.table_exists("connections")):        
            self.create_table("""
            CREATE TABLE IF NOT EXISTS connections (
                id integer PRIMARY KEY AUTOINCREMENT,
                added datetime,            
                player_id integer,
                player text,
                instance text,
                ip text,
                type text
            );""")

        # Tracks split play info changes
        if(not self.table_exists("player_info")):        
            self.create_table("""
            CREATE TABLE IF NOT EXISTS player_info (
                id integer PRIMARY KEY AUTOINCREMENT,
                added datetime,            
                player_id integer,
                player text,
                instance text,
                class_id text,
                class_name text,
                model text           
            );""")
              
        # Tracks processes / services and their PIDs
        if(not self.table_exists("processes")):        
            self.create_table("""
            CREATE TABLE IF NOT EXISTS processes (
                id integer PRIMARY KEY AUTOINCREMENT,
                added datetime,            
                pid integer,
                name text,
                instance text
            );""")        
                  
        
        # View, latest player "Client Change Info"
        if(not self.view_exists("latest_player_info")):        
            self.create_view("latest_player_info", """
               select max(p.added) as last_info_change, 
                p.class_id, 
                p.class_name,
                p.model,
                p.player_id,
                p.player,
                p.instance

                from player_info p

                group by p.player
            ;""")            
        
        # View, All Active Connections
        if(not self.view_exists("active_connections")):         
            self.create_view("active_connections", """
                select 
                max(c.added) last_connect, 
                c.player_id, 
                c.player, 
                c.instance, 
                c.ip,
                i.model,
                i.class_id,
                i.class_name

                from connections c

                left join connections d

                on d.instance = c.instance
                and d.player_id = c.player_id
                and d.added > c.added

                join latest_player_info i
                on i.player = c.player
                and i.instance = c.instance

                where c.type = "CONNECT"
                and d.id is null
                and printf("%d", c.player_id) = c.player_id
                and datetime(c.added) >=datetime('now', '-2 Hour')

                group by c.player

                order by c.added desc
            ;""")             