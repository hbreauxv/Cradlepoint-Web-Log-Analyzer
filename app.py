from flask import Flask, render_template, flash, redirect, url_for
from flask_socketio import SocketIO, emit
from bokeh.plotting import figure
from bokeh.embed import components
from forms import logFileForm
from ConnStateParse import ConnStateParse
from LogFile import logFile
from SignalQualityParser import signalQualityParser
from os import remove


app = Flask(__name__)
app.config['SECRET_KEY'] = '\x7f[\xce\x97\xf9\x86\x1b\x92YBx/7\xdcX^\xea\xd5\xc4\t~\x8c\xbe\x02'
SIOapp = SocketIO(app)

connStatePlot = None

## View functions
@app.route('/')
def showDashboard():
	form = logFileForm()

	plots = []
	if connStatePlot:
		plots.append(components(connStatePlot))

	return render_template('dashboard.html', plots=plots, form=form)


@app.route('/UploadFile', methods=['POST'])
def uploadFile():
	form = logFileForm()

	if form.validate_on_submit():
		logFileName = form.logFile.data.filename
		savedLocation = 'logFiles/' + logFileName
		form.logFile.data.save(savedLocation)
		flash("LogFile: {} has been submitted".format(logFileName))
		global connStatePlot
		connStatePlot = ConnStateParse.parseLog(savedLocation, 'plot')
		remove(savedLocation)  # don't want these files to build up, remove after parse

	return redirect(url_for('showDashboard'))

## SocketIO communication functions
@SIOapp.on('connect')
def connectHandler():

	print("Client connected")

@SIOapp.on('disconnect')
def disconnectHandler():
	print("Client disconnected")



