import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session , current_app
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    portfolio_data = db.execute("""SELECT portfolio.symbol, stocks.name, portfolio.shares FROM portfolio
                                INNER JOIN stocks ON portfolio.symbol = stocks.symbol WHERE user_id = ?""" , session["user_id"])
    for stock in portfolio_data:
        stock["price"] = lookup(stock["symbol"])["price"]
        stock["value"] = stock["shares"] *  stock["price"]


    user_info = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])
    cash = user_info[0]["cash"]
    total = sum(stock["value"] for stock in portfolio_data) + cash


    return render_template("home.html" , portfolio = portfolio_data ,cash = f"{cash:.2f}" , total = f"{total:.2f}")


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "POST":
        stock_symbol = request.form.get("symbol")
        shares = int(request.form.get("shares"))
        if not stock_symbol:
            return apology("Missing Symbol")
        elif not shares:
            return apology("Missing Shares")
        elif shares <= 0:
            return apology("Share amount cannot be 0 0r negative")
        res = lookup(stock_symbol)
        if res == None:
            return apology("Invalid symbol")
        stock_name, price, stock_symbol = res["name"], res["price"], res["symbol"]
        user_info = db.execute("SELECT * FROM users WHERE id = ?", session["user_id"])
        cost = price * shares
        if cost > user_info[0]["cash"]:
            return apology("You don't have enough funds")
        """ Procesing the purchase and upading the database"""
        # Changing cash value
        db.execute(
            "UPDATE users SET cash = cash - ? WHERE id = ?", cost, session["user_id"]
        )
        # updating the stocks table
        # Checking if symbol in stocks
        e_symbols = db.execute("SELECT * FROM stocks WHERE symbol = ?", stock_symbol)
        if not e_symbols:
            db.execute(
                "INSERT INTO stocks (symbol, name) VALUES (?, ?)",
                stock_symbol,
                stock_name,
            )

        # Portfolio change/insert

        existing_stock = db.execute(
            "SELECT * FROM portfolio WHERE user_id = ? AND symbol = ?",
            session["user_id"],
            stock_symbol,
        )

        if existing_stock:
            # If the stock is already in the portfolio, update the shares
            existing_shares = existing_stock[0]["shares"]
            updated_shares = existing_shares + shares
            db.execute(
                "UPDATE portfolio SET shares = ? WHERE user_id = ? AND symbol = ?",
                updated_shares,
                session["user_id"],
                stock_symbol,
            )
        else:
            # If the stock is not in the portfolio, insert a new entry
            db.execute(
                "INSERT INTO portfolio (user_id, symbol, shares) VALUES (?, ?, ?)",
                session["user_id"],
                stock_symbol,
                shares,
            )

        # Adding to transection
        db.execute(
            "INSERT INTO transactions (user_id, symbol, shares, price, transacted_at, transaction_type) VALUES (?, ?, ?, ?, datetime('now'), 'buy')",
            session["user_id"],
            stock_symbol,
            shares,
            price,
        )
        return redirect("/")
    else:
        return render_template("buy_get.html")


@app.route("/history")
@login_required
def history():

    transactions = db.execute("SELECT * FROM transactions WHERE user_id = ?", session["user_id"])
    current_app.logger.info(transactions)
    return render_template("history.html" , transactions = transactions)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute(
            "SELECT * FROM users WHERE username = ?", request.form.get("username")
        )

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(
            rows[0]["hash"], request.form.get("password")
        ):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    if request.method == "POST":
        symbol = request.form.get("symbol")
        if not symbol:
            return apology("Missing Symbol")
        res = lookup(symbol)
        if res == None:
            return apology("Invalid Symbol")
        name, price, symbol = res["name"], res["price"], res["symbol"]
        return render_template(
            "quote_post.html", name=name, price=f"{price:.2f}", symbol=symbol
        )

    else:
        return render_template("quote_get.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")
        p_hash = generate_password_hash(password)
        userindb = db.execute("Select * from users Where username = ?", username)
        if not username:
            return apology("Username empty")
        elif not password:
            return apology("No password")
        elif not (password == confirmation):
            return apology("Password doesn't match")
        elif len(userindb) != 0:
            return apology("Username already taken")
        else:
            db.execute(
                "Insert INTO users (username , hash ) VALUES(?, ?)", username, p_hash
            )
            rows = db.execute("SELECT * FROM users WHERE username = ?", username)
            session["user_id"] = rows[0]["id"]
            return redirect("/")

    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    user_info = db.execute("SELECT * FROM users WHERE id = ?", session["user_id"])
    user_portfolio = db.execute("SELECT * FROM portfolio WHERE user_id = ?", session["user_id"])
##converting in my favoravle form
    portfolio_dict = {}
    for item in user_portfolio:
        symbol = item['symbol']
        shares = item['shares']
        portfolio_dict[symbol] = shares
    stocks_owned = list(portfolio_dict.keys())
    current_app.logger.info(stocks_owned)
    """Sell shares of stock"""
    if request.method == "POST":
        stock_symbol = request.form.get("symbol")
        shares = request.form.get("shares")
        if not stock_symbol:
            return apology("Select a symbol")
        elif not shares:
            return apology("Missing Shares")
        elif int(shares) <= 0:
            return apology("Share amount cannot be 0 0r negative")
        res = lookup(stock_symbol)
        shares = int(shares)
        if res == None:
            return apology("Invalid symbol")
        stock_name, price, stock_symbol = res["name"], res["price"], res["symbol"]
        if stock_symbol not in stocks_owned:
            return apology("You don't own the stock")
        elif shares > portfolio_dict[stock_symbol]:
            return apology("You don't own enough shares")
##Checks done stocks are valid updating databses
        earnings = price * shares
        updated_cash = user_info[0]["cash"] + earnings
        db.execute("UPDATE users SET cash = ? WHERE id = ?", updated_cash, session["user_id"])

        ##updating portfolio table
        updated_shares = portfolio_dict[stock_symbol] - shares
        if updated_shares == 0:
            db.execute("DELETE FROM portfolio WHERE user_id = ? AND symbol = ?", session["user_id"], stock_symbol)
        else:
            db.execute("UPDATE portfolio SET shares = ? WHERE user_id = ? AND symbol = ?", updated_shares, session["user_id"], stock_symbol)
##updating transection
        db.execute(
        "INSERT INTO transactions (user_id, symbol, shares, price, transacted_at, transaction_type) VALUES (?, ?, ?, ?, datetime('now'), 'sell')",
        session["user_id"],
        stock_symbol,
        shares,
        price,
        )
        return redirect("/")

    else:
        return render_template("sell_get.html" , stocks_owned = stocks_owned)
