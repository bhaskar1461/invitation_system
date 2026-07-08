from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileRequired, FileAllowed
from wtforms import StringField, PasswordField, SubmitField, HiddenField
from wtforms.validators import DataRequired, Email, Length

class LoginForm(FlaskForm):
    email = StringField('Email Address', validators=[DataRequired(), Email(), Length(max=120)])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Log In')

class GuestForm(FlaskForm):
    name = StringField('Guest Name', validators=[DataRequired(), Length(max=100)])
    rollno = StringField('Roll Number', validators=[Length(max=50)])
    mobile = StringField('Mobile Number', validators=[Length(max=20)])
    email = StringField('Email Address', validators=[DataRequired(), Email(), Length(max=120)])
    submit = SubmitField('Save Guest')

class ExcelUploadForm(FlaskForm):
    excel_file = FileField('Excel Spreadsheet (.xlsx)', validators=[
        FileRequired(),
        FileAllowed(['xlsx'], 'Excel files (.xlsx) only!')
    ])
    submit = SubmitField('Upload')

class EmptyForm(FlaskForm):
    # Form used strictly for CSRF validation on actions (like sending emails or deleting guests)
    pass
