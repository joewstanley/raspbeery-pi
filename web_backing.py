#!/usr/bin/python

from flask import Flask, render_template, request, jsonify, redirect, url_for
from web_app import Monitor, MonitorApplication
import atexit
import cf_deployment_tracker
import ibmiotf.device
import json
import os
import re
import requests
import socket
import time


# emit Bluemix deployment event
cf_deployment_tracker.track()

# deploy app locally or through bluemix
app = Flask(__name__)

# get the port number from the environment variable PORT on bluemix
# default the port to 8080 on local machine
port = int(os.getenv('PORT', 8080))

# monitor application setup
iot_config = 'config/bluemix/app.cfg'
if os.path.exists(MonitorApplication.UPDATE_CONFIG_PATH):
    monitor_config = MonitorApplication.UPDATE_CONFIG_PATH
else:
    monitor_config = 'config/data/monitor.cfg'
monitor_app = MonitorApplication(monitor_config, iot_config)

@app.route('/')
def main_page():
    """Splash page that redirects to home page."""
    
    return render_template('splash.html')


@app.route('/home')
def home():
    """Render index.html for home page."""
    
    return render_template('index.html')


@app.route('/update/system')
def update_system():
    """Render page for updating system information."""
    
    return render_template('update/system.html')


@app.route('/update/system', methods=['POST'])
def put_system():
    """
    Publishes system information to application and database.
    Empty or null strings are not published to database.
    """
    
    # get data from json parameter
    data = request.json['system']
    
    monitor_app.update_system(data)
    
    return ''


@app.route('/update/beverage')
def update_beverage():
    """Render page for updating beverage information."""
    
    return render_template('update/beverage.html')


@app.route('/update/beverage', methods=['POST'])
def put_beverage():
    """
    Publishes beverage information to application and database.
    Empty or null strings are not published to database.
    """
    
    # get data from json parameter
    data = request.json['beverage']
    index = int(data['index'])
    
    monitor_app.update_beverage(index, data)
    
    return ''

@app.route('/update/control')
def update_control():
    """Render page for updating dispenser status."""
    
    return render_template('update/control.html')

@app.route('/update/control', methods=['POST'])
def put_control():
    """
    Publishes control information to application and database.
    """
    
    index = int(request.json['beverage'])
    state = request.json['state']
    
    if state:
        command = 'connect'
    else:
        command = 'disconnect'
    
    monitor_app.toggle_device_connection(index, command)
    
    return ''

@app.route('/update/usage', methods=['POST'])
def put_usage_update():
    
    index = int(request.json['beverage'])
    
    if (index == -1):
        monitor_app.update_order_analysis()
    else:
        monitor_app.update_beverage_analysis(index)
    
    return ''

@app.route('/update/auto', methods=['POST'])
def put_auto_update():
    
    index = int(request.json['beverage'])
    state = request.json['state']
    
    monitor_app.switch_auto_update(index, state)
    
    return ''

@app.route('/view/usage', methods=['GET'])
def view_usage():
    """Render page for viewing beverage usage data."""
    
    return render_template('view/usage.html')

@app.route( '/data/beverage', methods=['GET'] )
def get_beverage_data():
    """Retrieves beverage information from database."""
    
    # return all beverage information
    return jsonify(monitor_app.get_all_beverages())

@app.route( '/data/system', methods=['GET'] )
def get_system_data():
    """Retrieves system information from database."""
    
    # return system information
    return jsonify(monitor_app.get_system_info())

@app.route( '/data/usage', methods=['GET'] )
def get_beverage_usage():
    """Retrieves data to display for beverage usage."""
    
    data = []
    for index in range(len(monitor_app.monitor.beverages)):
        data.append(monitor_app.get_weekly_totals(index))
    
    # return beverage usage data
    return jsonify(data)

@atexit.register
def shutdown():
    # close mqtt client when terminating web server
    monitor_app.disconnect()

if __name__ == '__main__':
    try:
        # run app on localhost when called from terminal
        app.run( host='0.0.0.0', port=port, debug=False )
    except socket.error:
        # ignore errors caused by premature exit
        pass
