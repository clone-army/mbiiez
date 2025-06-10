from mbiiez.db import db

class controller:

    controller_bag = {}

    def __init__(self, instance = None):

        conn = db().connect()
        cur = conn.cursor()  
        
        self.controller_bag['instance'] = instance
    
        q = '''
           
        select 
        c.player_id,
        c.player,
        c.class_id,
        c.class_name, 
        c.ip,
        c.model
        
        from active_connections C

        where instance = "''' + instance + '''" 

        order by c.player_id

        ;'''
        
        cur.execute(q)
        players = cur.fetchall()

        self.controller_bag['players'] = players
    