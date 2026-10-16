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
    _init_lock = threading.Lock()
    _initialized = False

    def __init__(self):
        """ generates schema if not already created """
        self._ensure_initialized()
        self._maybe_cleanup()

    def _ensure_initialized(self):
        if db._initialized:
            return

        with db._init_lock:
            if db._initialized:
                return

            self.generate_schema()
            self.enable_wal()
            db._initialized = True



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
            # Several processes write here at once (each instance, the web UI,
            # the API): wait for the lock rather than fail. In WAL mode,
            # synchronous=NORMAL is still safe from corruption on a crash and
            # skips a disk sync on every commit - inserts ~13x faster.
            conn = sqlite3.connect(settings.database.database, timeout=15)
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA temp_store=MEMORY")
            conn.execute("PRAGMA cache_size=-16000")
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

    def insert_logs_batch(self, rows):
        """
        Insert many log rows in one transaction.
        rows: list of tuples (added, log, instance)
        """
        if not rows:
            return

        conn = None
        try:
            conn = self.connect()
            cur = conn.cursor()
            cur.executemany(
                "INSERT INTO logs (added, log, instance) VALUES (?, ?, ?)",
                rows,
            )
            conn.commit()
        except Error as e:
            print(e)
        finally:
            if conn:
                conn.close()
        
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
        
    # How long each table keeps its rows. Connections are kept longest: the
    # Connections page traces players by them.
    RETENTION_DAYS = {
        "logs": 7,
        "chatter": 7,
        "connections": 30,
        "player_info": 14,
        "frags": 30,
        "processes": 3,
        "web_audit": 180,
    }

    def clean_up(self, vacuum=False):
        """Drop rows past their table's retention, a batch at a time so no
        other process waits long for the lock. VACUUM (which rewrites the
        whole file and blocks every writer while it does) only when asked -
        from db_maintenance, with the servers stopped."""
        conn = self.connect()
        if not conn:
            return
        try:
            for table, days in self.RETENTION_DAYS.items():
                cutoff = (datetime.datetime.now() - datetime.timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
                try:
                    while True:
                        cur = conn.execute(
                            f"DELETE FROM {table} WHERE rowid IN (SELECT rowid FROM {table} WHERE added < ? LIMIT 5000)", (cutoff,))
                        conn.commit()
                        if cur.rowcount < 5000:
                            break
                        time.sleep(0.05)  # let the others in
                except Exception as table_err:
                    print(f"Cleanup warning on table {table}: {table_err}")
            if vacuum:
                conn.execute("VACUUM")
                conn.execute("ANALYZE")
            else:
                conn.execute("PRAGMA optimize")
        except Error as e:
            print(f"Cleanup error: {e}")
        finally:
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
            db._last_cleanup = now
            # Every process gets here; only the first in each 6 hours cleans.
            conn = self.connect()
            try:
                conn.execute("BEGIN IMMEDIATE")
                row = conn.execute("SELECT value FROM maintenance WHERE key = 'last_cleanup'").fetchone()
                if row and now - float(row["value"]) < db._cleanup_interval_seconds:
                    conn.rollback()
                    return
                conn.execute("INSERT OR REPLACE INTO maintenance (key, value) VALUES ('last_cleanup', ?)", (str(now),))
                conn.commit()
            except Error as e:
                print(f"Cleanup check: {e}")
                return
            finally:
                conn.close()
            self.clean_up()

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
                message varchar,
                target text
            );""")
        else:
            # Who a TELL went to - added after the table, so older ones lack it.
            conn = self.connect()
            try:
                if "target" not in [c["name"] for c in conn.execute("PRAGMA table_info(chatter)")]:
                    conn.execute("ALTER TABLE chatter ADD COLUMN target text")
                    conn.commit()
            except Error as e:
                print(e)
            finally:
                conn.close()

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

        # Tracks moderation/admin actions triggered from the web UI
        if(not self.table_exists("web_audit")):
            self.create_table("""
            CREATE TABLE IF NOT EXISTS web_audit (
                id integer PRIMARY KEY AUTOINCREMENT,
                added datetime,
                actor text,
                role text,
                action text,
                instance text,
                details text,
                ip text
            );""")
                  
        
        self.create_table("""
            CREATE TABLE IF NOT EXISTS maintenance (
                key text PRIMARY KEY,
                value text
            );""")

        # Indexes for what's looked up all the time: a player's latest connect
        # (every chat line), the log and chat pages, stats, the Connections
        # page, and the cleanup's date cut-offs.
        for index_sql in (
            "CREATE INDEX IF NOT EXISTS idx_connections_player ON connections (player, added)",
            "CREATE INDEX IF NOT EXISTS idx_connections_added ON connections (added)",
            "CREATE INDEX IF NOT EXISTS idx_connections_slot ON connections (instance, player_id, added)",
            "CREATE INDEX IF NOT EXISTS idx_connections_ip ON connections (ip)",
            "CREATE INDEX IF NOT EXISTS idx_logs_added ON logs (added)",
            "CREATE INDEX IF NOT EXISTS idx_logs_instance ON logs (instance, added)",
            "CREATE INDEX IF NOT EXISTS idx_chatter_added ON chatter (added)",
            "CREATE INDEX IF NOT EXISTS idx_chatter_instance ON chatter (instance COLLATE NOCASE, added)",
            "CREATE INDEX IF NOT EXISTS idx_chatter_player ON chatter (player COLLATE NOCASE, added)",
            "CREATE INDEX IF NOT EXISTS idx_frags_added ON frags (added)",
            "CREATE INDEX IF NOT EXISTS idx_frags_fragger ON frags (fragger)",
            "CREATE INDEX IF NOT EXISTS idx_frags_fragged ON frags (fragged)",
            "CREATE INDEX IF NOT EXISTS idx_player_info_player ON player_info (player, added)",
            "CREATE INDEX IF NOT EXISTS idx_processes_instance ON processes (instance, name)",
            "CREATE INDEX IF NOT EXISTS idx_web_audit_added ON web_audit (added)",
        ):
            self.create_table(index_sql)

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