# CSC453-FinalProject #
### RaspbeeryPi ###

The RaspbeeryPi application is built on IBM Bluemix.

To obtain the programs neccessary to deploy the applicaton locally and/or on devices such as a Raspberry Pi, open a terminal, navigate to your directory of choice, and enter:
```
git clone https://github.ncsu.edu/wemaxey/CSC453-FinalProject.git
```


## Bluemix Environment Setup ##

The Bluemix environment must be setup using a Watson IOT service, a NoSQL Cloudant database, and a Python web application.

The IOT service should contain five devices:  a web device, a status device, and three beverage devices.  The device information, including organization ID, device type, device ID, and authorization token, should be inserted into the respective device configuration file (i.e., bev1.cfg, bev2.cfg, bev3.cfg, web.cfg, status.cfg).  This allows each program to connect to the Bluemix MQTT broker.

The only database that is required for the Raspbeery Pi system is the beverage_dispense table.  This database stores all daily dispensed amounts, and is used for order analysis and displaying dispenser information.  Additionally, the Cloudant database can be linked to the IOT service, acting as a historian database to store all device history.

For an email to be received when an order is made, three actions will have to be created, one action for each beverage dispenser.  The actions should be linked to cloud rules that monitor the web device, waiting for the corresponding beverage number and an order time that is not zero.

## Web Application ##

The Python web application should be titled BeverageMonitor.  The Watson IOT service and Cloudant database should be linked to the application, creating API keys and authentication information for each service.  The IOT service API key information, including organization ID, application ID, authorization key, and authorization token, should be inserted in the app.cfg file.

The Raspbeery Pi source directory should be pushed to the web application using the Cloud Foundry command-line interface.  The steps for this process can be found under the "Getting Started" tab on the Application Details web page.  Once the application is uploaded, the monitor system can be accessed from from the following webpage:
```
https://beveragemonitor.mybluemix.net/
```

The web application can also be deployed locally.  For a local environment, the file 'vcap-local.json' should be added to the cofig/bluemix folder with the VCAP services data from the application environment variables.  The following command should be ran locally to ensure that all required libraries and modules are available:
```
pip install -r requirements.txt
```

Deploying locally will host the website at the following URL:
```
https://localhost:8080/
```

The splash page will be displayed followed by the home screen when entering this web page.  The webpage includes pages for monitoring the Raspbeery Pi system, updating beverage information, updating system variables, connecting beverage dispensers, and viewing and updating order analysis data.

## Dispenser Raspberry Pi ##

The client_dispenser.py file should be updated to include the proper input pins for your setup.  The global array BEV_PIN should include the three GPIO pins that are connected to the water flow sensors.

Each dispenser must be run in its own terminal using the following command:
```
python client_dispense.py <NUM_BEV>
```

The argument NUM_BEV represents the dispenser number and can be either 1, 2, or 3.  Only one instant of each dispenser can be run at a time.  The device must be connected from the web interface for the dispenser to begin reading values.

## Status and Refill Raspberry Pi ##

The client_status.py file should be updated to include the proper input and output pins for your setup.  The global arrays LED_RED, LED_GRN, and BTN_REF should include the GPIO pins used for the red LED lights, green LED lights, and refill buttons, respectively.

The status and refill client can be ran using the following command:
```
python client_status.py
```

You may notice that the status of all three beverages will be offline, as indicated by a red icon in the status column.
To put the sensors online, navigate to the Device Control page on the web server and toggle each connection on.

On the home page, the three beverages should now appear to be online via a green icon in the status column.
All changes to the amount remaining for each beverage will be displayed on this main page.  This page will automatically update at 1 second intervals to quickly display changes as they occur.
