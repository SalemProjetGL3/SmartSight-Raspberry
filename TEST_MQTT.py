import paho.mqtt.client as mqtt
import time
import json
import random
import socket # Needed to potentially show the IP

# --- Configuration ---
BROKER_ADDRESS = "localhost" # Connect to the broker running on THIS machine
BROKER_PORT = 1883
MQTT_USERNAME = None # Default Mosquitto install has no authentication
MQTT_PASSWORD = None
USE_TLS = False

TOPIC = "vision/data" # The topic to publish messages to
CLIENT_ID = "windows_publisher_sim"
PUBLISH_INTERVAL_SEC = 2

# --- Helper to find local IP (useful for telling the phone where to connect) ---
def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # Doesn't have to be reachable
        s.connect(('192.168.1.1', 1)) # Use a common gateway pattern
        IP = s.getsockname()[0]
    except Exception:
        try:
            IP = socket.gethostbyname(socket.gethostname())
        except Exception:
            IP = '127.0.0.1' # Fallback
    finally:
        s.close()
    return IP

# --- Dummy Data Generation ---
def get_simulated_data():
    obj_type = random.choice(["dar", "koucha", "kalb", "kattous"])
    data = {
        "timestamp": time.time(),
        "object_detected": obj_type,
        "confidence": round(random.uniform(0.6, 0.99), 2),
        "position_x": random.randint(0, 640),
        "position_y": random.randint(0, 480),
    }
    return json.dumps(data) # Publish as JSON string

# --- MQTT Callbacks ---
def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("Publisher Connected to MQTT Broker!")
    else:
        print(f"Publisher Failed to connect, return code {rc}")

def on_disconnect(client, userdata, rc):
    print(f"Publisher Disconnected with result code {rc}")

# --- Main Script ---
print("Attempting to find local IP address...")
local_ip = get_local_ip()
print(f"*** Your Windows PC's approximate local IP is: {local_ip} ***")
print("*** Use THIS IP address in the MQTT app on your phone. ***\n")


client = mqtt.Client(client_id=CLIENT_ID)

if MQTT_USERNAME and MQTT_PASSWORD:
    client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)

if USE_TLS:
    client.tls_set(tls_version=mqtt.ssl.PROTOCOL_TLS)

client.on_connect = on_connect
client.on_disconnect = on_disconnect

try:
    print(f"Publisher connecting to broker at {BROKER_ADDRESS}:{BROKER_PORT}...")
    client.connect(BROKER_ADDRESS, BROKER_PORT, 60)
except Exception as e:
    print(f"Error connecting publisher to broker: {e}")
    exit(1)

client.loop_start() # Start background thread for handling network traffic

try:
    while True:
        message = get_simulated_data()
        result = client.publish(TOPIC, message)
        status = result[0]
        if status == 0:
            # Don't print every time to keep output clean
            # print(f"Sent `{message}` to topic `{TOPIC}`")
            pass
        else:
            print(f"Failed to send message to topic {TOPIC}")

        time.sleep(PUBLISH_INTERVAL_SEC)

except KeyboardInterrupt:
    print("Publisher stopping...")
    client.loop_stop()
    client.disconnect()
    print("Publisher disconnected.")