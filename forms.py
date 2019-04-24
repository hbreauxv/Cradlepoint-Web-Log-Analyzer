from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileRequired

class logFileForm(FlaskForm):
	logFile = FileField(validators=[FileRequired()])
