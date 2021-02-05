from flask_wtf import FlaskForm
from wtforms import SubmitField, StringField, validators, PasswordField


class SettingsForm(FlaskForm):
    FORM_API_KEY = StringField("Binance API Key: ", validators=[validators.Optional()])
    FORM_SECRET_KEY = StringField("Binance Secret Key: ", validators=[validators.Optional()])
    FORM_EMAIL_TO = StringField("Email to: ", validators=[validators.Email(), validators.Optional()])

    submit = SubmitField("Submit")


class ChangePassForm(FlaskForm):
    old_pass = PasswordField("Old password: ", validators=[validators.DataRequired()])
    new_pass = PasswordField("New password: ", validators=[validators.DataRequired()])
    new_pass_repeat = PasswordField("Confirm password: ", validators=[validators.DataRequired()])

    submit = SubmitField("Submit")
