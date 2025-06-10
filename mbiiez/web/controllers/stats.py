from mbiiez.db import db

class controller:

    controller_bag = {}

    def __init__(self, instance = None):
    
            conn = db().connect()
            cur = conn.cursor()  
            
            self.controller_bag['instance'] = instance
            
            # Fetchs either all connections including instance 
            if(instance == None):
                q = ''' SELECT count(*) as connections, instance, strftime('%d', added) as date FROM connections WHERE type = "CONNECT" GROUP BY strftime('%Y %m %d', added), instance ORDER BY added DESC LIMIT 30; '''
            else:
                q = ''' SELECT count(*) as connections, instance, strftime('%d', added) as date FROM connections WHERE type = "CONNECT" and instance = "''' + instance + '''" GROUP BY strftime('%Y %m %d', added) ORDER BY added DESC LIMIT 30; '''
            
            cur.execute(q)
            
            self.controller_bag['connections'] = cur.fetchall()
            
            if(instance == None):
                q = ''' SELECT count(*) as connections, player as player FROM connections WHERE player <> "Padawan" and player <> "" and added >= date('now','-30 days') GROUP BY player order by connections DESC LIMIT 10; '''
            else:
                q = ''' SELECT count(*) as connections, player as player FROM connections WHERE instance = "''' + instance + '''" AND player <> "Padawan" and player <> "" and added >= date('now','-30 days') GROUP BY player order by connections DESC LIMIT 10; '''
            
            cur.execute(q)
            
            self.controller_bag['players'] = cur.fetchall()
                        
            
            if(instance == None):
                self.controller_bag['instance'] = "All"
            
            
            
            