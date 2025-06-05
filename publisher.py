import time
import json
import socket
import cv2
import numpy as np
import paho.mqtt.client as mqtt
from picamera2 import Picamera2
import torch
from super_gradients.training import models
from transformers import pipeline
import threading
from queue import Queue
import logging

import helpers.MQTTutils as mqtt_utils
import models.midas as midas_model
import models.yoloNAS as yolo_nas_model


# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Configuration ---
# MQTT Settings - ADJUST THESE!

BROKER_ADDRESS = "localhost"  # Replace with your MQTT broker's IP address (normalement takhtef fl localhost khater l broker local)
BROKER_PORT = 1883

MQTT_TOPIC_CV_RESULTS = "vision/results"
MQTT_CLIENT_ID = f"rpi_cv_publisher_{socket.gethostname()}"
MQTT_USERNAME = None  # Set if your broker requires authentication (doesn't lol)
MQTT_PASSWORD = None

# provide the ipv4 address to input to the phone app
ipv4=mqtt_utils.get_local_ip()  # This will return the local IP address of the Raspberry Pi
print(f"Local IP address for MQTT: {ipv4}")
print(f"Topic: {MQTT_TOPIC_CV_RESULTS}")

# Camera Settings
CAMERA_RESOLUTION = (1280, 720)  # Balanced resolution for performance
CAMERA_FRAMERATE = 10           # Conservative framerate for processing
PREVIEW_WINDOW = False          # Set to True to show preview (requires display)

# Model Settings
CONFIDENCE_THRESHOLD = 0.5      # Minimum confidence for object detection
DEPTH_MODEL_SIZE = "small"      # Options: "small", "base", "large"


class CVProcessor:
    def __init__(self):
        self.yolo_model = None
        self.depth_model = None
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        logger.info(f"Using device: {self.device}")
        
    def load_models(self):
        """Load YOLO NAS S and MIDAS models"""
        try:
            logger.info("Loading YOLO NAS S model...")
            # Load YOLO NAS S model
            # self.yolo_model = ...
            logger.info("YOLO NAS S model loaded successfully")

            logger.info("Loading MIDAS depth estimation model...")
            # Load MIDAS depth estimation model
            # self.depth_model = ...
            logger.info("MIDAS model loaded successfully")

            return True
            
        except Exception as e:
            logger.error(f"Error loading models: {e}")
            return False
    

    


class MQTTPublisher:
    def __init__(self):
        self.client = None
        self.connected = False
        
    def setup_mqtt(self):
        """Setup MQTT client"""
        try:
            self.client = mqtt.Client(client_id=MQTT_CLIENT_ID)
            
            if MQTT_USERNAME and MQTT_PASSWORD:
                self.client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
            
            self.client.on_connect = self.on_connect
            self.client.on_disconnect = self.on_disconnect
            self.client.on_publish = self.on_publish
            
            logger.info(f"Connecting to MQTT broker: {BROKER_ADDRESS}:{BROKER_PORT}")
            self.client.connect(BROKER_ADDRESS, BROKER_PORT, 60)
            self.client.loop_start()
            
            # Wait for connection
            timeout = 10
            while not self.connected and timeout > 0:
                time.sleep(0.1)
                timeout -= 0.1
                
            return self.connected
            
        except Exception as e:
            logger.error(f"Error setting up MQTT: {e}")
            return False
    
    # MQTT Callbacks
    def on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            self.connected = True
            logger.info(f"Successfully connected to MQTT Broker: {BROKER_ADDRESS}")
        else:
            logger.error(f"Failed to connect to MQTT Broker, return code {rc}")
    
    # MQTT Disconnect Callback
    def on_disconnect(self, client, userdata, rc):
        self.connected = False
        logger.info(f"Disconnected from MQTT Broker with result code {rc}")
    
    # MQTT Publish Callback
    def on_publish(self, client, userdata, mid):
        pass  # Uncomment next line for verbose logging
        # logger.debug(f"Message published with MID: {mid}")
    
    def publish_results(self, results):
        """Publish CV results to MQTT topic"""
        if self.connected:
            try:
                payload_json = json.dumps(results, indent=None, separators=(',', ':'))
                result = self.client.publish(MQTT_TOPIC_CV_RESULTS, payload_json)
                return result.rc == mqtt.MQTT_ERR_SUCCESS
            except Exception as e:
                logger.error(f"Error publishing results: {e}")
                return False
        return False
    
    def cleanup(self):
        """Cleanup MQTT connection"""
        if self.client and self.connected:
            self.client.loop_stop()
            self.client.disconnect()

def main():
    # Initialize components
    cv_processor = CVProcessor()
    mqtt_publisher = MQTTPublisher()
    picam2 = None
    
    try:
        # Load CV models
        logger.info("Loading computer vision models...")
        if not cv_processor.load_models():
            logger.error("Failed to load CV models. Exiting.")
            return
        
        # Setup MQTT
        logger.info("Setting up MQTT connection...")
        if not mqtt_publisher.setup_mqtt():
            logger.error("Failed to connect to MQTT broker. Exiting.")
            return
        
        # Initialize camera
        logger.info("Initializing camera...")
        picam2 = Picamera2()
        config = picam2.create_still_configuration(
            main={"size": CAMERA_RESOLUTION},
            lores={"size": (640, 360)}, 
            display="lores"
        )
        picam2.configure(config)
        
        if PREVIEW_WINDOW:
            picam2.start_preview()
        
        picam2.start()
        time.sleep(2)  # Allow camera to stabilize
        logger.info("Camera initialized successfully")
        
        logger.info(f"Starting CV processing and MQTT publishing to topic '{MQTT_TOPIC_CV_RESULTS}'...")
        logger.info("Press Ctrl+C to stop...")
        
        frame_count = 0
        total_processing_time = 0
        
        while True:
            start_time = time.time()
            
            # Capture frame
            frame_array = picam2.capture_array("main")
            
            # Run object detection
            detected_objects = cv_processor.run_object_detection(frame_array)
            
            # Run depth estimation if we have detected objects
            if detected_objects:
                results_with_depth = cv_processor.run_depth_estimation(frame_array, detected_objects)
            else:
                results_with_depth = detected_objects
            
            # Prepare payload
            payload = {
                "timestamp": time.time(),
                "device_id": MQTT_CLIENT_ID,
                "frame_resolution": {
                    "width": CAMERA_RESOLUTION[0], 
                    "height": CAMERA_RESOLUTION[1]
                },
                "processing_info": {
                    "model_confidence_threshold": CONFIDENCE_THRESHOLD,
                    "device": str(cv_processor.device)
                },
                "detections": results_with_depth
            }
            
            # Publish results
            if mqtt_publisher.publish_results(payload):
                processing_time = time.time() - start_time
                total_processing_time += processing_time
                frame_count += 1
                
                avg_processing_time = total_processing_time / frame_count
                fps = 1.0 / processing_time if processing_time > 0 else 0
                
                logger.info(f"Frame {frame_count}: {len(results_with_depth)} detections, "
                          f"Processing: {processing_time:.3f}s, FPS: {fps:.1f}, "
                          f"Avg: {avg_processing_time:.3f}s")
            else:
                logger.warning("Failed to publish results")
            
            # Control frame rate
            sleep_duration = max(0, (1.0 / CAMERA_FRAMERATE) - (time.time() - start_time))
            if sleep_duration > 0:
                time.sleep(sleep_duration)
    
    except KeyboardInterrupt:
        logger.info("Stopping publisher...")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
    finally:
        # Cleanup
        logger.info("Cleaning up...")
        if picam2:
            if PREVIEW_WINDOW:
                picam2.stop_preview()
            picam2.stop()
            logger.info("Camera stopped")
        
        mqtt_publisher.cleanup()
        logger.info("MQTT connection closed")
        logger.info("Publisher stopped")

if __name__ == "__main__":
    main()