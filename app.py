from flask import Flask, render_template, flash, redirect, url_for
from bokeh.plotting import figure
from bokeh.embed import components
from forms import logFileForm
from ConnStateParse import ConnStateParse

app = Flask(__name__)
app.config['SECRET_KEY'] = '\x7f[\xce\x97\xf9\x86\x1b\x92YBx/7\xdcX^\xea\xd5\xc4\t~\x8c\xbe\x02'

connStatePlot = None

@app.route('/')
def showDashboard():
	form = logFileForm()

	plots = []
	plots.append(makePlot())
	if connStatePlot:
		plots.append(components(connStatePlot))

	return render_template('dashboard.html', plots=plots, form=form)


@app.route('/UploadFile', methods=['POST'])
def uploadFile():
	form = logFileForm()

	if form.validate_on_submit():
		logFileName = form.logFile.data.filename
		form.logFile.data.save('logFiles/' + logFileName)
		flash("LogFile: {} has been submitted".format(logFileName))
		global connStatePlot
		connStatePlot = ConnStateParse.parseLog('logFiles/' + logFileName, 'plot')

	return redirect(url_for('showDashboard'))

def makePlot():
	plot = figure(plot_height=150, sizing_mode='scale_width')

	x = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]
	y = [2**v for v in x]
	plot.line(x, y, line_width=4)

	script, div = components(plot)
	return script, div
