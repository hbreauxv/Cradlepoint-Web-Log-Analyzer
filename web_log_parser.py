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


class connectionStateParser(object):
	def __init__(self):
		pass

	def parseLog(self, logFile):
		output = {}
		#series1 = [[1,1,"stateone-1"],[2,2,"stateone-2"],[3,3,"stateone-3"]]
		#series2 = [[1,0,"statetwo-1"],[2,0,"statetwo-2"],[3,0,"statetwo-3"]]
		#output['state_series1'] = series1
		#output['state_series2'] = series2
		return output

class signalQualityParser(object):
	def __init__(self):
		# excellent = if greater or equal to [0], 
		# good = if greater than [1] but less than [0]
		# fair = if greater than [2] but less than [1],
		# poor = if less than [2] 
		self.rssi = [-67, -70,  -80] 
		self.sinr = [ 20,  13,    0] 
		self.rsrp = [-80, -90, -100] 
		self.rsrq = [-10, -15,  -20] 
		self.ecio = [ -6, -10,  -20] 

	def parseLog(self, logFileObject):
		# Find the current signal quality values over time so they can be plotted.
		#  ex: signal MC400LPE (SIM1) on port modem2: 100%, RSSI:-45(dBm), SINR:15.6(dB), RSRP:-68(dB), RSRQ:-7(dB), RFBAND: Band 13
		#  ex: signal MC400LPE (SIM1) on port modem2: 100%, RSSI:-57(dBm), ECIO:-31.5(dBm), RFBAND: CDMA Band Class 0 (800 MHz)
		#  ex: Service Change : Not Reported -> LTE, 100%, RSSI: -45(dBm), SINR: 16.4, RSRP: -68, RSRQ: -7, RFBAND: Band 13
		#   

		logFileObject.setIterMode('tokenize')

		uids = {}
		re_uid_str = r'WAN:([0-9a-f]+)'
		re_end_str = r'{}:(.*)'         #RF band doesn't have parens
		re_gen_sig_str = r'{}:(.*?)\('  #signal strings in middle of line all have the form: XXXX:<val>(unit)

		sig_strs = {
					'RSSI':[re_gen_sig_str, self.rssi],
					'SINR':[re_gen_sig_str, self.sinr],
					'RSRP':[re_gen_sig_str, self.rsrp],
					'RSRQ':[re_gen_sig_str, self.rsrq],
					'ECIO':[re_gen_sig_str, self.ecio],
					'RFBAND':[re_end_str, None]
		}
		for line in logFileObject:
			src = line['source']
			msg = line['message']
			#print("source: {}, message: {}".format(src, msg))
			match_uid = re.search(re_uid_str, src, flags=0)
			if match_uid:
				uid = match_uid.group(1)
				uid_name = 'uid-'+uid
				if uid_name not in uids:
					print("source: {}, message: {}".format(src, msg))
					print("uid: {}".format(uid_name))
					uids[uid_name] = {'RSSI':[], 'SINR':[], 'RSRP':[], 'RSRQ':[], 'ECIO':[], 'RFBAND':[]}
				if 'signal' in msg:
					for sig_str in sig_strs:
						#put the leading value in: RSSI or SINR
						search_str = sig_strs[sig_str][0].format(sig_str)
						match_str = re.search(search_str, msg, flags=0)
						if match_str:
							val = match_str.group(1)
							limits = sig_strs[sig_str][1]
							quality = None
							if limits:
								val_int = float(val)
								quality = None
								if val_int >= limits[0]:
									quality = "Excellent"
								elif val_int >= limits[1]:
									quality = "Good"
								elif val_int >= limits[2]:
									quality = "Fair"
								else:
									quality = "Poor"

							uids[uid_name][sig_str].append([line['timestamp'], val, quality ])

		#print(uids)
		return uids


class gpsParser(object):
	def __init__(self):
		pass

	def parseLog(self, logFileObject):
		pass


class generateOutput(object):
	def __init__(self):
		pass

	def generate(self, data):
		for d in data:
			for series in d:
				print("Series, name: {}".format(series))
				series_data = d[series]
				if isinstance(series_data, dict):
					for sd in series_data:
						print("  sub name: {}".format(sd))
						for s in series_data[sd]:
							print("    {}".format(s))
						
				else:
					for sd in series_data:
						print("  data: {}".format(sd))



if __name__ == "__main__":
	data = []
	if len(sys.argv) > 1:
		logFileName = sys.argv[1]
	else:
		logFileName = input('Enter log file name: ')
	

	lf = logFile(logFileName)
	lf.open()
	connect = connectionStateParser()
	data.append(connect.parseLog(lf))
	lf.reset()

	quality = signalQualityParser()
	data.append(quality.parseLog(lf))
	lf.reset()

	output = generateOutput()
	output.generate(data)
	lf.close()
