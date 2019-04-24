from flask import Flask, render_template, flash
from bokeh.plotting import figure
from bokeh.embed import components
from forms import logFileForm

app = Flask(__name__)
app.config['SECRET_KEY'] = '\x7f[\xce\x97\xf9\x86\x1b\x92YBx/7\xdcX^\xea\xd5\xc4\t~\x8c\xbe\x02'


@app.route('/', methods=['GET', 'POST'])
def showDashboard():
	form = logFileForm()

	if form.validate_on_submit():
		logFileName = form.logFile.data.filename
		form.logFile.data.save('logFiles/' + logFileName)
		flash("LogFile: {} has been submitted".format(logFileName))


	plots = []
	plots.append(makePlot())

	return render_template('dashboard.html', plots=plots, form=form)




def makePlot():
	plot = figure(plot_height=150, sizing_mode='scale_width')

	x = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]
	y = [2**v for v in x]
	plot.line(x, y, line_width=4)

	script, div = components(plot)
	return script, div
