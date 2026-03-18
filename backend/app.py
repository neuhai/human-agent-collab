try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv optional; use env vars directly if not installed

from flask import Flask, render_template, jsonify
from flask_socketio import SocketIO
from flask_cors import CORS
from routes.session import session_bp
from routes.participant import participant_bp

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'  # Change this in production

# Register blueprints
app.register_blueprint(session_bp)
app.register_blueprint(participant_bp)

# Enable CORS for all routes
CORS(app, resources={r"/api/*": {"origins": "*"}})

# Initialize SocketIO
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# Import handlers after socketio is initialized to avoid circular import
from websocket import handlers
# Register handlers with socketio instance
handlers.register_handlers(socketio)

# Start production service to monitor and complete productions
from services.production_service import start_production_service
start_production_service()

@app.route('/')
def index():
    return render_template('index.html')

# Debug route to list all registered routes
@app.route('/debug/routes')
def list_routes():
    routes = []
    for rule in app.url_map.iter_rules():
        routes.append({
            'endpoint': rule.endpoint,
            'methods': list(rule.methods),
            'rule': str(rule)
        })
    return jsonify({'routes': routes})

if __name__ == '__main__':
    # IMPORTANT:
    # In debug mode, Flask's auto-reloader can spawn multiple processes.
    # Without a Socket.IO message queue (Redis/RabbitMQ), emits coming from HTTP routes
    # may not reach WebSocket clients connected to a different process.
    # Running with use_reloader=False keeps a single process so real-time updates work reliably.
    socketio.run(app, debug=True, use_reloader=False, host='0.0.0.0', port=5000)
