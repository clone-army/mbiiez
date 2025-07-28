from flask import Blueprint, request, jsonify, render_template
from mbiiez.db import db
import time

logs_api = Blueprint('logs_api', __name__)

@logs_api.route('/logs/data', methods=['GET'])
def logs_data():
    tag = request.args.get('tag', None)
    instance = request.args.get('instance', None)
    search = request.args.get('search', '').strip()
    try:
        limit = int(request.args.get('limit', 100))
    except (TypeError, ValueError):
        limit = 100

    q = "SELECT log, added FROM logs WHERE 1=1"
    params = []
    if instance:
        q += " AND LOWER(instance) = LOWER(?)"
        params.append(instance)
    if tag == 'SMOD':
        q += " AND (log LIKE '%SMOD command%' OR log LIKE '%SMOD say:%')"
    elif tag == 'ClientConnect':
        q += " AND log LIKE '%ClientConnect%'"
    elif tag == 'Exception':
        q += " AND (log LIKE 'Exception%' OR log LIKE 'Error%')"
    # Add free text search filter
    if search:
        q += " AND log LIKE ?"
        params.append(f"%{search}%")
    q += " ORDER BY added DESC LIMIT ?"
    params.append(limit)

    conn = db().connect()
    cur = conn.cursor()
    try:
        cur.execute(q, params)
        logs = cur.fetchall()
    except Exception:
        logs = []
    return jsonify([
        {"log_line": row["log"], "added": row["added"]} for row in logs
    ])
