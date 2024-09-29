from flask import Flask, render_template, request, session, redirect, url_for, jsonify
from flask_sqlalchemy import SQLAlchemy
import bcrypt
import math
import random

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
db = SQLAlchemy(app)
app.secret_key = 'your-secret-key'

# Dummy data for demo stocks
demo_stocks = [
    {"name": "Stock A", "price": 10.00, "profit_loss": 2.0},
    {"name": "Stock B", "price": 8.50, "profit_loss": -1.5},
    {"name": "Stock C", "price": 15.30, "profit_loss": 5.0},
    {"name": "Stock D", "price": 12.75, "profit_loss": -2.0},
    {"name": "Stock E", "price": 6.80, "profit_loss": 3.5}
]

# User Model
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    account_balance = db.Column(db.Float, nullable=False, default=100.00)
    wallet_balance = db.Column(db.Float, nullable=False, default=0.00)
    transactions = db.relationship('Transaction', backref='user', lazy=True)
    investments = db.relationship('Investment', backref='user', lazy=True)

    def __init__(self, email, password, name):
        self.name = name
        self.email = email
        self.password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

    def check_password(self, password):
        return bcrypt.checkpw(password.encode('utf-8'), self.password.encode('utf-8'))

# Transaction Model
class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.String(50), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    date = db.Column(db.DateTime, nullable=False, default=db.func.current_timestamp())
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

# Investment Model
class Investment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    stock_name = db.Column(db.String(100), nullable=False)
    invested_amount = db.Column(db.Float, nullable=False)
    profit_loss = db.Column(db.Float, nullable=False, default=0.0)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

# Route to handle both GET (show the payment page) and POST (handle payment and deposit)
@app.route('/pay', methods=['GET', 'POST'])
def handle_payment():
    if 'email' not in session:
        return redirect('/new_index')

    user = User.query.filter_by(email=session['email']).first()

    if request.method == 'POST':
        if 'payment_amount' in request.form:
            payment_amount = float(request.form['payment_amount'])

            # Round up to the next dollar
            next_dollar = math.ceil(payment_amount)
            wallet_addition = next_dollar - payment_amount  # Amount to add to wallet
            
            # Check if user has enough balance for the rounded-up amount
            if next_dollar > user.account_balance:
                return render_template('account_info.html', name=user.name, account_balance=round(user.account_balance, 2), error="Insufficient balance to complete payment.")

            # Deduct the next rounded dollar amount from account balance
            user.account_balance -= next_dollar

            # Add the difference to wallet
            user.wallet_balance += round(wallet_addition, 2)

            # Log the payment transaction
            new_transaction = Transaction(type="Payment", amount=next_dollar, user_id=user.id)
            db.session.add(new_transaction)
            db.session.commit()

            return render_template('account_info.html', name=user.name, account_balance=round(user.account_balance, 2), success="Payment processed successfully.")

        elif 'deposit_amount' in request.form:
            deposit_amount = float(request.form['deposit_amount'])
            if deposit_amount > 0:
                user.account_balance += deposit_amount
                new_transaction = Transaction(type="Deposit", amount=deposit_amount, user_id=user.id)
                db.session.add(new_transaction)
                db.session.commit()
            return redirect(url_for('handle_payment'))

    return render_template('account_info.html', name=user.name, account_balance=round(user.account_balance, 2))

# Route to add money to wallet
@app.route('/add_to_wallet', methods=['POST'])
def add_to_wallet():
    if 'email' not in session:
        return redirect('/new_index')

    user = User.query.filter_by(email=session['email']).first()

    try:
        wallet_amount = round(float(request.form['wallet_amount']), 2)

        if wallet_amount <= 0:
            return render_template('wallet.html', name=user.name, wallet_balance=round(user.wallet_balance, 2), error="Amount must be positive")

        user.wallet_balance += wallet_amount
        db.session.commit()

        new_transaction = Transaction(type="Wallet Deposit", amount=wallet_amount, user_id=user.id)
        db.session.add(new_transaction)
        db.session.commit()

        invest_wallet(user)

        return redirect('/wallet')

    except ValueError:
        return render_template('wallet.html', name=user.name, wallet_balance=round(user.wallet_balance, 2), error="Invalid input. Please enter a valid number.")

# Function to auto-invest from wallet when balance reaches $3
def invest_wallet(user):
    if user.wallet_balance >= 3:
        best_stock = random.choice(demo_stocks)
        investment_amount = user.wallet_balance

        user.wallet_balance = 0.00
        db.session.commit()

        new_transaction = Transaction(type="Investment", amount=investment_amount, user_id=user.id)
        db.session.add(new_transaction)

        new_investment = Investment(stock_name=best_stock['name'], invested_amount=investment_amount, profit_loss=best_stock['profit_loss'], user_id=user.id)
        db.session.add(new_investment)
        db.session.commit()

# Route to update stock prices dynamically and update investments accordingly
@app.route('/update_prices')
def update_prices():
    for stock in demo_stocks:
        stock['profit_loss'] += random.uniform(-5, 5)
        stock['price'] = round(min(stock['price'] * (1 + stock['profit_loss'] / 100), 20), 2)  # Cap stock price at $20

    investments = Investment.query.all()
    for investment in investments:
        for stock in demo_stocks:
            if investment.stock_name == stock['name']:
                investment.profit_loss = stock['profit_loss']
                db.session.commit()

    return jsonify(demo_stocks)

# Route to view wallet balance
@app.route('/wallet')
def wallet():
    if 'email' not in session:
        return redirect('/new_index')

    user = User.query.filter_by(email=session['email']).first()
    return render_template('wallet.html', name=user.name, wallet_balance=round(user.wallet_balance, 2))

# Route to view recent transactions
@app.route('/transactions')
def transactions():
    if 'email' not in session:
        return redirect('/new_index')

    user = User.query.filter_by(email=session['email']).first()

    transactions = Transaction.query.filter_by(user_id=user.id).order_by(Transaction.date.desc()).all()

    return render_template('transactions.html', name=user.name, transactions=transactions)

# Route to display dashboard
@app.route('/dashboard')
def dashboard():
    if 'email' not in session:
        return redirect('/new_index')

    user = User.query.filter_by(email=session['email']).first()
    investments = Investment.query.filter_by(user_id=user.id).all()

    transactions = Transaction.query.filter_by(user_id=user.id).order_by(Transaction.date.desc()).all()

    return render_template('dashboard.html', name=user.name, demo_stocks=demo_stocks, investments=investments, transactions=transactions)

# User authentication routes
@app.route('/')
def index():
    return render_template('new_index.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']

        if User.query.filter_by(email=email).first():
            return render_template('signup.html', error='User already exists with that email')

        new_user = User(name=name, email=email, password=password)
        db.session.add(new_user)
        db.session.commit()
        return redirect('/new_index')

    return render_template('signup.html')

@app.route('/new_index', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        user = User.query.filter_by(email=email).first()

        if user and user.check_password(password):
            session['email'] = user.email
            return redirect('/dashboard')
        else:
            return render_template('new_index.html', error='Invalid credentials')

    return render_template('new_index.html')

@app.route('/logout')
def logout():
    session.pop('email', None)
    return redirect('/new_index')

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
