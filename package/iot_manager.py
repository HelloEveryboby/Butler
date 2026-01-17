# -*- coding: utf-8 -*-
"""
iot_manager.py

This module provides a centralized manager for handling communication with IoT devices
using the MQTT protocol. It is designed to be a standalone component that can be
integrated into the Butler system to act as the "brain" for controlling various
hardware "bodies" like STM32 microcontrollers.

Features:
- Connects to an MQTT broker.
- Provides a simple interface to publish commands to specific device topics.
- Formats commands into a standardized JSON payload.
- Handles MQTT connection logic in the background.

To use this module, you would typically:
1. Instantiate the IoTManager.
2. Call the `send_command` method with a target device_id and a command payload.

Example:
    # This code would be in the main Butler application or an intent handler.
    # from package.iot_manager import IoTManager

    # Initialize the manager
    # iot_manager = IoTManager(broker_host="your_mqtt_broker_ip")

    # Send a command to turn on an LED on a device named 'stm32-led-1'
    # iot_manager.send_command(
    #     device_id="stm32-led-1",
    #     command="set_led",
    #     value="on"
    # )
"""
import paho.mqtt.client as mqtt
import json
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class IoTManager:
    """
    Manages the connection and communication with IoT devices via MQTT.
    """
    def __init__(self, broker_host="localhost", broker_port=1883, client_id="butler_brain"):
        """
        Initializes the IoTManager and connects to the MQTT broker.

        Args:
            broker_host (str): The hostname or IP address of the MQTT broker.
            broker_port (int): The port of the MQTT broker.
            client_id (str): The unique client ID for this connection.
        """
        self.broker_host = broker_host
        self.broker_port = broker_port
        self.client_id = client_id

        self.client = mqtt.Client(client_id=self.client_id)
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect

        self._connect()

    def _connect(self):
        """
        Establishes the connection to the MQTT broker and starts the network loop.
        """
        try:
            self.client.connect(self.broker_host, self.broker_port, 60)
            self.client.loop_start()  # Starts a background thread to handle network traffic
            logging.info(f"Attempting to connect to MQTT broker at {self.broker_host}:{self.broker_port}")
        except ConnectionRefusedError:
            logging.error(f"Connection to MQTT broker at {self.broker_host}:{self.broker_port} was refused.")
        except OSError as e:
            logging.error(f"A network error occurred: {e}")
        except Exception as e:
            logging.error(f"An unexpected error occurred during connection: {e}")

    def _on_connect(self, client, userdata, flags, rc):
        """
        Callback function for when the client connects to the broker.
        """
        if rc == 0:
            logging.info("Successfully connected to MQTT Broker!")
        else:
            logging.error(f"Failed to connect to MQTT Broker, return code {rc}")

    def _on_disconnect(self, client, userdata, rc):
        """
        Callback function for when the client disconnects from the broker.
        """
        if rc != 0:
            logging.warning("Unexpected disconnection from MQTT Broker. Will attempt to reconnect.")

    def send_command(self, device_id: str, command: str, value):
        """
        Publishes a command to a specific IoT device.

        Args:
            device_id (str): The unique identifier of the target device.
            command (str): The command to be executed (e.g., "set_led", "read_sensor").
            value: The value associated with the command (e.g., "on", 1, {"temp": 25.5}).
        """
        if not self.client.is_connected():
            logging.error("Cannot send command: MQTT client is not connected.")
            return

        # Define the topic based on a standardized convention
        topic = f"devices/{device_id}/command"

        # Structure the payload in a consistent JSON format
        payload = {
            "command": command,
            "value": value
        }

        try:
            # Convert the dictionary to a JSON string
            payload_str = json.dumps(payload)

            # Publish the message
            result = self.client.publish(topic, payload_str)

            # Check if the message was successfully sent
            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                logging.info(f"Successfully sent command to topic '{topic}': {payload_str}")
            else:
                logging.error(f"Failed to send command to topic '{topic}'. Return code: {result.rc}")

        except TypeError as e:
            logging.error(f"Error serializing payload to JSON: {e}")
        except Exception as e:
            logging.error(f"An unexpected error occurred while sending command: {e}")

    def disconnect(self):
        """
        Stops the network loop and disconnects from the broker gracefully.
        """
        logging.info("Disconnecting from MQTT broker.")
        self.client.loop_stop()
        self.client.disconnect()

# Example of how this class could be used:
if __name__ == '__main__':
    # This block is for demonstration and testing purposes.
    # It will only run when the script is executed directly.

    # --- IMPORTANT ---
    # To run this test, you need an MQTT broker running.
    # You can easily start one with Docker:
    # docker run -it -p 1883:1883 -p 9001:9001 eclipse-mosquitto

    import time

    logging.info("Starting IoT Manager demonstration.")
    # Replace "localhost" with your broker's IP if it's not running on the same machine.
    iot_manager = IoTManager(broker_host="localhost")

    # Give it a moment to connect
    time.sleep(2)

    # Example 1: Send a command to turn on an LED
    print("\n--- Sending command to turn ON LED ---")
    iot_manager.send_command(device_id="stm32-led-1", command="set_led", value="on")
    time.sleep(1)

    # Example 2: Send a command to turn off an LED
    print("\n--- Sending command to turn OFF LED ---")
    iot_manager.send_command(device_id="stm32-led-1", command="set_led", value="off")
    time.sleep(1)

    # Example 3: Send a command with a numerical value
    print("\n--- Sending command to set brightness ---")
    iot_manager.send_command(device_id="stm32-led-1", command="set_brightness", value=85)
    time.sleep(1)

    # Clean up
    iot_manager.disconnect()
    logging.info("IoT Manager demonstration finished.")
