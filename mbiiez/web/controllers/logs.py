import math
from flask import request, jsonify
from mbiiez.db import db

class controller:

    controller_bag = {}

    def __init__(self, instance = None, page = 1, per_page = 100, search=None):
    
            conn = db().connect()
            cur = conn.cursor()  
            
            where_clauses = []
            params = []

            if instance is not None and instance.lower() != "all":
                where_clauses.append('LOWER(instance) = LOWER(?)')
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
                
# Example Flask route for /logs/data
def get_logs_data():
    tag = request.args.get('tag', '')
    limit = int(request.args.get('limit', 100))
    search = request.args.get('search', '').strip()

    conn = db().connect()
    cur = conn.cursor()

    where_clauses = []
    params = []

    if tag:
        where_clauses.append('log_line LIKE ?')
        params.append(f'%{tag}%')
    if search:
        where_clauses.append('log_line LIKE ?')
        params.append(f'%{search}%')

    where_sql = ''
    if where_clauses:
        where_sql = 'WHERE ' + ' AND '.join(where_clauses)

    q = f'''SELECT * FROM logs {where_sql} ORDER BY added DESC LIMIT ?;'''
    params.append(limit)
    cur.execute(q, params)
    rows = cur.fetchall()

    # Adapt to your schema
    return jsonify([
        {'added': row['added'], 'log_line': row['log_line']}
        for row in rows
    ])

# If using Flask, register:
# app.route('/logs/data')(get_logs_data)