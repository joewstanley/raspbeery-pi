#!/usr/bin/python

from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timedelta

import ConfigParser
import ibmiotf.application
import json
import os
import requests
import time


class MonitorApplication:
    DEFAULT_TAP_SIZE = 5.0
    DEFAULT_ORDER_AMOUNT = 31.0
    DEFAULT_MAX_STORAGE = 310.0
    DEFAULT_DAYS_TO_ORDER = 1
    
    UPDATE_CONFIG_PATH = 'config/data/current.cfg'
    
    def __init__(self, monitor_config, iot_config):
        self.iot_config = iot_config
        self.monitor_config = monitor_config
        
        self.configure_monitor(monitor_config)
        self.configure_iot(iot_config)
        self.configure_cloudant()
        self.configure_scheduler()
    
    def __exit__(self, exc_type, exc_value, traceback):
        self.disconnect()
    
    def configure_monitor(self, config):
        parser = ConfigParser.ConfigParser()
        
        with open(config) as f:
            parser.readfp(f)
        
        tap_size = parser.get('monitor', 'tap_size')
        order_amount = parser.get('monitor', 'order_amount')
        max_storage = parser.get('monitor', 'max_storage')
        days_to_order = parser.get('monitor', 'days_to_order')
        
        if tap_size is None or len(tap_size) == 0:
            tap_size = MonitorApplication.DEFAULT_TAP_SIZE
        if order_amount is None or len(order_amount) == 0:
            order_amount = MonitorApplication.DEFAULT_ORDER_AMOUNT
        if max_storage is None or len(max_storage) == 0:
            max_storage = MonitorApplication.DEFAULT_MAX_STORAGE
        if days_to_order is None or len(days_to_order) == 0:
            days_to_order = MonitorApplication.DEFAULT_DAYS_TO_ORDER
        
        self.monitor = Monitor(float(tap_size), float(order_amount), float(max_storage), float(days_to_order))
        
        while parser.has_section('beverage' + str(len(self.monitor.beverages) + 1)):
            section = 'beverage' + str(len(self.monitor.beverages) + 1)
            
            name = parser.get(section, 'name')
            tap = parser.get(section, 'tap')
            storage = parser.get(section, 'storage')
            total_dispensed = parser.get(section, 'total_dispensed')
            days_dispensed = parser.get(section, 'days_dispensed')
            last_order = parser.get(section, 'last_order')
            auto_update = parser.get(section, 'auto_update')
            
            if name is None or len(name) == 0:
                name = 'Beverage ' + str(len(self.monitor.beverages) + 1)
            if tap is None or len(tap) == 0:
                tap = 0.0
            if storage is None or len(storage) == 0:
                storage = 0.0
            if total_dispensed is None or len(total_dispensed) == 0:
                total_dispensed = tap_size
            if days_dispensed is None or len(days_dispensed) == 0:
                days_dispensed = 1
            if last_order is None or len(last_order) == 0:
                last_order = 0
            if auto_update is None or len(auto_update) == 0:
                auto_update = False
                
            self.monitor.add_beverage(Beverage(name, float(tap), float(storage), float(total_dispensed), int(days_dispensed), long(last_order), auto_update == 'True'))
    
    def configure_iot(self, config):
        options = ibmiotf.application.ParseConfigFile(config)
        self.client = ibmiotf.application.Client(options)
        
        self.client.connect()
        
        self.client.deviceEventCallback = self.event_callback
        
        self.client.subscribeToDeviceEvents(event='dispensed')
        self.client.subscribeToDeviceEvents(event='refill')
        self.client.subscribeToDeviceEvents(event='online')
        self.client.subscribeToDeviceEvents(event='pouring')
        self.client.subscribeToDeviceEvents(event='startup')
    
    def configure_cloudant(self):
        self.cloudant = CloudantConnector('beverage_dispense')
    
    def configure_scheduler(self):
        self.sched = BackgroundScheduler()
        next_date = datetime.now() + timedelta(days=1)
        run_time = datetime(next_date.year, next_date.month, next_date.day, 0, 0, 0, 0)
        self.sched.add_job(self.update_event, 'date', run_date=run_time)
        self.sched.start()
    
    def update_event(self):
        for index in range(len(self.monitor.beverages)):
            beverage = self.monitor.get_beverage(index)
            if beverage.auto_update:
                self.update_beverage_analysis(index)
        self.sched.shutdown(wait=False)
        self.configure_scheduler()
            
    
    def event_callback(self, command):
        if command.event == 'startup':
            data = {'beverages': self.get_all_beverages()}
            self.send_command('status', 'info', data)
        else:
            data = json.loads(command.payload)
            index = int(data['beverage'])
            
            if command.event == 'dispensed':
                dispensed_amount = float(data['amount'])
                self.monitor.dispense_beverage(index, dispensed_amount)
                if self.monitor.order_status(index):
                    self.publish_order(index)
            elif command.event == 'refill':
                self.monitor.refill_beverage(index)
            elif command.event == 'online':
                status = data['state']
                self.monitor.toggle_online(index, status)
                info = {'beverages': self.get_all_beverages()}
                self.send_command('status', 'info', info)
            elif command.event == 'pouring':
                status = data['state']
                self.monitor.toggle_pouring(index, status)
            
            self.publish_beverage(index)

    def publish_order(self, index):
        beverage = self.monitor.get_beverage(index)
        data = {'order_time': beverage.last_order}
        self.publish(index, 'order', data)
    
    def publish_beverage(self, index):
        data = self.get_beverage_data(index)
        self.publish(index, 'log', data)
        self.update_config(index)
    
    def publish(self, index, event, data):
        data['beverage'] = index
        self.client.publishEvent('Webpage', 'web', event, 'json', data)
    
    def send_command(self, deviceId, command, data):
        self.client.publishCommand('RaspberryPi', deviceId, command, 'json', data)
    
    def toggle_device_connection(self, index, command):
        device = 'bev' + str(index + 1)
        data = {'beverage': index}
        self.send_command(device, command, data)
    
    def update_config(self, index):
        beverage = self.monitor.get_beverage(index)
        parser = ConfigParser.ConfigParser()
        
        if os.path.exists(MonitorApplication.UPDATE_CONFIG_PATH):
            with open(MonitorApplication.UPDATE_CONFIG_PATH) as f:
                parser.readfp(f)
            os.remove(MonitorApplication.UPDATE_CONFIG_PATH)
        else:
            with open(self.monitor_config) as f:
                parser.readfp(f)
        
        config = open(MonitorApplication.UPDATE_CONFIG_PATH, 'w')
        
        section = 'beverage' + str(index + 1)
        parser.set(section, 'name', beverage.name)
        parser.set(section, 'tap', beverage.tap)
        parser.set(section, 'storage', beverage.storage)
        parser.set(section, 'total_dispensed', beverage.total_dispensed)
        parser.set(section, 'days_dispensed', beverage.days_dispensed)
        parser.set(section, 'auto_update', beverage.auto_update)
        if beverage.last_order != 0:
            parser.set(section, 'last_order', beverage.last_order)
        
        parser.write(config)
        config.close()
    
    def post_daily_total(self, index):
        beverage = self.monitor.get_beverage(index)
        data = {
            'beverage': index + 1,
            'date': int(time.time() * 1000),
            'amount_dispensed': beverage.daily_total
        }
        self.cloudant.post_json(data)
    
    def get_weekly_totals(self, index):
        beverage = self.monitor.get_beverage(index)
        week_info = self.cloudant.get_data('by-bev' + str(index + 1), True, 7)
        
        data = {
            'total_dispensed': beverage.total_dispensed,
            'days_dispensed': beverage.days_dispensed,
            'auto_update': beverage.auto_update,
            'day': beverage.daily_total,
            'week': week_info
        }
        
        return data
    
    def get_all_beverages(self):
        beverages = []
        for index in range(len(self.monitor.beverages)):
            beverages.append(self.get_beverage_data(index))
        return beverages
    
    def get_beverage_data(self, index):
        beverage = self.monitor.get_beverage(index)
        data = {
            'name': beverage.name,
            'tap': beverage.tap,
            'storage': beverage.storage,
            'days_left': beverage.storage * beverage.days_dispensed / beverage.total_dispensed,
            'last_order': beverage.last_order,
            'online': beverage.online,
            'pouring': beverage.pouring,
            'auto_update': beverage.auto_update
        }
        return data
    
    def get_system_info(self):
        data = {
            'min_tap_size': self.monitor.MIN_TAP_SIZE,
            'min_storage_size': self.monitor.MIN_STORAGE_SIZE,
            'tap_size': self.monitor.tap_size,
            'max_storage': self.monitor.max_storage,
            'order_amount': self.monitor.order_amount,
            'days_to_order': self.monitor.days_to_order
        }
        return data
    
    def update_beverage(self, index, data):
        if data['name'] is not None and len(data['name']) != 0:
            name = data['name']
            self.monitor.update_name(index, name)
        
        if data['tap'] is not None and len(data['tap']) != 0:
            tap = float(data['tap'])
            self.monitor.update_tap(index, tap)
        
        if data['storage'] is not None and len(data['storage']) != 0:
            storage = float(data['storage'])
            tap = self.monitor.get_beverage(index).tap
            self.monitor.update_storage(index, max(tap, storage))
            if self.monitor.order_status(index):
                self.publish_order(index)
        
        if data['average_dispensed'] is not None and len(data['average_dispensed']) != 0:
            average_dispensed = float(data['average_dispensed'])
            self.monitor.update_average_dispensed(index, average_dispensed)
        
        self.publish_beverage(index)
    
    def update_system(self, data):
        if data['tap_size'] is not None and len(data['tap_size']) != 0:
            tap_size = float(data['tap_size'])
            self.monitor.update_tap_size(tap_size)
        
        if data['order_amount'] is not None and len(data['order_amount']) != 0:
            order_amount = float(data['order_amount'])
            self.monitor.update_order_amount(order_amount)
        
        if data['max_storage'] is not None and len(data['max_storage']) != 0:
            max_storage = float(data['max_storage'])
            self.monitor.update_max_storage(max_storage)
        
        if data['days_to_order'] is not None and len(data['days_to_order']) != 0:
            days_to_order = float(data['days_to_order'])
            self.monitor.update_days_to_order(days_to_order)
            for index in range(len(self.monitor.beverages)):
                if self.monitor.order_status(index):
                    self.publish_order(index)
    
    def update_order_analysis(self):
        for index in range(len(self.monitor.beverages)):
            self.update_beverage_analysis(index)
            time.sleep(0.2)
    
    def update_beverage_analysis(self, index):
        self.post_daily_total(index)
        self.monitor.reset_total_dispensed(index)
        self.publish_beverage(index)
    
    def switch_auto_update(self, index, status):
        self.monitor.toggle_auto_update(index, status)
        self.publish_beverage(index)
    
    def disconnect(self):
        if hasattr(self, 'client'):
            self.client.disconnect()
        if hasattr(self, 'sched'):
            self.sched.shutdown()


class Monitor:
    MIN_TAP_SIZE = 1.0
    MIN_STORAGE_SIZE = 1.0
    
    def __init__(self, tap_size, order_amount, max_storage, days_to_order):
        self.tap_size = tap_size
        self.order_amount = order_amount
        self.max_storage = max_storage
        self.days_to_order = days_to_order
        self.beverages = []
    
    def add_beverage(self, beverage):
        self.beverages.append(beverage)
    
    def get_beverage(self, index):
        return self.beverages[index]
    
    def update_name(self, index, name):
        beverage = self.get_beverage(index)
        beverage.name = name
        
    def update_tap(self, index, tap):
        beverage = self.get_beverage(index)
        beverage.tap = tap
    
    def update_storage(self, index, storage):
        beverage = self.get_beverage(index)
        beverage.storage = storage
    
    def update_average_dispensed(self, index, average_dispensed):
        beverage = self.get_beverage(index)
        beverage.total_dispensed = average_dispensed
        beverage.days_dispensed = 1
    
    def update_tap_size(self, tap_size):
        self.tap_size = tap_size
        for beverage in self.beverages:
            if beverage.tap > tap_size:
                beverage.tap = tap_size
    
    def update_order_amount(self, order_amount):
        self.order_amount = order_amount
    
    def update_max_storage(self, max_storage):
        self.max_storage = max_storage
    
    def update_days_to_order(self, days_to_order):
        self.days_to_order = days_to_order
    
    def reset_total_dispensed(self, index):
        beverage = self.get_beverage(index)
        beverage.total_dispensed += beverage.daily_total
        beverage.days_dispensed += 1
        beverage.daily_total = 0.0
    
    def refill_beverage(self, index):
        beverage = self.get_beverage(index)
        if beverage.storage < self.tap_size:
            beverage.tap = beverage.storage
        else:
            beverage.tap = self.tap_size
    
    def dispense_beverage(self, index, dispensed_amount):
        beverage = self.get_beverage(index)
        beverage.tap -= dispensed_amount
        beverage.storage -= dispensed_amount
        if beverage.tap < 0:
            beverage.tap = 0.0
        if beverage.storage < 0:
            beverage.storage = 0.0
		
        beverage.daily_total += dispensed_amount
    
    def order_status(self, index):
        beverage = self.get_beverage(index)
        days_left = beverage.storage * beverage.days_dispensed / beverage.total_dispensed
        if days_left <= self.days_to_order:
            self.make_order(index)
            return True
        else:
            return False
    
    def make_order(self, index):
        beverage = self.get_beverage(index)
        beverage.storage += self.order_amount
        beverage.last_order = int(time.time() * 1000)
    
    def toggle_online(self, index, status):
        beverage = self.get_beverage(index)
        if status:
            beverage.online = True
        else:
            beverage.online = False
    
    def toggle_pouring(self, index, status):
        beverage = self.get_beverage(index)
        if status:
            beverage.pouring = True
        else:
            beverage.pouring = False
    
    def toggle_auto_update(self, index, status):
        beverage = self.get_beverage(index)
        beverage.auto_update = status


class Beverage:
    def __init__(self, name, tap, storage, total_dispensed, days_dispensed, last_order, auto_update):
        self.name = name
        self.tap = tap
        self.storage = storage
        self.total_dispensed = total_dispensed
        self.days_dispensed = days_dispensed
        self.last_order = last_order
        self.auto_update = auto_update
        
        self.daily_total = 0.0
        self.online = False
        self.pouring = False


class CloudantConnector:
    def __init__(self, database):
        # get credentials for cloudant database
        if 'VCAP_SERVICES' in os.environ:
            # credentials are given by bluemix environment
            vcap = json.loads(os.getenv('VCAP_SERVICES'))
            if 'cloudantNoSQLDB' in vcap:
                creds = vcap['cloudantNoSQLDB'][0]['credentials']
                self.username = creds['username']
                self.password = creds['password']
                host = creds['host']
        elif os.path.isfile('config/bluemix/vcap-local.json'):
            # credentials are found locally
            # vcap/vcap-local.json
            with open('config/bluemix/vcap-local.json') as f:
                vcap = json.load(f)
                creds = vcap['cloudantNoSQLDB'][0]['credentials']
                self.username = creds['username']
                self.password = creds['password']
                host = creds['host']
        
        self.url = 'https://' + host + '/' + database
    
    def get_data(self, view, descending, limit):
        view_url = self.url + '/_design/data/_view/' + view
        args = {'descending': descending, 'limit': limit}
        
        response = requests.get(view_url, params=args, auth=(self.username, self.password))
        if 'rows' in response.json():
            return response.json()['rows']
        else:
            return ''
    
    def post_json(self, data):
        return requests.post(self.url, json=data, auth=(self.username, self.password))