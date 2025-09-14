import cv2
import mediapipe as mp
import numpy as np
import time

# --- Initialization ---
# Initialize MediaPipe Hands for hand tracking
mp_hands = mp.solutions.hands
# Configure Hands with confidence thresholds to filter out weak detections
hands = mp_hands.Hands(min_detection_confidence=0.7, min_tracking_confidence=0.7)
# Utility for drawing hand landmarks and connections
mp_drawing = mp.solutions.drawing_utils

# --- Webcam Setup ---
# Attempt to open the default webcam (index 0)
cap = cv2.VideoCapture(0)
if not cap.isOpened():
    print("Error: Could not open webcam.")
    exit()

# --- Gesture Recognition Variables ---
# Stores the name of the last recognized gesture
gesture = None
# Stores the previous position of the wrist for swipe detection
prev_x, prev_y = -1, -1
# Timestamp of the last recognized gesture to implement a cooldown
last_gesture_time = 0
# Cooldown period in seconds to prevent rapid, repeated gesture recognition
gesture_cooldown = 1.0

def get_static_gesture(hand_landmarks):
    """
    Recognizes static gestures (Fist, Pinch) from hand landmarks.
    Args:
        hand_landmarks: The detected landmarks for a single hand.
    Returns:
        A string with the name of the gesture, or None if no gesture is detected.
    """
    landmarks = hand_landmarks.landmark

    # --- 1. Fist Gesture (Stop) ---
    # A fist is detected if the tips of the 4 fingers are below their respective second joints (PIP).
    finger_tips_indices = [8, 12, 16, 20]  # Index, Middle, Ring, Pinky tips
    pip_joints_indices = [6, 10, 14, 18]   # Index, Middle, Ring, Pinky PIP joints

    is_fist = True
    for tip_idx, pip_idx in zip(finger_tips_indices, pip_joints_indices):
        # In the image, a lower y-coordinate means a higher position.
        if landmarks[tip_idx].y > landmarks[pip_idx].y:
            is_fist = False
            break
    if is_fist:
        return "Stop (Fist)"

    # --- 2. Pinch Gesture (Click) ---
    # A pinch is detected if the distance between the thumb tip and index finger tip is small.
    thumb_tip = landmarks[4]
    index_tip = landmarks[8]
    # Calculate Euclidean distance in normalized coordinates
    distance = np.sqrt((thumb_tip.x - index_tip.x)**2 + (thumb_tip.y - index_tip.y)**2)
    # The threshold is based on normalized coordinates, may need tuning
    if distance < 0.05:
        return "Click (Pinch)"

    return None  # No static gesture detected

# --- Main Loop ---
print("Starting gesture recognition. Press 'q' to quit.")
while cap.isOpened():
    # Read a frame from the webcam
    success, image = cap.read()
    if not success:
        print("Ignoring empty camera frame.")
        continue

    # Flip the image horizontally for a natural, selfie-view display
    image = cv2.flip(image, 1)

    # Convert the BGR image to RGB, as MediaPipe requires RGB input
    rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

    # Process the image with MediaPipe Hands to detect hand landmarks
    results = hands.process(rgb_image)

    current_time = time.time()
    new_gesture_detected = False

    # --- Hand Landmark Processing ---
    if results.multi_hand_landmarks:
        # Process the first detected hand
        hand_landmarks = results.multi_hand_landmarks[0]

        # Draw the landmarks on the image for visualization
        mp_drawing.draw_landmarks(image, hand_landmarks, mp_hands.HAND_CONNECTIONS)

        # --- Gesture Recognition Logic ---
        # First, check for static gestures (Fist, Pinch)
        static_gesture = get_static_gesture(hand_landmarks)

        if static_gesture and (current_time - last_gesture_time > gesture_cooldown):
            gesture = static_gesture
            last_gesture_time = current_time
            new_gesture_detected = True

        # If no static gesture, check for dynamic (swipe) gestures
        else:
            # Use the wrist landmark (landmark 0) to track hand position
            wrist = hand_landmarks.landmark[0]
            current_x = int(wrist.x * image.shape[1])
            current_y = int(wrist.y * image.shape[0])

            if prev_x != -1:
                dx = current_x - prev_x
                dy = current_y - prev_y

                # Check for significant movement (swipe)
                swipe_threshold = 50
                if current_time - last_gesture_time > gesture_cooldown:
                    if abs(dx) > swipe_threshold and abs(dx) > abs(dy):
                        gesture = "Swipe Right" if dx > 0 else "Swipe Left"
                        last_gesture_time = current_time
                        new_gesture_detected = True
                    elif abs(dy) > swipe_threshold and abs(dy) > abs(dx):
                        # Note: In OpenCV, y increases downwards
                        gesture = "Swipe Down" if dy > 0 else "Swipe Up"
                        last_gesture_time = current_time
                        new_gesture_detected = True

            prev_x, prev_y = current_x, current_y

    else:
        # If no hands are detected, reset the swipe tracking
        prev_x, prev_y = -1, -1
        gesture = None

    # --- Display Results ---
    # Print the new gesture to the console when it's recognized
    if new_gesture_detected and gesture:
        print(f"Recognized Gesture: {gesture}")

    # Display the current gesture on the video feed
    if gesture:
        cv2.putText(image, gesture, (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2, cv2.LINE_AA)

    # Show the image in a window
    cv2.imshow('Hand Gesture Recognition', image)

    # Exit the loop if the 'q' key is pressed
    if cv2.waitKey(5) & 0xFF == ord('q'):
        break

# --- Cleanup ---
print("Exiting...")
cap.release()
cv2.destroyAllWindows()
