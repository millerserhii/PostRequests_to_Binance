import json
from datetime import datetime
import pandas as pd
from binance.client import Client
from binance.enums import *
from flask import Flask, request, render_template, redirect, url_for, flash
from flask_script import Manager
from flask_mail import Mail, Message
from flask_bootstrap import Bootstrap
from model import SettingsForm, ChangePassForm
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash


app = Flask(__name__)


app.config['DEBUG'] = False
app.config['SECRET_KEY'] = "any secret string"
app.config['WTF_CSRF_SECRET_KEY'] = "any secret string"
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///settings.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

manager = Manager(app)
Bootstrap(app)


class ApiSettings(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    API_KEY = db.Column(db.String(100), unique=True, nullable=False)
    WEBHOOK_PASS = db.Column(db.String(100), unique=True, nullable=False)
    MAIL_ADDR = db.Column(db.String(100))
    SECRET_KEY = db.Column(db.String(100), unique=True, nullable=False)
    MAIL_PASS = db.Column(db.String(100))
    MAIL_SMTP_SERVER = db.Column(db.String(100))
    MAIL_RECIPIENT = db.Column(db.String(100))
    MAIL_PORT = db.Column(db.Integer)
    MAIL_TLS = db.Column(db.Boolean)
    MAIL_SSL = db.Column(db.Boolean)

    def __repr__(self):
        return '<User %r>' % self.username


db.create_all()


def order(side, quantity, symbol, order_type=ORDER_TYPE_MARKET):
    client = Client(ApiSettings.query.filter_by(id=1).first().API_KEY,
                    ApiSettings.query.filter_by(id=1).first().SECRET_KEY)
    try:
        print(f"sending order {order_type} - {side} {quantity} {symbol}")
        order = client.create_order(symbol=symbol, side=side, type=order_type, quantity=quantity)
    except Exception as e:
        print(f"an exception occured - {e}")
        result = e
        logs_to_file(side, quantity, ticker, tv_price, result)
        return False
    return order


def get_price(ticker):
    client = Client(ApiSettings.query.filter_by(id=1).first().API_KEY,
                    ApiSettings.query.filter_by(id=1).first().SECRET_KEY)
    ticker_price = client.get_symbol_ticker(symbol=ticker)
    return float(ticker_price["price"])


def check_hike(tv_price, bin_price, side, percent=0):
    if percent != 0:
        ser = [tv_price, bin_price]
        price_series = pd.Series(ser)
        percent_change = round(price_series.pct_change()[1]*100, 2)
        print(f"price change: {percent_change}%")
        if side == "BUY":
            if percent_change <= percent:
                return True
            else:
                return False
        if side == "SELL":
            if percent_change >= (percent*-1):
                return True
            else:
                return False
    else:
        return True


def logs_to_file(side, quantity, ticker, price, result):
    dt = datetime.strftime(datetime.now(), "%Y.%m.%d %H:%M:%S")
    log_message = f"{dt}, {ticker}, {side}, {quantity}, {price}, {result} \n"
    try:
        send_email(log_message)
    except Exception as e:
        print(e)
        with open("logs.txt", 'a') as f:
            f.writelines(f"email error({e}), ")
    with open("logs.txt", 'a') as f:
        f.writelines(log_message)


def logs_to_site(filename):
    with open(filename, 'r') as f:
        log_text = reversed(f.readlines())
    return log_text


def send_email(text):
    app.config['MAIL_SERVER'] = ApiSettings.query.filter_by(id=1).first().MAIL_SMTP_SERVER
    app.config['MAIL_PORT'] = ApiSettings.query.filter_by(id=1).first().MAIL_PORT
    app.config['MAIL_USERNAME'] = ApiSettings.query.filter_by(id=1).first().MAIL_ADDR
    app.config['MAIL_PASSWORD'] = ApiSettings.query.filter_by(id=1).first().MAIL_PASS
    app.config['MAIL_USE_TLS'] = False
    app.config['MAIL_USE_SSL'] = True
    mail = Mail(app)
    msg = Message('Trading LOG', sender=ApiSettings.query.filter_by(id=1).first().MAIL_ADDR,
                  recipients=[ApiSettings.query.filter_by(id=1).first().MAIL_RECIPIENT])
    msg.body = text
    mail.send(msg)
    return "Sent"


def webhook_data():
    global data, side, quantity, ticker, tv_price, percent
    data = json.loads(request.data)
    side = data['side'].upper()
    quantity = data['quoteOrderQty']
    ticker = data['symbol']
    try:
        tv_price = data['marketPrice']
    except KeyError:
        tv_price = 0
    try:
        percent = data['PriceChange%']
    except KeyError:
        percent = 0


@app.route('/')
def welcome():
    return render_template("index.html")


@app.route('/webhook', methods=['POST'])
def webhook():
    webhook_data()
    if not check_password_hash(ApiSettings.query.filter_by(id=1).first().WEBHOOK_PASS, data['passphrase']):
        result = "wrong_pass_error"
        logs_to_file(side, quantity, ticker, tv_price, result)
        return {
            "code": "error",
            "message": "wrong passphrase"
        }

    if check_hike(tv_price, get_price(ticker), side, percent):
        order_response = order(side, quantity, ticker)
    else:
        result = "price_changing_error"
        logs_to_file(side, quantity, ticker, tv_price, result)

        return {
            "code": "error",
            "message": "price changed too much"
        }

    if order_response:
        result = "success"
        logs_to_file(side, quantity, ticker, tv_price, result)
        return {
            "code": "success",
            "message": "order executed"
        }
    else:

        return {
            "code": "error",
            "message": "order failed"
        }


@app.route('/logs')
def logs():
    return render_template(
        "logs.html",
        log_res=logs_to_site("logs.txt")
    )


@app.route('/settings', methods=('GET', 'POST'))
def settings_template():
    form = SettingsForm()
    pass_form = ChangePassForm()
    if form.validate_on_submit():
        if form.FORM_API_KEY.data:
            ApiSettings.query.filter_by(id=1).first().API_KEY = form.FORM_API_KEY.data
            db.session.commit()
        if form.FORM_SECRET_KEY.data:
            ApiSettings.query.filter_by(id=1).first().SECRET_KEY = form.FORM_SECRET_KEY.data
            db.session.commit()
        if form.FORM_EMAIL_TO.data:
            ApiSettings.query.filter_by(id=1).first().MAIL_RECIPIENT = form.FORM_EMAIL_TO.data
            db.session.commit()
        flash("Settings changed", "success")
        return redirect(url_for('settings_template'))
    if request.form.get('Clear log list') == 'Clear log list':
        with open('logs.txt', 'w') as f:
            f.writelines('')
        flash("Log list cleared", "success")
    return render_template('settings.html', pass_form=pass_form, form=form)


@app.route('/change_pass', methods=['POST'])
def change_pass():
    pass_form = ChangePassForm()
    pass_hash = ApiSettings.query.filter_by(id=1).first().WEBHOOK_PASS
    if pass_form.validate_on_submit() and check_password_hash(pass_hash, pass_form.old_pass.data):
        if pass_form.new_pass.data == pass_form.new_pass_repeat.data:
            ApiSettings.query.filter_by(id=1).first().WEBHOOK_PASS = generate_password_hash(pass_form.new_pass_repeat.data)
            db.session.commit()
            flash("Password changed", "success")
        else:
            flash("Passwords aren't equal", "warning")
    else:
        flash("Old password is wrong", "danger")
    return redirect(url_for('settings_template'))


@app.context_processor
def get_settings():
    return dict(
        mail_to=ApiSettings.query.filter_by(id=1).first().MAIL_RECIPIENT,
        api=ApiSettings.query.filter_by(id=1).first().API_KEY,
        secret_api=ApiSettings.query.filter_by(id=1).first().SECRET_KEY
    )
