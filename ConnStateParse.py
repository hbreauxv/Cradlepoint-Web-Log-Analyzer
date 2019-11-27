#!/usr/bin/env python
import argparse
import re
from enum import Enum, auto
from pprint import pprint
from copy import copy
from datetime import datetime
from bokeh.plotting import figure, output_file, show
from bokeh.models import ColumnDataSource, HoverTool
from LogFile import logFile

class ConnStateParse():
    #Wan state enumeration
    class WANState(Enum):
        unplugged = 0
        plugged = auto()
        #configured = auto()
        disconnected = auto()
        disconnecting = auto()
        standby_connecting = auto()
        standby = auto()
        connecting = auto()
        connected = auto()

    class WanEvent:
        timeformat = r'%Y-%m-%d %H:%M:%S'
        def __init__(self, dt, uid, state, details={}):
            self.dt = datetime.strptime(dt, self.timeformat)
            self.dtstr = dt
            # self.dt = dt
            self.uid = uid
            #self.state = ConnStateParse.WANState[state].value  # State as integer from enum
            self.state = state  # state as string
            self.details = copy(details)  # Dictionary of additional event details
            self.details.update({'State':state})
        
        def detailFormat(self):
            ret = ''
            for key in self.details:
                ret += '{}: {}, '.format(key, self.details[key])
            if ret:
                ret = ret[:-2]
            return ret

        #Keep this function in sync with getCSV
        @staticmethod
        def getCSVHeader():
            return 'datetime,uid,stateEnum,details\n'

        def getCSV(self):
            return '{},{},{},"{}"\n'.format(self.dt, self.uid, self.state, self.details)
        
        def getList(self):
            return [self.dt, self.state, self.detailFormat(), self.dtstr]


    #Given a line, return a WANEvent if the line shows one
    #Example lines. Parse out time, uid, last state, new state, reason (if given)
    #2019-04-19 03:37:05 192.168.0.1 S= INFO ﻿WAN:685ca069 -- connecting -> disconnecting
    #2019-04-19 03:35:51 192.168.0.1 S= INFO ﻿WAN:686be2ac -- connecting -> connected, Reason: Failback
    @classmethod
    def _parseDevState(self, line):
        retEvt = None
        rgxDevState = r'^(\d*-\d*-\d* \d*:\d*:\d*).*WAN:(.*) -- (?!Service Change)(.*) -> (.*?)(?:, Reason: (.*))?$'
        matchobj = re.match(rgxDevState, line)
        if matchobj:
            time = matchobj.group(1)
            uid = matchobj.group(2)
            state = matchobj.group(4)
            prevstate = matchobj.group(3)
            reason = matchobj.group(5)
            details = {'PrevState':prevstate}
            if reason:
                details.update({'Reason':reason})
            retEvt = self.WanEvent(time,uid,state,details)
        return retEvt

    @classmethod
    def _parseUnplug(self, line):
        retEvt = None
        rgxUnplug = r'^(\d*-\d*-\d* \d*:\d*:\d*).*WAN:(.*) -- Unplugged$'
        matchobj = re.match(rgxUnplug, line)
        if matchobj:
            time = matchobj.group(1)
            uid = matchobj.group(2)
            state = "unplugged"
            retEvt = self.WanEvent(time,uid,state)
        return retEvt

    @classmethod
    def _parsePlug(self, line):
        retEvt = None
        rgxPlug = r'^(\d*-\d*-\d* \d*:\d*:\d*).*WAN:(.*) -- Plug event: ok$'
        matchobj = re.match(rgxPlug, line)
        if matchobj:
            time = matchobj.group(1)
            uid = matchobj.group(2)
            state = "plugged"
            retEvt = self.WanEvent(time,uid,state)
        return retEvt
    
    @classmethod
    def _parseConfigure(self, line):
        retEvt = None
        rgxConfig = r'^(\d*-\d*-\d* \d*:\d*:\d*).*WAN:(.*) -- Configure Event:.*$'
        matchobj = re.match(rgxConfig, line)
        if matchobj:
            time = matchobj.group(1)
            uid = matchobj.group(2)
            state = "configured"
            retEvt = self.WanEvent(time,uid,state)
        return retEvt

    #Main parsing funcion
    #Given file name parse it and return the specified format
    #Output is {uid:[[time,state,details],],}
    #output optional CSV string of all data
    @classmethod
    def parseLog(self, log, retType):
        retTypes = ['dict', 'csv', 'plot']
        if retType not in retTypes:
            raise ValueError(' retType must be in {}'.format(retTypes))
        #Every function in list below will be executed on every line
        parseFuncs = [self._parseDevState, self._parseUnplug, self._parsePlug] # Every function here should parse a line and return a wanEvt
        log.reset()
        retCSV = self.WanEvent.getCSVHeader()  # Start building string of all parsed data in CSV output format
        retDict = {}
        for line in log:
            for func in parseFuncs:
                evt = func(line)
                if evt:  # If evt not None, we've got a new event to add
                    if retType == 'csv':  # Building CSV output
                        retCSV += evt.getCSV()
                    if retType in ['dict', 'plot']:  # Here we're building dictionary output
                        if not evt.uid in retDict:
                            retDict[evt.uid] = []
                        retDict[evt.uid].append(evt.getList())
                    break
        log.reset()
        # Return format
        if retType == 'csv':
            return retCSV
        if retType == 'dict':
            return retDict
        if retType == 'plot':
            return self.getPlot(retDict)
        
    @classmethod
    def getPlot(self, graphDict, view=False):
        #Function showing an example interpretation of the parseLog functions
        #Features here: Step graph (using mode 'after'), circles on points for better visuals,
        #   Tooltips showing desc data, legend with 'hide' option, y_range using strings
        output_file('graph.html') # Naming our output html doc
        TOOLTIPS = [
            ("Details", "@desc"),
            ("Time", "@dtstr")
        ]
        connStateRange=[x.name for x in ConnStateParse.WANState] #Get list of state strings
        #Colors here are what will be used to color lines (in order) TODO make sure that we just loop if we hit the end
        colors = iter(['red','blue','green','deepskyblue', 'navy', 'rosybrown', 'darkgoldenrod', ' aquamarine', 'olive', 'orangered', 'orange', 'pink', 'purple', 'indigo',])
        p=figure(plot_width=1000, x_axis_type='datetime', y_range=connStateRange, tooltips=TOOLTIPS)
        p.title.text = 'Connection State Graph'
        for uid in graphDict:
            color = next(colors)
            datetimes = [elt[0] for elt in graphDict[uid]]
            stateEnum = [elt[1] for elt in graphDict[uid]]
            details =   [str(elt[2]) for elt in graphDict[uid]]
            dtstrs =    [elt[3] for elt in graphDict[uid]]
            source = ColumnDataSource(data=dict(
                x=datetimes,
                y=stateEnum,
                desc=details,
                dtstr=dtstrs
            ))
            p.step('x','y', source=source, line_width=2, mode='after', color=color, alpha=0.6, legend=uid)
            p.circle('x','y', source=source, color=color, size=8, alpha=0.6, legend=uid)
        # Format legend
        p.legend.location = "bottom_center"
        p.legend.orientation = "horizontal"
        p.legend.click_policy="hide"
        if view:
            show(p)
        return p


if __name__ == '__main__':

    parser = argparse.ArgumentParser(description='The connection health parser')
    parser.add_argument('filename', type=str, help='syslog file to parse')

    args = parser.parse_args()
    filename = args.filename


    #Example usage of the class
    log = logFile(filename)
    log.open()
    resl = ConnStateParse.parseLog(log, 'dict')  # Here we get our standard output. {uid1:[[event1,...eventN],[...]],...uidN:[[]]}
    ConnStateParse.getPlot(resl, view=True)  # Plotting and viewing
    #ConnStateParse.parseLog(filename, 'log')  # Getting a plot back, to be viewed, saved, embedded
    log.close()
    

