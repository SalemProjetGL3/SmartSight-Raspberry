import cv2
import onnxruntime as ort
import numpy as np
import time
import os
import paho.mqtt.client as mqtt # <-- MQTT ADDITION
import json                       # <-- MQTT ADDITION

# --- MQTT Configuration ---  
BROKER_ADDRESS = "localhost"  # Use your Pi's IP if the broker is on another machine
BROKER_PORT = 1883
MQTT_TOPIC = "vision/data"
# --- End of MQTT Configuration ---

# Load model
session = ort.InferenceSession("yolo_nas_s.onnx")

CLASS_NAMES = [
    "person", "bicycle", "car", "motorcycle", "airplane", "bus", "train", "truck", "boat",
    "traffic light", "fire hydrant", "stop sign", "parking meter", "bench", "bird", "cat",
    "dog", "horse", "sheep", "cow", "elephant", "bear", "zebra", "giraffe", "backpack",
    "umbrella", "handbag", "tie", "suitcase", "frisbee", "skis", "snowboard", "sports ball",
    "kite", "baseball bat", "baseball glove", "skateboard", "surfboard", "tennis racket",
    "bottle", "wine glass", "cup", "fork", "knife", "spoon", "bowl", "banana", "apple",
    "sandwich", "orange", "broccoli", "carrot", "hot dog", "pizza", "donut", "cake", "chair",
    "couch", "potted plant", "bed", "dining table", "toilet", "tv", "laptop", "mouse", "remote",
    "keyboard", "cell phone", "microwave", "oven", "toaster", "sink", "refrigerator", "book",
    "clock", "vase", "scissors", "teddy bear", "hair drier", "toothbrush"
]

def preprocess_image(image, input_size=(640, 640)):
    orig_image = image.copy()
    orig_height, orig_width = image.shape[:2]

    image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    resized = cv2.resize(image, input_size)

    input_tensor = resized.transpose(2, 0, 1).astype(np.float32) / 255.0
    input_tensor = np.expand_dims(input_tensor, axis=0)

    return orig_image, input_tensor, (orig_width, orig_height)

def process_output(outputs, confidence_threshold=0.5, orig_size=None):
    boxes = outputs[0].squeeze(0)  # [N, 4]
    class_scores = outputs[1].squeeze(0)  # [N, 80]

    scores = np.max(class_scores, axis=1)
    class_ids = np.argmax(class_scores, axis=1)

    mask = scores > confidence_threshold
    boxes = boxes[mask]
    scores = scores[mask]
    class_ids = class_ids[mask]

    if boxes.shape[0] == 0:
        return [], [], []

    if orig_size:
        orig_width, orig_height = orig_size
        scale_x = orig_width / 640
        scale_y = orig_height / 640
        boxes[:, [0, 2]] *= scale_x
        boxes[:, [1, 3]] *= scale_y

    return boxes, scores, class_ids.astype(int)

def apply_nms(boxes, scores, class_ids, iou_threshold=0.5):
    if len(boxes) == 0:
        return [], [], []

    boxes_wh = np.zeros_like(boxes)
    boxes_wh[:, 0] = boxes[:, 0]
    boxes_wh[:, 1] = boxes[:, 1]
    boxes_wh[:, 2] = boxes[:, 2] - boxes[:, 0]  # width
    boxes_wh[:, 3] = boxes[:, 3] - boxes[:, 1]  # height

    indices = cv2.dnn.NMSBoxes(boxes_wh.tolist(), scores.tolist(), 0.5, iou_threshold)
    if len(indices) > 0:
        indices = indices.flatten()
        return boxes[indices], scores[indices], class_ids[indices]
    else:
        return [], [], []

def draw_boxes(image, boxes, scores, class_ids):
    for box, score, class_id in zip(boxes, scores, class_ids):
        x1, y1, x2, y2 = box.astype(int)
        label = f"{CLASS_NAMES[class_id]}: {score:.2f}"
        cv2.rectangle(image, (x1, y1), (x2, y2), (0, 255, 0), 2)
        cv2.putText(image, label, (x1, y1 - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
    return image

# Decision Logic Integration
def is_side_clear(labels, side, threshold=0.05):
    total_area = 0
    for _, x_center, _, width, height in labels:
        if side == 'left' and x_center < 0.4:
            total_area += width * height
        elif side == 'right' and x_center > 0.6:
            total_area += width * height
    return total_area < threshold

def decide_direction(labels):
    left = right = middle = 0
    for label in labels:
        _, x_center, _, _, _ = label
        if 0.4 <= x_center <= 0.6:
            middle += 1
        elif x_center < 0.4:
            left += 1
        else:
            right += 1

    if middle > 0:
        left_clear = is_side_clear(labels, 'right')
        right_clear = is_side_clear(labels, 'left')

        if left < right and left_clear:
            return "right"
        elif right_clear:
            return "left"
        elif left_clear:
            return "right"
        else:
            return "stop"
    else:
        return "straight"

# Capture, Inference and Decision Loop
def capture_and_infer(mqtt_client, save_dir="results"): # (mqtt_client passed in)
    os.makedirs(save_dir, exist_ok=True)
    cap = cv2.VideoCapture(0)

    if not cap.isOpened():
        print("❌ Cannot open camera")
        return

    print("📷 Running inference. Press Ctrl+C to stop.")
    count = 0
    last_decision_time = time.time()

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                print("❌ Failed to grab frame")
                break

            orig_image, input_tensor, orig_size = preprocess_image(frame)
            input_name = session.get_inputs()[0].name
            outputs = session.run(None, {input_name: input_tensor})

            boxes, scores, class_ids = process_output(outputs, 0.5, orig_size)
            boxes, scores, class_ids = apply_nms(boxes, scores, class_ids)

            # Save result image
            result_image = draw_boxes(orig_image, boxes, scores, class_ids)
            filename = os.path.join(save_dir, f"result_{count}.jpg")
            # cv2.imwrite(filename, result_image) # You may want to comment this out to save disk space
            # print(f"✅ Saved {filename}")
            count += 1

            # Every second make a decision and publish it
            now = time.time()
            if now - last_decision_time >= 1:
                norm_labels = []
                for box in boxes:
                    x1, y1, x2, y2 = box
                    width = x2 - x1
                    height = y2 - y1
                    x_center = x1 + width / 2
                    y_center = y1 + height / 2

                    # Normalize to [0, 1]
                    x_center /= orig_size[0]
                    y_center /= orig_size[1]
                    width /= orig_size[0]
                    height /= orig_size[1]

                    norm_labels.append((0, x_center, y_center, width, height))

                decision = decide_direction(norm_labels)
                print(f"🧭 Decision: {decision}")

                # ---- THIS IS THE NEW MQTT PUBLISHING PART ---- # <-- MQTT ADDITION
                payload = json.dumps({"timestamp": now, "decision": decision})
                mqtt_client.publish(MQTT_TOPIC, payload)
                # ---------------------------------------------- #

                last_decision_time = now

    except KeyboardInterrupt:
        print("🛑 Stopped by user")

    finally:
        cap.release()

# Run the main loop
if __name__ == "__main__":
    # --- Initialize and connect MQTT Client --- # <-- MQTT ADDITION
    client = mqtt.Client()
    try:
        client.connect(BROKER_ADDRESS, BROKER_PORT, 60)
        client.loop_start() # Starts a background thread for publishing
        print("✅ MQTT Client Connected and running in background.")
    except Exception as e:
        print(f"❌ Failed to connect MQTT Client: {e}")
        exit()
    # ----------------------------------------- #

    # Call the main inference function, passing the client to it
    capture_and_infer(client) # <-- MQTT ADDITION (pass client)

    # --- Cleanly disconnect MQTT Client --- # <-- MQTT ADDITION
    print("Disconnecting MQTT Client...")
    client.loop_stop()
    client.disconnect()
    # ------------------------------------ #
