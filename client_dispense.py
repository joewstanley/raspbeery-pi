#!/usr/bin/python

from dispenser import Dispenser

import ibmiotf.device
import json
import RPi.GPIO as GPIO
import sys
import time


# number of beverage dispensers
NUM_BEVS = 3

# I/O pins for beverage
BEV_PIN = [36, 38, 40]

beverage = int(sys.argv[1])
dispenser = None

# setup I/O pins
GPIO.setwarnings(False)
GPIO.setmode(GPIO.BOARD)
GPIO.setup(BEV_PIN[beverage - 1], GPIO.IN)

def command_callback(command):
    if command.command == 'connect' and not dispenser.running:
        print 'Connecting Beverage ' + str(beverage) + '...'
        dispenser.connect_device()
    elif command.command == 'disconnect' and not dispenser.disconnect:
        print 'Disconnecting Beverage ' + str(beverage) + '...'
        dispenser.disconnect_device()

try:
    options = ibmiotf.device.ParseConfigFile('config/bluemix/bev' + str(beverage) + '.cfg')
    client = ibmiotf.device.Client(options)
    client.connect()
    client.commandCallback = command_callback
    
    dispenser = Dispenser(client, beverage - 1, BEV_PIN[beverage - 1])
    
    while True:
        if dispenser.running:
            dispenser.loop()
except ibmiotf.ConnectionException as e:
    print e
except KeyboardInterrupt:
    dispenser.cleanup()
    
    if client:
        client.disconnect()
finally:
    GPIO.cleanup()
