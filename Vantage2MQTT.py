#!python3
#!/usr/bin/env python
# -*- coding: utf-8 -*-
__author__ = "Thomas B."
"""
 Copyright 2020 Thomas B.
 Script:  Vantage2MQTT.py
 Author:  Thomas B.
 Purpose: Translate Vantage Infusion raw TCP ASCII to MQTT messages
"""

import sys
import socket
import select
import time
import threading
import datetime
import paho.mqtt.client as mqtt
import xml.etree.ElementTree as ET

# define the TCP conection to the Vantage controller
TCP_IP = '192.168.0.210'
TCP_PORT = 3001
BUFFER_SIZE = 2048

# define the MQTT connection for communication with ioBroker
broker = "192.168.0.203"
username = ""
password = ""
channel = "vantage/"

# A list of all the controlled vantage objects
items = []
threadEvent = threading.Event()

# Logger helper
def logOut(text):
	nowstr = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
	print(nowstr + ": " + text)

# Class for a command which is executed by the vantage controller
class Command:
	def __init__(self, element, floorname):
		self.name = element.get('name')
		self.task = int(element.get('taskid'))
		self.topic = floorname.lower().replace(" ", "") + "/command/" + self.name.lower().replace(" ", "")
		self.value = 0
		
	def handleMsgFromVantage(self, statuslist):
		# A command has no state which is handled in that direction
		return False;
	
	def handleMsgToVantage(self, topic, payload):
		if topic == self.topic:
			# The command gets executed whenever the payload differs from "0"
			if payload != "0":
				msgtcp = bytes("TASK " + str(self.task) + " PRESS\r\n", 'utf-8')
				s.send(msgtcp)
			# Then we reset the payload on the channel back to "0" so the next command can fire when this is changed again
			client.publish(channel + self.topic, payload=None)
			return True
		return False
	
	def handleSubscribe(self, client):
		# We subscribe to the broker with our topic
		fulltopic = channel + self.topic
		logOut(fulltopic)
		client.subscribe(fulltopic, 0)
		
	def handleTimer(self):
		# Nothing to do
		return False
		
# Class for a button of the vantage system. Can handle and signal the button to mqtt and can change the status LED color as return value        
class Button:
	def __init__(self, element, floorname, roomname):
		self.name = element.get('name')
		self.load = int(element.get('id'))
		self.topic = floorname.lower().replace(" ", "") + "/" + roomname.lower().replace(" ", "") + "/button/" + self.name.lower().replace(" ", "")
		self.statetopic = self.topic + "state"
		self.value = 0
		
	def handleMsgFromVantage(self, statuslist):
		if statuslist[0] == 'BTN' and int(statuslist[1]) == self.load:
			if (statuslist[2] == "PRESS"):
				self.value = 1
			else:
				self.value = 0
			logOut("New Value for Topic: " + self.topic + " Value: " + str(self.value))
			client.publish(channel + self.topic, str(self.value))
			return True
		return False;
	
	def handleMsgToVantage(self, topic, payload):
		if topic == self.statetopic:
			# We send the LED status to vantage
			if (payload.lower() == "true"):
				sendval = int(255)
			else:
				sendval = int(0)
			msgtcp = bytes("LED " + str(self.load) + " " + str(sendval) + "\r\n", 'utf-8')
			s.send(msgtcp)
			client.publish(channel + self.statetopic, payload)
			return True
		return False
	
	def handleSubscribe(self, client):
		# We subscribe to the broker with our state topic
		fulltopic = channel + self.statetopic
		logOut(fulltopic)
		client.subscribe(fulltopic, 0)
		
		client.publish(channel + self.topic, str(self.value))
		
	def handleTimer(self):
		# Nothing to do
		return False

# Dimmer class, can handle dimmed loads in vantage. Syncronizes both directions so the mqtt value always matches the value of the load in vantage
class Dimmer:
	def __init__(self, element, floorname, roomname):
		self.name = element.get('name')
		self.load = int(element.get('loadid'))
		self.typename = element.get('type')
		self.topic = floorname.lower().replace(" ", "") + "/" + roomname.lower().replace(" ", "") + "/dimmer/" + self.name.lower().replace(" ", "")
		self.value = 0
		
	def handleMsgFromVantage(self, statuslist):
		if statuslist[0] == 'LOAD' and int(statuslist[1]) == self.load:
			self.value = int(float(statuslist[2]))
			logOut("New Value for Topic: " + self.topic + " Value: " + str(self.value))
			client.publish(channel + self.topic, str(self.value))
			return True
		return False;
	
	def handleMsgToVantage(self, topic, payload):
		if topic == self.topic:
			sendval = int(payload)
			msgtcp = bytes("LOAD " + str(self.load) + " " + str(sendval) + "\r\n", 'utf-8')
			s.send(msgtcp)
			return True
		return False
	
	def handleSubscribe(self, client):
		# We subscribe to the broker with our topic
		fulltopic = channel + self.topic
		logOut(fulltopic)
		client.subscribe(fulltopic, 0)
		
	def handleTimer(self):
		# Nothing to do
		return	False

# Switch class this is the same as a dimmer but with only 100% or 0% load.
class Switch:
	def __init__(self, element, floorname, roomname):
		self.name = element.get('name')
		self.load = int(element.get('loadid'))
		self.typename = element.get('type')
		self.topic = floorname.lower() .replace(" ", "")+ "/" + roomname.lower().replace(" ", "") + "/switch/" + self.name.lower().replace(" ", "")
		self.value = 0
		
	def handleMsgFromVantage(self, statuslist):
		if statuslist[0] == 'LOAD' and int(statuslist[1]) == self.load:
			self.value = int(float(statuslist[2]))
			logOut("New Value for Topic: " + self.topic + " Value: " + str(self.value))
			client.publish(channel + self.topic, str(self.value))
			return True
		return False;
	
	def handleMsgToVantage(self, topic, payload):
		if topic == self.topic:
			sendval = int(payload)
			msgtcp = bytes("LOAD " + str(self.load) + " " + str(sendval) + "\r\n", 'utf-8')
			s.send(msgtcp)
			return True
		return False
	
	def handleSubscribe(self, client):
		# We subscribe to the broker with our topic
		fulltopic = channel + self.topic
		logOut(fulltopic)
		client.subscribe(fulltopic, 0)
		
	def handleTimer(self):
		# Nothing to do
		return False	

# A group class, this is used to handle multiple loads of dimmer or switch classes as one group and with syncronized values
class Group:
	def __init__(self, element, floorname, roomname):
		self.name = element.get('name')
		self.topic = floorname.lower() .replace(" ", "")+ "/" + roomname.lower().replace(" ", "") + "/group/" + self.name.lower().replace(" ", "")
		self.subItems = []
		for subElement in element:
			newItem = createItemFromElement(subElement, floorname, roomname)
			if newItem is not None:
				self.subItems.append(newItem)

	def handleMsgFromVantage(self, statuslist):
		for subItem in self.subItems:
			if subItem.handleMsgFromVantage(statuslist) == True:
				# If the sub item handled the request, we handled it also and return True
				return True
		return False;
	
	def handleMsgToVantage(self, topic, payload):
		# if the topic is our topic we handle the request for the whole group
		if topic == self.topic:
			for subItem in self.subItems:
				# We talk to all sub items and call their topic with the payload
				subItem.handleMsgToVantage(subItem.topic, payload)
			# We handled the request so we have to acknowledge the value
			client.publish(channel + self.topic, payload=None)
			return True
		else:
			# If it is not our own topic we try to send the request along in our groups
			for subItem in self.subItems:
				if subItem.handleMsgToVantage(topic, payload) == True:
					# If the sub item handled the request, we handled it also and return True
					return True
		return False
	
	def handleSubscribe(self, client):
		fulltopic = channel + self.topic
		logOut(fulltopic)
		client.subscribe(fulltopic, 0)
		# Now we subscribe our subitems
		for subItem in self.subItems:
			subItem.handleSubscribe(client)
			
	def handleTimer(self):
		# Nothing to do
		return False	

# A blind handler class, this is controlling two status variables (closed/motion) and two tasks (up/down) in vantage and maps it to percentage in mqtt
# 100% means the blind is fully closed while 0% means the blind is fully opened	
class Blind:
	def __init__(self, element, floorname, roomname):
		self.name = element.get('name')
		self.uptask = int(element.get('upid'))
		self.downtask = int(element.get('downid'))
		self.lasttask = int(0)
		self.statevar = int(element.get('stateid'))
		self.motionvar = int(element.get('motionid'))
		self.opentime = float(element.get('opentime'))
		self.closetime = float(element.get('closetime'))
		self.topic = floorname.lower().replace(" ", "") + "/" + roomname.lower().replace(" ", "") + "/blind/" + self.name.lower().replace(" ", "") + "/percent"
		self.percent = 0.0
		self.moveDuration = 0.0
		self.moveStartPercent = 0.0
		self.moveStarttime = None
		self.closed = False
		self.motion = False
		self.forceTime = False
		self.lastStateTime = None
		
	def handleMsgFromVantage(self, statuslist):
		if statuslist[0] == 'VARIABLE' and int(statuslist[1]) == self.statevar:
			if statuslist[2] == "1":
				self.closed = True
			else:
				self.closed = False
			
			if self.motion:
				# We have to redetermine the start percentage and the time of the movement
				self.moveStartPercent = self.percent
				self.moveStarttime = time.time()
				self.lastStateTime = self.moveStarttime
					
				# If we not forced the time by a percent change we reset the duration so it will be determined again next timer step
				if not self.forceTime:
					self.moveDuration = 0.0					
					
			return True
		elif statuslist[0] == 'VARIABLE' and int(statuslist[1]) == self.motionvar:
			if statuslist[2] == "1":
				self.motion = True
				# remember when we started the movement
				self.moveStarttime = time.time()
				self.moveStartPercent = self.percent
				self.lastStateTime = self.moveStarttime
										
				# now we need our thread to track the percentage for us
				threadEvent.set()
			else:
				self.lasttask = 0
				self.motion = False
				# We no longer have a duration
				self.moveDuration = 0.0
				# We reset the forced time as we ended the movement
				self.forceTime = False				
				
				# Now that we have stopped the movement we calculate the final percentage we now have
				if self.moveStarttime != None:
					# How long all in all did we move?
					movingTime = time.time() - self.moveStarttime
					
					# We no longer have a start time
					self.moveStarttime = None
					
					# Calculate the percentage for the whole movement depending on direction
					if self.closed:
						percentageChange = movingTime / self.closetime * 100.0
						self.percent = self.moveStartPercent + percentageChange
					
						if self.percent > 100.0:
							self.percent = 100.0						
					else:
						percentageChange = movingTime / self.opentime * 100.0
						self.percent = self.moveStartPercent - percentageChange
					
						if self.percent < 0.0:
							self.percent = 0.0						

				# Report the new final percentage to broker as int
				client.publish(channel + self.topic, payload=str(round(self.percent)))
			return True
		return False;
	
	def handleMsgToVantage(self, topic, payload):
		if topic == self.topic:
			
			# Get the value of the request
			targetpercent = float(payload)
			
			logOut(self.name + " request to move to " + str(int(targetpercent)))
			
			# If we got a negative payload we are requested to stop
			if targetpercent < 0.0:
				logOut(self.name + " stopping movement...")
				msgtcp = bytes("TASK " + str(self.uptask) + " PRESS\r\n", 'utf-8')
				msgtcp += bytes("TASK " + str(self.uptask) + " RELEASE\r\n", 'utf-8')
			else:				
				if targetpercent > 100.0:
					targetpercent = 100.0
				if targetpercent < 0.0:
					targetpercent = 0.0
				
				# Calculate the change in percent we want to do
				percentchange = targetpercent - self.percent
				abspercent = abs(percentchange)
				
				# determine the direction of movement
				if abs(percentchange) < 1.0:
					# we don't do changes below a certain percent threshold
					logOut(self.name + " change is less than threshold. Will not be executed!")
					return True
				else:
					msgtcp = bytes()
					self.moveDuration = 0.0
					
					# we determine the direction we need and build the command from this
					if percentchange < 0.0:
						# negative percentage means upwards (towards 0%)
						msgtcp = bytes("TASK " + str(self.uptask) + " PRESS\r\n", 'utf-8')
						self.lasttask = self.uptask
						self.moveDuration = self.opentime / 100.0 * abspercent
					else:
						# positive percentage means downwards (towards 100%)
						msgtcp = bytes("TASK " + str(self.downtask) + " PRESS\r\n", 'utf-8')
						self.lasttask = self.downtask
						self.moveDuration = self.closetime / 100.0 * abspercent
					
					if targetpercent == 0.0:
						# This is the special case that we want the percentage to 0 to compensate for cumulative errors we use this to recalibrate the motor
						self.moveDuration = self.moveDuration + self.opentime * 0.1
					elif targetpercent == 100.0:
						# This is the special case that we want the percentage to 100 to compensate for cumulative errors we use this to recalibrate the motor
						self.moveDuration = self.moveDuration + self.closetime * 0.1
					
					# For this movement we force the time as it was triggered by percent change
					self.forceTime = True
						
			# start the movement if any
			if len(msgtcp) > 0:
				s.send(msgtcp)
				
			return True
		
		return False
	
	def handleSubscribe(self, client):
		# We subscribe to the broker with our topics
		ctrlTopic = channel + self.topic
		logOut(ctrlTopic)
		client.subscribe(ctrlTopic, 0)
		# Report the current assumed percentage to broker as int
		client.publish(channel + self.topic, payload=str(round(self.percent)))		
		
		# Last thing is that we force all variables to be false as we cannot correctly sync to Vantage otherwise
		msgtcp = bytes("VARIABLE " + str(self.motionvar) + " 0\r\n", 'utf-8')
		s.send(msgtcp)
		msgtcp = bytes("VARIABLE " + str(self.statevar) + " 0\r\n", 'utf-8')
		s.send(msgtcp)		
		
	def handleTimer(self):		
		now = time.time()
		
		if self.motion:
			# Check if we have to calculate the moving time
			if self.moveDuration == 0.0:
				logOut(self.name + " unknown move duration, trying to determine direction and time...")
				# determine the direction from the status variable for closed
				if self.closed:
					# determine the maximum move time from the current percentage
					maxMoveTime = ((100 - self.moveStartPercent) / 100) * self.closetime
					self.moveDuration = maxMoveTime + self.closetime * 0.1
					logOut(self.name + " closing: " + str(self.moveDuration))
				else:
					# determine the maximum move time from the current percentage
					maxMoveTime = (self.moveStartPercent / 100) * self.opentime
					self.moveDuration = maxMoveTime + self.opentime * 0.1
					logOut(self.name + " opening: " + str(self.moveDuration))
					
			# How long all in all did we move?
			movingTime = now - self.moveStarttime
		
			# Check if we have to report the state
			# We report every 1 second
			if now - self.lastStateTime > 1.0 and self.moveStarttime != None:
				# Remember that we report now
				self.lastStateTime = now
				
				# Calculate the percentage for the whole movement depending on direction
				if self.closed:
					percentageChange = movingTime / self.closetime * 100.0
					self.percent = self.moveStartPercent + percentageChange
			
					if self.percent > 100.0:
						self.percent = 100.0
				else:
					percentageChange = movingTime / self.opentime * 100.0
					self.percent = self.moveStartPercent - percentageChange
			
					if self.percent < 0.0:
						self.percent = 0.0				
	
				# Report the current percentage to broker as int
				client.publish(channel + self.topic, payload=str(round(self.percent)))
	
			# Check for end of moving
			if self.moveDuration > 0.0:
				# How much time till we have to stop the movement
				remainingTime = self.moveDuration - movingTime
				# If the time step is smaller than our delta time till we get called next time we stop the movement now
				if remainingTime < 0.1:
					if self.lasttask != 0:
						# we have to stop the movement now
						logOut(self.name + " stop the movement with lasttask")
						msgtcp = bytes("TASK " + str(self.lasttask) + " RELEASE\r\n", 'utf-8')
						self.lasttask = 0
						# stop the movement
						s.send(msgtcp)
					else:
						logOut(self.name + " stop external movement by setting motion variable")
						msgtcp = bytes("VARIABLE " + str(self.motionvar) + " 0\r\n", 'utf-8')
						# stop the movement
						s.send(msgtcp)						
		
		# We return if we are in motion right now
		return self.motion

# A group of blinds. This class handles multiple blinds in one group and can open or close them fully. Percentage is not possible with this class		
class BlindGroup:
	def __init__(self, element, floorname, roomname):
		self.name = element.get('name')
		self.uptask = int(element.get('upid'))
		self.downtask = int(element.get('downid'))		
		self.topic = floorname.lower() .replace(" ", "")+ "/" + roomname.lower().replace(" ", "") + "/blindgroup/" + self.name.lower().replace(" ", "")
		self.subItems = []
		for subElement in element:
			newItem = createItemFromElement(subElement, floorname, roomname)
			if newItem is not None:
				self.subItems.append(newItem)
				
	def handleMsgFromVantage(self, statuslist):
		# As a group we never handle requests from vantage as we have no own state
		for subItem in self.subItems:
			if subItem.handleMsgFromVantage(statuslist) == True:
				# If the sub item handled the request, we handled it also and return True
				return True
		return False;
	
	def handleMsgToVantage(self, topic, payload):
		# As a group we can only handle up and down commands
		# The states are always handled by the sub items itself
		if topic == self.topic:
			msgtcp = bytes()

			if payload == '1':
				msgtcp = bytes("TASK " + str(self.uptask) + " PRESS\r\n", 'utf-8')
			elif payload == '2':
				msgtcp = bytes("TASK " + str(self.downtask) + " PRESS\r\n", 'utf-8')

			if len(msgtcp) > 0:
				s.send(msgtcp)
			# Then we set the payload back to 0 so we acknowledge to the broker that we did something
			client.publish(channel + self.topic, payload=None)
			return True
		else:
			# If it is not our own topic we try to send the request along in our groups
			for subItem in self.subItems:
				if subItem.handleMsgToVantage(topic, payload) == True:
					# If the sub item handled the request, we handled it also and return True
					return True
		return False
	
	def handleSubscribe(self, client):
		# We subscribe ourself
		fulltopic = channel + self.topic
		logOut(fulltopic)
		client.subscribe(fulltopic, 0)		
		# And we subscribe our sub items
		for subItem in self.subItems:
			subItem.handleSubscribe(client)
			
	def handleTimer(self):
		retVal = False
		# We handle all out sub items
		for subItem in self.subItems:
			if subItem.handleTimer() == True:
				# If the sub item returned true we store that at least one sub item needs true as return value
				retVal = True
		
		# We return	True of at least one sub item returned true else we return false
		return retVal

# This gets called when the connection of the mqtt broker was established
def on_mqtt_connect(client, userdata, flags, rc):
	if(rc == 0):
		logOut("Connected to MQTT Broker: ", rc)
		client.connected_flag = True #set flag
	else:
		logOut("Error connecting to MQTT Broker: ", rc)
		brokerconnected = False
		client.connected_flag = False #set flag

# This is called for all subscribed topics
def on_message_from_mqtt(client, userdata, msg):
	rawtopic = msg.topic[len(channel):]
	payload = str(msg.payload.decode("utf-8"))
	logOut("Topic: " + rawtopic + " Payload: " + payload)
	
	handled = False
	
	if len(payload) != 0:
		# We have to forward the request to our items
		for curItem in items:
			if curItem.handleMsgToVantage(rawtopic, payload) == True:
				handled = True
				break
		if handled == False:
			print("Not handled!")

# This is our factory which handles the creation of the instances of above classes from the xml file data	
def createItemFromElement(element, floorname, roomname):
	if(element.tag == 'dimmer'):
		logOut("Create Dimmer")
		return Dimmer(element, floorname, roomname)
	elif(element.tag == 'switch'):
		logOut("Create Switch")
		return Switch(element, floorname, roomname)
	elif(element.tag == 'button'):
		logOut("Create Button")
		return Button(element, floorname, roomname)	
	elif(element.tag == 'group'):
		logOut("Create Group")
		return Group(element, floorname, roomname)
	elif(element.tag == 'blindgroup'):
		logOut("Create Blindgroup")
		return BlindGroup(element, floorname, roomname)
	elif(element.tag == 'blind'):
		logOut("Create Blind")
		return Blind(element, floorname, roomname)
	else:
		logOut("Unknown element type: " + element.tag + " Ignoring!")
	return None

# This method runs the threaded elements (currently only blinds use the timer)
def threadRunner():
	while(True):
		# Wait for the thread to be signaled to run
		threadEvent.wait()
		
		logOut("Thread woken due to blind trigger")
		
		# Check if we have to stay awake
		stayAwake = True
		
		while(stayAwake):
			# We start by waiting for 100ms until we do our thing
			time.sleep(0.1)
			
			atLeastOneWorks = False
			
			# We check all items once and track if at least one requests to stay awake for next cycle
			for curItem in items:
				if curItem.handleTimer() == True:
					atLeastOneWorks = True
			
			# We have to stay awake for the next cycle if at least one handler still requires operations
			stayAwake = atLeastOneWorks
			
			# As we are about to sleep again we reset our signal to be trigerred again next time
			if stayAwake == False:
				threadEvent.clear()
				logOut("Thread is about to sleep again until next trigger")

### Main programm
if __name__ == '__main__':
	try:
		configfile = 'VantageConfig.xml'
		
		if len(sys.argv) >= 2:
			logOut("Using argv config")
			configfile = sys.argv[1]
			
		logOut("Parsing: '" + configfile + "' ...")
		tree = ET.parse(configfile)
		root = tree.getroot()
		for floor in root.iter('floor'):
			floorname = floor.get('name')
			for room in floor.iter('room'):
				roomname = room.get('name')
				for element in room:
					newitem = createItemFromElement(element, floorname, roomname)
					if newitem is not None:
						items.append(newitem)
			for command in floor.iter('command'):
				items.append(Command(command, floorname))
									
		# establish TCP connection to Vantage controller
		if len(sys.argv) >= 3:
			connectTime = int(sys.argv[2])
			logOut("Connecting Vantage Controller... in" + connectTime + " seconds")
			time.sleep(connectTime)
		else:
			logOut("Connecting Vantage Controller...")
			
		s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		s.connect((TCP_IP, TCP_PORT))
		# We have to request the Vantage controller to send us status changes for specific types
		s.send(b'status load\r\n')
		s.send(b'status variable\r\n')
		s.send(b'status btn\r\n')
		
		# Create the MQTT client and set the callbacks
		client = mqtt.Client(client_id="vantage2mqtt_client")
		client.on_connect = on_mqtt_connect
		client.on_message = on_message_from_mqtt
		
		# Connect to MQTT and wait for messages
		logOut("Connecting MQTT Broker...")
		client.username_pw_set(username, password)
		client.connect(broker, 1883, 60)
		
		# Inform that we are about to start the thread
		logOut("Starting timer thread...")
		timerThread = threading.Thread(target=threadRunner, daemon=True)
		timerThread.start()
		
		# Inform about the channels being subscribed
		logOut("Subscribing to channels:")
		
		# Subscribe to all channels on MQTT
		for curItem in items:
			curItem.handleSubscribe(client)
		
		# infinite loop ...
		logOut("Wait for signals...")
		client.loop_start()	
		
		while True:
			try:
				ready_to_read, ready_to_write, in_error = select.select([s,], [], [], 5)				
			except select.error:
				s.shutdown(2)    # 0 = done receiving, 1 = done sending, 2 = both
				s.close()
				# connection error, socket died
				logOut("Socket Connection Error! Reconnecting...")
				# we try to reconnect
				s.connect((TCP_IP, TCP_PORT))
				# We have to request the Vantage controller to send us status changes for specific types
				s.send(b'status load\r\n')
				s.send(b'status variable\r\n')
				s.send(b'status btn\r\n')
				logOut("Reconnect worked!")
			# receive data from vantage
			if len(ready_to_read) > 0:
				data = bytes(s.recv(BUFFER_SIZE))
				data = str(data.decode("utf-8"))
				# Split the commands to multiple lines if applicable
				recvData = data.splitlines()
				# cut the "\r\n" at end
				#data = data[0:len(data)-2]
				
				# call the handlers for each line
				for curLine in recvData:
					logOut("From Vantage: " + curLine)
					# Check for the ':' in the string
					msgtypelist = curLine.split(':')
				
					if msgtypelist[0] == 'S':
						# Split the real status message in its components
						statuslist = msgtypelist[1].split(' ')			
						for curItem in items:
							if curItem.handleMsgFromVantage(statuslist) == True:
								break
	except KeyboardInterrupt:
		logOut("Stopped by user")
	except:
		logOut("Exit by error")
	finally:
		s.close()
		client.loop_stop()
		logOut("This is Ripley last survivor of the Nostromo signing off")
