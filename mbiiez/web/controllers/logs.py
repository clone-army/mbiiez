import math
from mbiiez.db import db

class controller:

    controller_bag = {}

    def __init__(self, instance = None, page = 1, per_page = 100, search=None):
    
            conn = db().connect()
            cur = conn.cursor()  
            
            where_clauses = []
            params = []

            if instance is not None and instance.lower() != "all":
                where_clauses.append('instance = ?')
                params.append(instance)
            if search:
                where_clauses.append('log_line LIKE ?')
                params.append(f'%{search}%')

            where_sql = ''
            if where_clauses:
                where_sql = 'WHERE ' + ' AND '.join(where_clauses)

            # Count query
            q = f'''SELECT COUNT(*) as total FROM logs {where_sql};'''
            cur.execute(q, params)
            totals = cur.fetchone()

            # Total number of log lines
            self.controller_bag['total'] = int(totals['total'])
            self.controller_bag['pages'] = math.ceil(int(totals['total']) / int(per_page)) 
            
            offset = (int(per_page) * int(int(page)-1))
            
            # Data query
            q = f'''SELECT * FROM logs {where_sql} ORDER BY added DESC LIMIT ? OFFSET ?;'''
            params_data = params + [per_page, offset]
            cur.execute(q, params_data)
            self.controller_bag['rows'] = cur.fetchall()
            self.controller_bag['instance'] = instance
            self.controller_bag['page'] = page
            self.controller_bag['search'] = search
            
            
            if(instance == None or instance.lower() == "all"):
                self.controller_bag['instance'] = "All"