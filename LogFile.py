#!/usr/bin/env python3
import sys
import subprocess
import random
import re
from time import strftime, sleep 
import json
import logging
import tempfile
from datetime import datetime, timedelta


# Base Class for all translators
class LogTranslator(object):
	'''Base class for custom translator classes.  Translators will read a log file in one format (like
	   NCM export, router UI export, syslog, CLI log command, etc), and emit a "common" log file used
	   by the various log file parsers for user-friendly consumption.'''
	OUTPUT_FORMAT = '{}  {} S= {} \ufeff{}  --  {}\n'
	# Out Format:   DATE IP    lvl      src      msg
	OUTPUT_DATE_FORMAT = '%Y-%m-%d %H:%M:%S'

	def __init__(self):
		super().__init__()

		# Interface flags
		self._abortParse = False		# Stop parsing the file (we're done with log content)

	@classmethod
	def detect(cls, logFile):
		'''Detect the source file type for this translator.  Return True if the source logFile appears
		   to be a log file of this type, False otherwise.  Note that you should reset the file pointer
		   if you are going to return False, as another "detector" function will be invoked using the 
		   same file pointer.  If you return True, it is acceptable to leave the pointer wherever you please,
		   as the next method to be invoked will be the file translate method.'''
		pass

	@property
	def abort(self):
		'''Interface method to inform caller that parsing is finished before the file-end.  Useful for
		   aggregated logs that only need to look at a portion of the log file.'''
		return self._abortParse

	def writeOutputLine(self, timestamp, ip, logLevel, msgSource, logMessage):
		'''Helper method for writing output messages.  Called by translateLine'''
		return self.OUTPUT_FORMAT.format(timestamp, ip, logLevel, msgSource, logMessage)

	def translateLine(self, ln):
		'''Translate an individual line of a log file into the common log output format.  If the line does
		   not match, return None to avoid writing anything to the output file.  Should be overridden.'''
		return ln


class SyslogTranslator(LogTranslator):
	@classmethod
	def detect(cls, logFile):
		expr = re.compile(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\s*(\d+.\d+.\d+.\d+)\s*S=\s*(\S*)\s*\W(\S*)\s*--\s*(.*)')

		lineNo = logFile.tell()	 # Get the current file position
		line = logFile.readline()
		logFile.seek(lineNo)

		if expr.match(line):
			return True
		else:
			return False

	def __init__(self):
		super().__init__()

	def translateLine(self, ln):
		'''Translate an individual line of a log file into the common log output format.  If the line does
		   not match, return None to avoid writing anything to the output file.  Should be overridden.'''
		return ln


class RouterUIExportTranslator(LogTranslator):
	'''Translator for log files exported from router UI "Export Log" button'''
	REGEX = re.compile(r'(\S{3} \S{3} \d{2} \d{2}:\d{2}:\d{2} \d{4})\|([A-Z]*)\|([A-Za-z0-9_:\[\]\.]*)\|(.*)')

	def __init__(self):
		super().__init__()

	@classmethod
	def detect(cls, logFile):
		lineNo = logFile.tell()	 # Get the current file position
		line = logFile.readline()
		logFile.seek(lineNo)  		 # Restore the file pointer


		if RouterUIExportTranslator.headerPresent(logFile) or RouterUIExportTranslator.REGEX.match(line):
			return True
		else:
			return False

	@classmethod
	def headerPresent(cls, logFile):
		'''
		   Utility function to determine if the log file begins with the header at the start of the router log exported
		   by the router UI.  Sample header:
				Firmware Type: RELEASE
				Firmware Version: 7.0.10.2728fcc
				Firmware Build Date: Tue Nov 27 02:00:56 UTC 2018
				Product Name: IBR900LP6
		  '''
		regexes = ['Firmware Type: \S*',
				   'Firmware Version: \S*',
				   'Firmware Build Date: \S{3} \S{3}\s*\d{1,2} \d{2}:\d{2}:\d{2} \S{3} \d{4}',
				   'Product Name: \S*']
		lineNo = 0

		logFile.seek(0)  # Go back to start of file.

		while lineNo < 4:
			line = logFile.readline()
			reg = re.compile(regexes[lineNo])
			if not reg.match(line):
				logFile.seek(0)  # Restore the file pointer.
				return False
			lineNo += 1
		# If we get here and have matched all of the items, this sure appears to be a Router UI
		return True

	def translateLine(self, ln):
		'''Translate a Log file from the router UI.  Basically, parse the log, transform lines to our desired format &
		   return for writing to the file.'''
		mtch = RouterUIExportTranslator.REGEX.match(ln)
		if mtch:
			timestamp_str = mtch.group(1)
			level = mtch.group(2)
			source = mtch.group(3)
			msg = mtch.group(4)
			ip = '0.0.0.0'  # The log file doesn't have the IP.  Supply one.

			timestamp = datetime.strptime(timestamp_str, '%a %b %d %H:%M:%S %Y')

			return self.writeOutputLine(timestamp.strftime(self.OUTPUT_DATE_FORMAT), ip, level, source, msg)
		else:
			# This line doesn't match.  Don't return any text.
			return None


class ncmSupportlogTranslator(LogTranslator):
	'''Translator for log files exported from NCM "Export" method'''
	def __init__(self):
		super().__init__()
		# State variables
		self._lastDate = None
		self._offsetDate = None
		self._lastCorrectDate = None

	@classmethod
	def detect(cls, logFile):
		lineNo = logFile.tell()
		logFile.seek(0)
		for i in range(2):
			logFile.readline()
		line = logFile.readline()
		# Restore the line number
		logFile.seek(lineNo)
		return line == "ECM Info\n"
	
	def translateLine(self, ln):
		ncm_rgx = r'^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\|\s*(\S*)\|\s*(\S*)\|(.*)$'
		         #   (           Date                    ) | (Level) | (Source)|(Message)

		matchobj = re.match(ncm_rgx, ln)
		if matchobj:
			curdatetime = datetime.strptime(matchobj.group(1), self.OUTPUT_DATE_FORMAT)

			# This stuff gets kinda janky, but it's a functioning first pass for dealing with the 1969 issue
			if not self._offsetDate and curdatetime.year == 1969: # Save last correct date
				self._offsetDate = curdatetime
				self._lastCorrectDate = self._lastDate
			if curdatetime.year == 1969:
				finaldatetime = self._lastCorrectDate - (self._offsetDate - curdatetime)
				strDateTime = finaldatetime.strftime(self.OUTPUT_DATE_FORMAT)
			else:
				self._lastDate = curdatetime
				strDateTime = matchobj.group(1)

				return self.writeOutputLine(strDateTime, '0.0.0.0', matchobj.group(2), matchobj.group(3), matchobj.group(4))

		if ln == 'Status\n':
			self._abortParse = True

		return None


class usbLogTranslator(LogTranslator):
	'''Translator for logs collected via USB.'''
	REGEX = re.compile(r'(\d+)\s*([a-z\.]+)\s*([A-Za-z0-9_:\[\]\.]+)\s*(.+)\n')
	#       (date?) (source)  (level) (message)

	def __init__(self):
		super().__init__()

		self.baseDate = datetime.strptime('1969-12-31 18:00:00', self.OUTPUT_DATE_FORMAT)
		self.logStartTime = None

	@classmethod
	def detect(cls, logFile):
		lineNo = logFile.tell()	 # Get the current file position
		line = logFile.readline()
		logFile.seek(lineNo)  		 # Restore the file pointer

		if usbLogTranslator.REGEX.match(line):
			return True
		else:
			return False

	def transformTimestamp(self, time):
		if self.logStartTime is None:
			self.logStartTime = int(time)

			retTime = self.baseDate
		else:
			diff = int(time) - self.logStartTime

			retTime = self.baseDate + timedelta(seconds=diff)

		return retTime.strftime(self.OUTPUT_DATE_FORMAT)


	def translateLine(self, ln):
		mtch = usbLogTranslator.REGEX.match(ln)
		if mtch:
			timestamp_str = self.transformTimestamp(mtch.group(1))
			level = mtch.group(2)
			source = mtch.group(3)
			msg = mtch.group(4)
			ip = '0.0.0.0'  # The log file doesn't have the IP.  Supply one.

			if source.endswith(':'):
				source = source[:-1]

			return self.writeOutputLine(timestamp_str, ip, level, source, msg)
		else:
			# This line doesn't match.  Don't return any text.
			return None


class logFile(object):
	def __init__(self, logFileName):
		self.logFileName = logFileName
		self._fileFormat = None
		self._sourceFD = None
		self._tempFileName = None
		self._tempFD = None
		self._iterMode = 'raw'
		self._translator = None

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
		self._autoDetectFormat()

		ln = self._sourceFD.readline()

		while ln:
			translated_line = self._translator.translateLine(ln)
			if translated_line is not None:
				self._tempFD.write(translated_line)

			if self._translator.abort:
				break

			ln = self._sourceFD.readline()

		self.reset()

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

	def _autoDetectFormat(self):

		logFileTranslators = [SyslogTranslator,  # Syslog listener as produced by WANTester
							  RouterUIExportTranslator,  # Log file exported from router UI
							  ncmSupportlogTranslator,		# NCM Support log
							  usbLogTranslator]				# USB Log file

		for trans in logFileTranslators:
			if trans.detect(self._sourceFD):
				self._translator = trans()
				break

		if self._translator is None:
			# Unrecognized format. Graphs wont work, interpret as router log to at least get message analysis
			self._translator = RouterUIExportTranslator()
			print("Log Format not detected, graphs will probably not be generated")
			# raise Exception('Unrecognized File Format')

	def setIterMode(self, mode):
		if mode.lower() not in ['raw', 'tokenize']:
			raise Exception('Unrecognized Iterator Mode.  Should be "raw" or "tokenize"')

		self._iterMode = mode.lower()

	def open(self):
		#open input file, read contents and modify to generic and write to new (temp) file.
		self._sourceFD = open(self.logFileName, 'r')

		self._tempFD = tempfile.NamedTemporaryFile(mode='w+', encoding='UTF-8')
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
