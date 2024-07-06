# pip install opencv-python mediapipe pyautogui osascript pyobjc-framework-Quartz
# python Virtual-Mouse-control-using-gesture.py

import cv2
import mediapipe as mp
import pyautogui
import math
from enum import IntEnum
from ctypes import cast, POINTER
import osascript
from google.protobuf.json_format import MessageToDict
from Quartz import CoreGraphics as cg

pyautogui.FAILSAFE = False

mp_drawing = mp.solutions.drawing_utils
mp_hands = mp.solutions.hands

class Gest(IntEnum):
    FIST = 0
    PINKY = 1
    RING = 2
    MID = 4
    LAST3 = 7
    INDEX = 8
    FIRST2 = 12
    LAST4 = 15
    THUMB = 16    
    PALM = 31
    V_GEST = 33
    TWO_FINGER_CLOSED = 34
    PINCH_MAJOR = 35
    PINCH_MINOR = 36

class HLabel(IntEnum):
    MINOR = 0
    MAJOR = 1

class HandRecog:
    def __init__(self, hand_label):
        self.finger = 0
        self.ori_gesture = Gest.PALM
        self.prev_gesture = Gest.PALM
        self.frame_count = 0
        self.hand_result = None
        self.hand_label = hand_label

    def update_hand_result(self, hand_result):
        self.hand_result = hand_result

    def get_signed_dist(self, point):
        sign = -1
        if self.hand_result.landmark[point[0]].y < self.hand_result.landmark[point[1]].y:
            sign = 1
        dist = (self.hand_result.landmark[point[0]].x - self.hand_result.landmark[point[1]].x)**2
        dist += (self.hand_result.landmark[point[0]].y - self.hand_result.landmark[point[1]].y)**2
        dist = math.sqrt(dist)
        return dist*sign

    def get_dist(self, point):
        dist = (self.hand_result.landmark[point[0]].x - self.hand_result.landmark[point[1]].x)**2
        dist += (self.hand_result.landmark[point[0]].y - self.hand_result.landmark[point[1]].y)**2
        dist = math.sqrt(dist)
        return dist

    def get_dz(self, point):
        return abs(self.hand_result.landmark[point[0]].z - self.hand_result.landmark[point[1]].z)

    def set_finger_state(self):
        if self.hand_result is None:
            return

        points = [[8,5,0],[12,9,0],[16,13,0],[20,17,0]]
        self.finger = 0
        self.finger = self.finger | 0
        for idx,point in enumerate(points):
            dist = self.get_signed_dist(point[:2])
            dist2 = self.get_signed_dist(point[1:])
            try:
                ratio = round(dist/dist2,1)
            except:
                ratio = round(dist/0.01,1)
            self.finger = self.finger << 1
            if ratio > 0.5 :
                self.finger = self.finger | 1

    def get_gesture(self):
        if self.hand_result is None:
            return Gest.PALM

        current_gesture = Gest.PALM
        if self.finger in [Gest.LAST3, Gest.LAST4] and self.get_dist([8, 4]) < 0.05:
            if self.hand_label == HLabel.MINOR:
                current_gesture = Gest.PINCH_MINOR
            else:
                current_gesture = Gest.PINCH_MAJOR
        elif Gest.FIRST2 == self.finger:
            point = [[8, 12], [5, 9]]
            dist1 = self.get_dist(point[0])
            dist2 = self.get_dist(point[1])
            ratio = dist1 / dist2
            if ratio > 1.7:
                current_gesture = Gest.V_GEST
            else:
                if self.get_dz([8, 12]) < 0.1:
                    current_gesture = Gest.TWO_FINGER_CLOSED
                else:
                    current_gesture = Gest.MID
        else:
            current_gesture = self.finger

        if current_gesture == self.prev_gesture:
            self.frame_count += 1
        else:
            self.frame_count = 0

        self.prev_gesture = current_gesture

        if self.frame_count > 4:
            self.ori_gesture = current_gesture
        return self.ori_gesture

class Controller:
    tx_old = 0
    ty_old = 0
    trial = True
    flag = False
    grabflag = False
    pinchmajorflag = False
    pinchminorflag = False
    pinchstartxcoord = None
    pinchstartycoord = None
    pinchdirectionflag = None
    prevpinchlv = 0
    pinchlv = 0
    framecount = 0
    prev_hand = None
    pinch_threshold = 0.3

    @staticmethod
    def getpinchylv(hand_result):
        dist = round((Controller.pinchstartycoord - hand_result.landmark[8].y) * 10, 1)
        return dist

    @staticmethod
    def getpinchxlv(hand_result):
        dist = round((hand_result.landmark[8].x - Controller.pinchstartxcoord) * 10, 1)
        return dist

    @staticmethod
    def changesystembrightness():
        currentBrightnessLv = cg.CGDisplayBrightness(cg.CGMainDisplayID())
        currentBrightnessLv += Controller.pinchlv / 50.0
        if currentBrightnessLv > 1.0:
            currentBrightnessLv = 1.0
        elif currentBrightnessLv < 0.0:
            currentBrightnessLv = 0.0
        cg.CGDisplaySetBrightness(cg.CGMainDisplayID(), currentBrightnessLv)

    @staticmethod
    def changesystemvolume():
        currentVolumeLv = int(osascript.osascript("output volume of (get volume settings)")[1])
        currentVolumeLv += int(Controller.pinchlv)
        if currentVolumeLv > 100:
            currentVolumeLv = 100
        elif currentVolumeLv < 0:
            currentVolumeLv = 0
        osascript.osascript(f"set volume output volume {currentVolumeLv}")

    @staticmethod
    def scrollVertical():
        pyautogui.scroll(120 if Controller.pinchlv > 0.0 else -120)

    @staticmethod
    def scrollHorizontal():
        pyautogui.keyDown('shift')
        pyautogui.keyDown('ctrl')
        pyautogui.scroll(-120 if Controller.pinchlv > 0.0 else 120)
        pyautogui.keyUp('ctrl')
        pyautogui.keyUp('shift')

    @staticmethod
    def get_position(hand_result):
        point = 9
        position = [hand_result.landmark[point].x, hand_result.landmark[point].y]
        sx, sy = pyautogui.size()
        x_old, y_old = pyautogui.position()
        x = int(position[0] * sx)
        y = int(position[1] * sy)
        if Controller.prev_hand is None:
            Controller.prev_hand = x, y
        delta_x = x - Controller.prev_hand[0]
        delta_y = y - Controller.prev_hand[1]

        distsq = delta_x ** 2 + delta_y ** 2
        ratio = 1
        Controller.prev_hand = [x, y]

        if distsq <= 25:
            ratio = 0
        elif distsq <= 900:
            ratio = 0.07 * (distsq ** (1 / 2))
        else:
            ratio = 2.1
        x, y = x_old + delta_x * ratio, y_old + delta_y * ratio

        if x >= sx:
            x = sx - 1
        elif x < 0:
            x = 0
        if y >= sy:
            y = sy - 1
        elif y < 0:
            y = 0

        return (x, y)

    @staticmethod
    def handle_controls(gesture, hand_result):
        x, y = None, None
        if gesture == Gest.PINCH_MINOR:
            if Controller.pinchminorflag == False:
                Controller.pinchstartxcoord = hand_result.landmark[8].x
                Controller.pinchstartycoord = hand_result.landmark[8].y
                Controller.pinchminorflag = True
                Controller.framecount = 0
            if Controller.framecount == 5:
                Controller.pinchlv = Controller.getpinchylv(hand_result)
                Controller.scrollVertical()
            elif Controller.framecount == 6:
                Controller.pinchlv = Controller.getpinchxlv(hand_result)
                Controller.scrollHorizontal()
            Controller.framecount += 1

        elif gesture == Gest.PINCH_MAJOR:
            if Controller.pinchmajorflag == False:
                Controller.pinchstartxcoord = hand_result.landmark[8].x
                Controller.pinchstartycoord = hand_result.landmark[8].y
                Controller.pinchmajorflag = True
                Controller.framecount = 0
            if Controller.framecount == 5:
                Controller.pinchlv = Controller.getpinchylv(hand_result)
                Controller.changesystemvolume()
            elif Controller.framecount == 6:
                Controller.pinchlv = Controller.getpinchylv(hand_result)
                Controller.changesystembrightness()
            Controller.framecount += 1

        elif gesture == Gest.V_GEST:
            if Controller.flag == False:
                Controller.flag = True
                pyautogui.mouseDown()
            Controller.trial = False

        elif gesture == Gest.FIST:
            if Controller.grabflag == False:
                Controller.grabflag = True
                pyautogui.mouseDown(button="left")
            x, y = Controller.get_position(hand_result)
            pyautogui.moveTo(x, y, duration=0.1)

        elif gesture == Gest.PALM and Controller.trial == False:
            Controller.flag = False
            Controller.grabflag = False
            Controller.pinchminorflag = False
            Controller.pinchmajorflag = False
            Controller.trial = True
            pyautogui.mouseUp(button="left")

        else:
            x, y = Controller.get_position(hand_result)
            pyautogui.moveTo(x, y, duration=0.1)

class GestureController:
    gc_mode = 0
    cap = None
    CAM_HEIGHT = None
    CAM_WIDTH = None
    hr_major = None
    hr_minor = None

    def __init__(self):
        GestureController.cap = cv2.VideoCapture(0)
        GestureController.CAM_WIDTH = GestureController.cap.get(cv2.CAP_PROP_FRAME_WIDTH)
        GestureController.CAM_HEIGHT = GestureController.cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
        with mp_hands.Hands(model_complexity=0,min_detection_confidence=0.5,min_tracking_confidence=0.5,max_num_hands=2) as hands:
            while GestureController.cap.isOpened():
                success, image = GestureController.cap.read()
                if not success:
                    print("Ignoring empty camera frame.")
                    continue

                image.flags.writeable = False
                image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
                results = hands.process(image)

                image.flags.writeable = True
                image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)

                if results.multi_hand_landmarks:
                    for hand_landmarks in results.multi_hand_landmarks:
                        handedness_dict = MessageToDict(results.multi_handedness[results.multi_hand_landmarks.index(hand_landmarks)])
                        if handedness_dict['classification'][0]['label'] == 'Right':
                            hand_label = HLabel.MAJOR
                            if GestureController.hr_major == None:
                                GestureController.hr_major = HandRecog(hand_label)
                            GestureController.hr_major.update_hand_result(hand_landmarks)
                            GestureController.hr_major.set_finger_state()
                            gesture = GestureController.hr_major.get_gesture()
                            Controller.handle_controls(gesture, GestureController.hr_major.hand_result)
                        else:
                            hand_label = HLabel.MINOR
                            if GestureController.hr_minor == None:
                                GestureController.hr_minor = HandRecog(hand_label)
                            GestureController.hr_minor.update_hand_result(hand_landmarks)
                            GestureController.hr_minor.set_finger_state()
                            gesture = GestureController.hr_minor.get_gesture()
                            Controller.handle_controls(gesture, GestureController.hr_minor.hand_result)

                        mp_drawing.draw_landmarks(image, hand_landmarks, mp_hands.HAND_CONNECTIONS)
                cv2.imshow('MediaPipe Hands', image)
                if cv2.waitKey(5) & 0xFF == 27:
                    break
        GestureController.cap.release()
        cv2.destroyAllWindows()

gc1 = GestureController()
