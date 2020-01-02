from flask import Flask, render_template, flash, redirect, url_for, session
from bokeh.plotting import figure
from bokeh.embed import components
from forms import logFileForm
from ConnStateParse import ConnStateParse
from LogFile import logFile
from SignalQualityParser import signalQualityParser
from scan_log import ScanLog
from os import remove

app = Flask(__name__)
app.config['SECRET_KEY'] = '\x7f[\xce\x97\xf9\x86\x1b\x92YBx/7\xdcX^\xea\xd5\xc4\t~\x8c\xbe\x02'

scanner = ScanLog(None, None, log_database='./log_messages.json')


## View functions
@app.route('/')
def showDashboard():
    form = logFileForm()

    plots = []
    analysis = ''
    fileNameLoc = session.pop('logFileLoc', None)
    if fileNameLoc:
        plots = generatePlots(fileNameLoc)
        analysis = search_log(fileNameLoc)
        remove(fileNameLoc)

    return render_template('dashboard.html', plots=plots, form=form, analysis=analysis)


@app.route('/UploadFile', methods=['POST'])
def uploadFile():
    form = logFileForm()

    if form.validate_on_submit():
        logFileName = form.logFile.data.filename
        savedLocation = 'logFiles/' + logFileName
        form.logFile.data.save(savedLocation)
        flash("LogFile: {} has been submitted".format(logFileName))

        session.pop('logFileLoc', None)  # clear old logFileLoc from session
        session['logFileLoc'] = savedLocation

    return redirect(url_for('showDashboard'))

@app.route('/log_messages', methods=['GET'])
def showMessages():
    with open("log_messages.json", "r") as f:
        j = f.read()
    return j


@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404


@app.errorhandler(500)
def server_error(e):
    return render_template('500.html'), 500


def generatePlots(logFileLoc):
    plots = []
    try:
        log = logFile(logFileLoc)
        log.open()
    except FileNotFoundError as e:
        print('Could not find file: {}'.format(e))
        return []

    connStatePlot = ConnStateParse.parseLog(log, 'plot')
    plots.append(components(connStatePlot))

    sigQParse = signalQualityParser()
    sigQPlot = sigQParse.parseLog(log, 'plot')

    for figure in sigQPlot:
        plots.append(components(figure))


    # this line breaks things on windows
    # remove(logFileLoc)  # don't want these files to build up, remove after parse

    return plots


def search_log(logFileLoc):
    """Search Log file for problematic messages"""
    problem_messages = []

    try:
        log = logFile(logFileLoc)
        log.open()
    except FileNotFoundError as e:
        print('Could not find file: {}'.format(e))
        return []

    scanner.input_file = logFileLoc
    problem_messages = scanner.search_log()

    return problem_messages
