from flask import Blueprint, request, jsonify
from mbiiez.db import db
from mbiiez.instance import instance as MBInstance

chat_api = Blueprint('chat_api', __name__)

@chat_api.route('/chat/data', methods=['GET'])
def chat_data():
    instance = request.args.get('instance')
    conn = db().connect()
    cur = conn.cursor()
    if instance:
        q = "SELECT * FROM chatter WHERE instance = ? ORDER BY added DESC LIMIT 100"
        cur.execute(q, (instance,))
    else:
        q = "SELECT * FROM chatter ORDER BY added DESC LIMIT 100"
        cur.execute(q)
    rows = cur.fetchall()
    # Reverse for chat order (oldest at top)
    messages = list(reversed(rows))
    return jsonify(messages)

@chat_api.route('/chat/send', methods=['POST'])
def chat_send():
    data = request.get_json()
    instance = data.get('instance')
    message = data.get('message')
    if not instance or not message:
        return jsonify({'error': 'Missing instance or message'}), 400
    inst = MBInstance(instance)
    inst.say(message)
    return jsonify({'success': True})
