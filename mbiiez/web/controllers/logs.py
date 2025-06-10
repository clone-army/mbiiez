import math
from mbiiez.db import db

class controller:

    controller_bag = {}

    def __init__(self, instance = None, page = 1, per_page = 100):
    
            conn = db().connect()
            cur = conn.cursor()  
            
            if(instance == None or instance.lower() == "all"):
                q = ''' SELECT COUNT(*) as total FROM logs ; '''
            else:
                q = ''' SELECT COUNT(*) as total FROM logs where instance = "''' + instance + '''"'''
                       
            cur.execute(q)
            totals = cur.fetchone()
            
            # Total number of log lines
            self.controller_bag['total'] = int(totals['total'])
            self.controller_bag['pages'] = math.ceil(int(totals['total']) / int(per_page)) 
            
            offset = (int(per_page) * int(int(page)-1))
            
            if(instance == None or instance.lower() == "all"):
                q = ''' SELECT * FROM logs ORDER BY added DESC LIMIT ''' + str(per_page) + ''' OFFSET ''' + str(offset) + ''';'''
            else:
                q = ''' SELECT * FROM logs where instance = "''' + instance + '''" ORDER BY added DESC LIMIT ''' + str(per_page) + ''' OFFSET ''' + str(offset) + ''';'''
            
            cur.execute(q)
            self.controller_bag['rows'] = cur.fetchall()
            self.controller_bag['instance'] = instance
            self.controller_bag['page'] = page
            
            
            if(instance == None or instance.lower() == "all"):
                self.controller_bag['instance'] = "All"            