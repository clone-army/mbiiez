import math
from mbiiez.db import db

class controller:

    controller_bag = {}

    def __init__(self, instance = None, page = 1, per_page = 100):
    
            conn = db().connect()
            cur = conn.cursor()  
            
            q = '''
               
            SELECT 
            CAST(SUM(Cast ((
                JulianDay(D.added) - JulianDay(C.added )
            ) * 24 As Integer)) as Integer) / 24 / 60 / 60 / 60 as hours,

            c.player 
            from CONNECTIONS C 

            JOIN CONNECTIONS D
            ON C.ADDED < D.ADDED

            WHERE 
            C.type="CONNECT"
            AND
            D.type = "DISCONNECT"
     

            GROUP BY C.player

            ORDER BY hours DESC '''
                       
            cur.execute(q)
            players = cur.fetchall()
            
            self.controller_bag['players'] = players
                      