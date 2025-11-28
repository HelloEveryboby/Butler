from flask import Flask, render_template
from flask_socketio import SocketIO, emit
import threading
import time

app = Flask(__name__)
socketio = SocketIO(app)
jarvis_instance = None

def set_jarvis_instance(jarvis):
    global jarvis_instance
    jarvis_instance = jarvis

@app.route('/')
def index():
    return render_template('index.html')

@socketio.on('message')
def handle_message(message):
    if jarvis_instance:
        command = message['data']

        # Define a wrapper function for Jarvis's command handler
        def jarvis_handler_wrapper():
            # This is a simplified approach. You might need a more sophisticated
            # way to capture output from Jarvis, especially if it's asynchronous.
            # For now, we'll assume ui_print is the primary way Jarvis gives feedback.

            # We need a way to intercept calls to ui_print.
            # Let's override it for the duration of this call.
            original_ui_print = jarvis_instance.ui_print

            def web_ui_print(text, tag='ai_response', response_id=None):
                socketio.emit('response', {'data': text})
                # Also call the original to see it in the console
                original_ui_print(text, tag, response_id)

            jarvis_instance.ui_print = web_ui_print

            try:
                # Assuming handle_user_command is the entry point for processing commands.
                # The 'programs' argument might need to be sourced correctly.
                jarvis_instance.handle_user_command(command, {})
            finally:
                # Restore the original ui_print function
                jarvis_instance.ui_print = original_ui_print

        # Run the Jarvis command handler in a separate thread
        # to avoid blocking the web server.
        thread = threading.Thread(target=jarvis_handler_wrapper)
        thread.start()
    else:
        emit('response', {'data': 'Jarvis not initialized'})

def run_web_server():
    socketio.run(app, host='0.0.0.0', port=5000)