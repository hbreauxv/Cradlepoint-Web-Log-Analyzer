from app import app

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
    # app.run(host='0.0.0.0', port=80) # This has to be run as root on linux, but then you don't have to specify the port