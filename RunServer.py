from app import app
import os
import glob

logFileDir = 'logFiles/'

if __name__ == '__main__':
    try:
        for file in glob.glob(logFileDir+"*.log"):
            os.remove(file)
    except Exception as e:
        print('Unable to clear log file dir. E: {}'.format(e))


    app.run(host='0.0.0.0', port=5000)
    # app.run(host='0.0.0.0', port=80) # This has to be run as root on linux, but then you don't have to specify the port