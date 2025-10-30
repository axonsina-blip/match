
from flask import Flask, jsonify, render_template
import sqlite3
from flask_socketio import SocketIO, emit
from database import init_db
from worker import start_worker, update_matches_db
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key' # Replace with a strong secret key
socketio = SocketIO(app)

# Global counter for connected users
connected_users = 0

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/matches')
def get_matches():
    conn = sqlite3.connect('matches.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM matches")
    matches = [dict(row) for row in c.fetchall()]
    conn.close()
    return jsonify(matches)

@socketio.on('connect')
def handle_connect():
    global connected_users
    connected_users += 1
    emit('user_count', {'count': connected_users}, broadcast=True)
    print(f"Client connected. Total users: {connected_users}")

@socketio.on('disconnect')
def handle_disconnect():
    global connected_users
    connected_users -= 1
    emit('user_count', {'count': connected_users}, broadcast=True)
    print(f"Client disconnected. Total users: {connected_users}")

if __name__ == "__main__":
    init_db()
    # Check if the database is empty
    conn = sqlite3.connect('matches.db')
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM matches")
    count = c.fetchone()[0]
    conn.close()
    update_matches_db()    

    if count == 0:
        print("Database is empty. Populating it for the first time...")

    start_worker()
    socketio.run(app, debug=True)
