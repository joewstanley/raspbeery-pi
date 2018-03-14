#!/usr/bin/python

import ibmiotf.device
import json
import RPi.GPIO as GPIO
import threading
import time


# number of beverage dispensers
NUM_BEVS = 3

# GPIO component pins
LED_RED = [7, 13, 29]
LED_GRN = [11, 15, 31]
BTN_REF = [33, 35, 37]

# setup I/O pins
GPIO.setwarnings(False)
GPIO.setmode(GPIO.BOARD)
GPIO.setup(LED_RED, GPIO.OUT)
GPIO.setup(LED_GRN, GPIO.OUT)
GPIO.setup(BTN_REF, GPIO.IN)

def toggle_lights(online):
    for i in range(NUM_BEVS):
        GPIO.output(LED_GRN[i], online[i])
        GPIO.output(LED_RED[i], not online[i])

def command_callback(command):
    if command.command == 'info':
        beverages = command.data['beverages']
        
        online = []
        for beverage in beverages:
            online.append(beverage['online'])
        toggle_lights(online)

try:
    options = ibmiotf.device.ParseConfigFile('config/bluemix/status.cfg')
    client = ibmiotf.device.Client(options)
    client.connect()
    client.commandCallback = command_callback
    
    client.publishEvent('startup', 'json', {})
    
    button_state = False
    prev_button_state = False
    
    while True:
        for i in range(NUM_BEVS):
            button_state = GPIO.input(BTN_REF[i])
            if button_state and button_state != prev_button_state:
                client.publishEvent('refill', 'json', {'beverage': i})
            prev_button_state = button_state
        time.sleep(0.2)
except ibmiotf.ConnectionException as e:
    print e
except KeyboardInterrupt:
    if client:
        client.disconnect()
finally:
    GPIO.cleanup()
