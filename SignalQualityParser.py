#!/usr/bin/env python3
import sys
import subprocess
import random
import re
from time import strftime, sleep 
import json
import logging
import tempfile
from LogFile import logFile
from bokeh.plotting import figure, output_file, show
from bokeh.models import ColumnDataSource, HoverTool, LinearAxis
from datetime import datetime

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

	def parseLog(self, log, format='plot', view=False):
		formats = ['dict', 'csv', 'plot']
		if format not in formats:
			raise ValueError(' Format {} is not in {}'.format(format, formats))

		data = self._parseLog(log)
		if format == 'plot':
			data = self._getPlot(data, view=view)
		#turn data into a plot
		return data


	def _parseLog(self, log):
		# Find the current signal quality values over time so they can be plotted.
		#  ex: signal MC400LPE (SIM1) on port modem2: 100%, RSSI:-45(dBm), SINR:15.6(dB), RSRP:-68(dB), RSRQ:-7(dB), RFBAND: Band 13
		#  ex: signal MC400LPE (SIM1) on port modem2: 100%, RSSI:-57(dBm), ECIO:-31.5(dBm), RFBAND: CDMA Band Class 0 (800 MHz)
		#  ex: Service Change : Not Reported -> LTE, 100%, RSSI: -45(dBm), SINR: 16.4, RSRP: -68, RSRQ: -7, RFBAND: Band 13
		#   

		#output
		#  {
		#      uid1:{'RSSI':[], 'SINR':[], 'RSRP':[], 'RSRQ':[], 'ECIO':[], 'RFBAND':[]}
		#      uid2:{'RSSI':[], 'SINR':[], 'RSRP':[], 'RSRQ':[], 'ECIO':[], 'RFBAND':[]}
		#  }
		log.setIterMode('tokenize')
		timeformat = r'%Y-%m-%d %H:%M:%S'

		uids = {}
		re_uid_str = r'WAN:([0-9a-f]+)'
		re_end_str = r'{}:(.*)' 		#RF band doesn't have parens
		re_gen_sig_str = r'{}:(.*?)\('  #signal strings in middle of line all have the form: XXXX:<val>(unit)

		sig_strs = {
			#'RFBAND':[re_end_str, None],
			'RSSI':[re_gen_sig_str, self.rssi],
			'SINR':[re_gen_sig_str, self.sinr],
			'RSRP':[re_gen_sig_str, self.rsrp],
			'RSRQ':[re_gen_sig_str, self.rsrq],
			'ECIO':[re_gen_sig_str, self.ecio]
		}
		for line in log:
			src = line['source']
			msg = line['message']
			#print("source: {}, message: {}".format(src, msg))
			match_uid = re.search(re_uid_str, src, flags=0)
			if not match_uid:
				continue
			uid = match_uid.group(1)
			uid_name = 'uid-'+uid
			if uid_name not in uids:
				print("source: {}, message: {}".format(src, msg))
				print("uid: {}".format(uid_name))
				uids[uid_name] = {} #'RSSI':[], 'SINR':[], 'RSRP':[], 'RSRQ':[], 'ECIO':[], 'RFBAND':[]}
			if 'signal' in msg:
				for sig_str in sig_strs:
					#put the leading value in: RSSI or SINR
					vals = []
					search_str = sig_strs[sig_str][0].format(sig_str)
					match_str = re.search(search_str, msg, flags=0)
					if not match_str:
						continue
					val = match_str.group(1)
					if sig_str == 'RSSI' and val == '0':
						val = '-125'
					limits = sig_strs[sig_str][1]
					quality = None
					if not limits:
						continue
					val_int = float(val)
					if val_int >= limits[0]:
						quality = "Excellent"
					elif val_int >= limits[1]:
						quality = "Good"
					elif val_int >= limits[2]:
						quality = "Fair"
					else:
						quality = "Poor"

					timestamp = datetime.strptime(line['timestamp'], timeformat)
					if sig_str not in uids[uid_name]:
						uids[uid_name][sig_str] = []
					uids[uid_name][sig_str].append([timestamp, val, quality ])
		#print(uids)
		final_uids = {}
		for uid in uids:
			#print(uid)
			#print(uids[uid].keys())
			if len(uids[uid].keys()) != 0:
				final_uids[uid] = uids[uid]
		return final_uids

	#
	def _getPlot(self, graphDict, view=False):
		#Function showing an example interpretation of the parseLog functions
		#Features here: Step graph (using mode 'after'), circles on points for better visuals,
		#   Tooltips showing desc data, legend with 'hide' option, y_range using strings
		TOOLTIPS = [
			("Details", "@desc"),
		]
		plots = []
		#print(graphDict)
		for uid in graphDict:
			#if no entries in the series, skip it
			if len(graphDict[uid]) == 0:
				continue
			p=figure(plot_width=1000, x_axis_type='datetime', y_range=(-125,50), tooltips=TOOLTIPS)
			p.title.text = 'Signal Quality Graph {}'.format(uid)
			#Colors here are what will be used to color lines (in order) TODO make sure that we just loop if we hit the end
			colors = iter(['red','blue','green','deepskyblue', 'navy', 'rosybrown', 'darkgoldenrod', ' aquamarine', 'olive', 'orangered', 'orange', 'pink', 'purple', 'indigo',])
			for s in graphDict[uid]:
				if len(graphDict[uid][s]) == 0 or s == 'RFBAND':
					continue
				color = next(colors)
				datetimes = [elt[0] for elt in graphDict[uid][s]]
				#print(datetimes)
				values = [elt[1] for elt in graphDict[uid][s]]
				details =   [str(elt[2]) for elt in graphDict[uid][s]]
				source = ColumnDataSource(data=dict(
					x=datetimes,
					y=values,
					desc=details,
					))
				source1 = source
				source2 = source
				p.circle('x','y', source=source1, color=color, size=8, alpha=0.6, legend=s)
				p.step('x','y', source=source2, line_width=2, mode='after', color=color, alpha=0.6, legend=s)
				#p.add_layout(LinearAxis(y_range_name="{}".format(s)))
			# Format legend
			p.legend.location = "bottom_center"
			p.legend.orientation = "horizontal"
			p.legend.click_policy="hide"
			plots.append(p)
			if view:
				output_file('graph-{}.html'.format(uid)) # Naming our output html doc
				show(p)
		return plots        



class generateOutput(object):
	def __init__(self):
		pass

	def generate(self, data):
		#data:
		#  {
		#      uid1:{'RSSI':[], 'SINR':[], 'RSRP':[], 'RSRQ':[], 'ECIO':[], 'RFBAND':[]}
		#      uid2:{'RSSI':[], 'SINR':[], 'RSRP':[], 'RSRQ':[], 'ECIO':[], 'RFBAND':[]}
		#  }

		for uid in data:
			for series in uid:
				print("Series, name: {}".format(series))
				series_data = uid[series]
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
	

	format = 'plot'
	#format = 'dict'

	lf = logFile(logFileName)
	lf.open()

	sigQ = signalQualityParser()
	d = sigQ.parseLog(lf, format=format, view=(format == 'plot'))
	lf.reset()

	if format == 'dict':
		data.append(d)
		output = generateOutput()
		output.generate(data)
	lf.close()