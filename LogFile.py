#!/usr/bin/env python3
import sys
import subprocess
import random
import re
from time import strftime, sleep 
import json
import logging
import tempfile
from datetime import datetime


class logFile(object):
	def __init__(self, logFileName):
		self.logFileName = logFileName
		self._fileFormat = None
		self._sourceFD = None
		self._tempFileName = None
		self._tempFD = None
		self._iterMode = 'raw'

	def __iter__(self):
		return self

	def __next__(self):
		# Get next line 
		line = self.getNextLine()
		if line:
			if self._iterMode == 'raw':
				return line
			elif self._iterMode == 'tokenize':
				return self._tokenize(line)
			else:
				raise Exception('Unrecognized Iterator Mode')
		else:
			raise StopIteration

	def _translateFile(self):
		# For now, just read source & write to temp all at once.  Ver 2 - produce on-demand.
		#Determine what kind of file this is
		if self._isNCMSupportLog():
			self._translateNCMSupportLog()
		else:
			self._translateDefault()
		self.reset()

	##Support logs are exported from NCM on a per router basis
	#Reports time as follows "2019-04-25 13:34:33", using 24 hour time
	#Log contains a lot of extra data we don't currently need. Trim off that data and keep only log
	#Date can be from 1969, need to detect this and adjust time
	#Log sorted newest->oldest
	def _isNCMSupportLog(self):
		self._sourceFD.seek(0)
		for i in range(2):
			self._sourceFD.readline()
		line = self._sourceFD.readline()
		self._sourceFD.seek(0)
		return line == "ECM Info\n"
	
	def _translateNCMSupportLog(self):
		ncm_rgx = r'^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\|\s*(\S*)\|\s*(\S*)\|(.*)$'
		#originTime = datetime(1969,12,31,18,0,0) # Currently unused reference to the origin time of the log file
		timeformat = r'%Y-%m-%d %H:%M:%S'
		lastDate = None
		offsetDate = None
		lastCorrectDate = None
		for line in self._sourceFD:
			matchobj = re.match(ncm_rgx, line)
			if matchobj:
				curdatetime = datetime.strptime(matchobj.group(1), timeformat)
				#This stuff gets kinda janky, but it's a functioning first pass for dealing with the 1969 issue
				if not offsetDate and curdatetime.year == 1969: # Save last correct date
					offsetDate = curdatetime
					lastCorrectDate = lastDate
				if curdatetime.year == 1969:
					finaldatetime = lastCorrectDate - (offsetDate - curdatetime)
					strDateTime = finaldatetime.strftime(timeformat)
				else:
					lastDate = curdatetime
					strDateTime = matchobj.group(1)
				line = '{} 0.0.0.0 S= {} ﻿{} -- {}\n'.format(strDateTime, matchobj.group(2), matchobj.group(3), matchobj.group(4))
				self._tempFD.write(line)
			if line == 'Status\n':
				break
	
	def _translateDefault(self):
		line = self._sourceFD.readline()
		#Determine what kind of file this is
		while line:
			self._tempFD.write(line)
			line = self._sourceFD.readline()

	def _tokenize(self, line):
		'''Break line into its component parts.
		   Return:  dictionary with the following elements:  timestamp, IP, Host, Level, Source, Message'''
		ret = {}
		expr = re.compile(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\s*(\d+.\d+.\d+.\d+)\s*S=\s*(\S*)\s*\W(\S*)\s*--\s*(.*)')

		mtch = expr.match(line)
		if mtch:
			ret['timestamp'] = mtch.group(1)
			ret['ip'] = mtch.group(2)
			ret['level'] = mtch.group(3)
			ret['source'] = mtch.group(4)
			ret['message'] = mtch.group(5)

		else:
			# This line didn't match our standard format.  Advance to the next line
			ret = self.__next__()

		return ret

	def setIterMode(self, mode):
		if mode.lower() not in ['raw', 'tokenize']:
			raise Exception('Unrecognized Iterator Mode.  Should be "raw" or "tokenize"')

		self._iterMode = mode.lower()

	def open(self):
		#open input file, read contents and modify to generic and write to new (temp) file.
		self._sourceFD = open(self.logFileName, 'r')

		self._tempFD = tempfile.NamedTemporaryFile(mode='w+')  
		self._tempFileName = self._tempFD.name

		# Translate the file now that we've opened it.
		self._translateFile()
		return

	def reset(self):
		#reset file pointer to beginning, and reset Iterator mode.
		self._tempFD.seek(0)
		self.setIterMode('raw')

	def getNextLine(self):
		#return next line from the file
		return self._tempFD.readline()

	def close(self):
		#close log file -- automatically deletes tmp file??
		self._tempFD.close()