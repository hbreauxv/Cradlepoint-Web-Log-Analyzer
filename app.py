from flask import Flask, render_template, flash, redirect, url_for, session
from bokeh.plotting import figure
from bokeh.embed import components
from forms import logFileForm
from ConnStateParse import ConnStateParse
from LogFile import logFile
from SignalQualityParser import signalQualityParser
from os import remove


app = Flask(__name__)
app.config['SECRET_KEY'] = '\x7f[\xce\x97\xf9\x86\x1b\x92YBx/7\xdcX^\xea\xd5\xc4\t~\x8c\xbe\x02'


## View functions
@app.route('/')
def showDashboard():
	form = logFileForm()

	plots = []
	fileNameLoc = session.pop('logFileLoc', None)
	if fileNameLoc:
		plots = generatePlots(fileNameLoc)

	return render_template('dashboard.html', plots=plots, form=form)

@app.route('/UploadFile', methods=['POST'])
def uploadFile():
	form = logFileForm()

	if form.validate_on_submit():
		logFileName = form.logFile.data.filename
		savedLocation = 'logFiles/' + logFileName
		form.logFile.data.save(savedLocation)
		flash("LogFile: {} has been submitted".format(logFileName))

		session.pop('logFileLoc', None) #clear old logFileLoc from session
		session['logFileLoc'] = savedLocation

	return redirect(url_for('showDashboard'))


def generatePlots(logFileLoc):

	plots = []
	log = logFile(logFileLoc)
	log.open()

	connStatePlot = ConnStateParse.parseLog(log, 'plot')
	plots.append(components(connStatePlot))

	sigQParse = signalQualityParser()
	sigQPlot = sigQParse.parseLog(log, 'plot')

	for figure in sigQPlot:
		plots.append(components(figure))


	remove(logFileLoc)  # don't want these files to build up, remove after parse

	return plots