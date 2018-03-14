#!/usr/bin/python

import ibmiotf.device
import json
import RPi.GPIO as GPIO
import time


class Dispenser:
    LITERS_TO_GAL = 0.26417205234815
    GAL_LIMIT = 0.001
    
    def __init__(self, client, index, sensor):
        self.client = client
        self.index = index
        self.sensor = sensor
        self.running = False
        self.disconnect = False

        self.pouring = False
        self.gallonsPoured = 0

    def publish_data(self, event, data):
        data['beverage'] = self.index
        self.client.publishEvent(event, 'json', data)

    def loop(self):
        self.publish_data('online', {'state': True})
        
        self.disconnect = False
        self.pouring = False
        self.gallonsPoured = 0
        
        lastPinState = False
        pinState = 0
        lastPinChange = int(time.time() * 1000)
        pourStart = 0
        pinChange = lastPinChange
        pinDelta = 0
        hertz = 0
        flow = 0
        
        while self.running and not self.disconnect:
            currentTime = int(time.time() * 1000)
            
            if GPIO.input(self.sensor):
                pinState = True
            else:
                pinState = False

            if pinState != lastPinState and pinState:
                if not self.pouring:
                    pourStart = currentTime
                    self.pouring = True
                    self.publish_data('pouring', {'state': True})
                
                pinChange = currentTime
                pinDelta = pinChange - lastPinChange
                
                if pinDelta < 1000 and pinDelta != 0:
                    # calculate the instantaneous speed
                    hertz = 1000.0000 / pinDelta
                    flow = hertz / ( 60 * 7.5 ) # L/s
                    self.gallonsPoured += flow * pinDelta * Dispenser.LITERS_TO_GAL / 1000.0

            if self.pouring and pinState == lastPinState and (currentTime - lastPinChange) > 3000:
                if self.gallonsPoured > Dispenser.GAL_LIMIT:
                    # publish amount of liquid dispensed
                    self.publish_data('dispensed', {'amount': self.gallonsPoured})
                    
                    # print last amount poured
                    print self.gallonsPoured, 'gal'
                    
                    # reset gallons poured
                    self.gallonsPoured = 0

                # reset pouring flag
                self.pouring = False
                self.publish_data('pouring', {'state': False})

            lastPinChange = pinChange
            lastPinState = pinState

        self.cleanup()

    def cleanup(self):
        if self.pouring:
            self.publish_data('dispensed', {'amount': self.gallonsPoured})
            time.sleep(0.2)
            self.publish_data('pouring', {'state': False})
            time.sleep(0.2)
        
        self.publish_data('online', {'state': False})
        
        self.running = False

    def connect_device(self):
        self.running = True
    
    def disconnect_device(self):
        self.disconnect = True
