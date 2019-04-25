#!/usr/bin/env python3
import sys
import subprocess
import random
import re
from time import strftime, sleep 
import json
import logging
import tempfile


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
		line = self._sourceFD.readline()

		while line:
			self._tempFD.write(line)

			line = self._sourceFD.readline()

		self.reset()

	def _tokenize(self, line):
		'''Break line into its component parts.
		   Return:  dictionary with the following elements:  timestamp, IP, Host, Level, Source, Message'''
		ret = {}
		expr = re.compile('(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\s*(\d+.\d+.\d+.\d+)\s*S=\s*(\S*)\s*\W(\S*)\s*--\s*(.*)')

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