
import os
import cloudinary
import cloudinary.uploader
from dotenv import load_dotenv


from werkzeug.utils import secure_filename
from flask import request

from flask import Flask, render_template, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta


from dotenv import load_dotenv
load_dotenv()


cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET")
)
import cloudinary
import cloudinary.uploader



app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "fallback-secret")



# -------------------- DATABASE CONFIG --------------------
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///restaurant.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# -------------------- MODELS --------------------

class Menu(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Integer, nullable=False)
    image = db.Column(db.String(200), nullable=False)


class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    total = db.Column(db.Integer, nullable=False)
    date = db.Column(db.DateTime, default=datetime.utcnow)



class OrderItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'))
    item_name = db.Column(db.String(100))
    qty = db.Column(db.Integer)
    price = db.Column(db.Integer)
    order = db.relationship('Order', backref='items')

    with app.app_context():
        db.create_all()


# -------------------- HOME --------------------
def utc_to_ist(utc_time):
    return utc_time + timedelta(hours=5, minutes=30)




@app.route('/')
def home():
    return render_template("home.html")

# -------------------- MENU --------------------

@app.route('/menu')
def menu_page():
    items = Menu.query.all()
    return render_template("menu.html", menu=items)

# -------------------- ADD TO CART --------------------
@app.route('/add-food', methods=['GET', 'POST'])
def add_food():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        price = request.form.get('price', '').strip()
        file = request.files.get('image')

        # -------- VALIDATION --------
        if not name or not price or not file:
            return render_template(
                "add_food.html",
                error="All fields are required"
            )

        if not price.isdigit():
            return render_template(
                "add_food.html",
                error="Price must be a number"
            )

        # -------- DUPLICATE CHECK --------
        existing = Menu.query.filter_by(name=name).first()
        if existing:
            return render_template(
                "add_food.html",
                error="Item already exists"
            )

        try:
            # 🔥 Upload image to Cloudinary
            upload_result = cloudinary.uploader.upload(
                file,
                folder="restaurant_menu"
            )

            image_url = upload_result["secure_url"]

        except Exception as e:
            return render_template(
                "add_food.html",
                error="Image upload failed"
            )

        # -------- SAVE DB --------
        new_item = Menu(
            name=name,
            price=int(price),
            image=image_url   # ✅ Cloudinary URL
        )

        db.session.add(new_item)
        db.session.commit()

        return redirect(url_for('menu_page'))

    return render_template("add_food.html")

@app.route('/add/<int:item_id>')
def add_to_cart(item_id):
    cart = session.get('cart', {})
    cart[str(item_id)] = cart.get(str(item_id), 0) + 1
    session['cart'] = cart
    return redirect(url_for('menu_page'))
#update cart item
from flask import session, jsonify

@app.route('/update_cart/<int:item_id>/<action>')
def update_cart(item_id, action):
    cart = session.get('cart', {})

    item_id_str = str(item_id)  # session keys must be string

    if action == 'add':
        cart[item_id_str] = cart.get(item_id_str, 0) + 1

    elif action == 'remove':
        if item_id_str in cart:
            cart[item_id_str] -= 1
            if cart[item_id_str] <= 0:
                del cart[item_id_str]

    session['cart'] = cart
    session.modified = True

    # Return JSON with just the updated quantity of this item
    return jsonify({"qty": cart.get(item_id_str, 0)})



# -------------------- CART --------------------

@app.route('/cart')
def cart():
    cart_data = session.get('cart', {})
    cart_items = []
    total = 0

    for item_id, qty in cart_data.items():
        item = db.session.get(Menu, int(item_id))
        subtotal = item.price * qty
        total += subtotal

        cart_items.append({
            'name': item.name,
            'price': item.price,
            'qty': qty,
            'subtotal': subtotal
        })

    return render_template("cart.html", cart=cart_items, total=total)

# -------------------- BILL (PRINT ONLY) --------------------

@app.route('/bill')
def bill():
    cart_data = session.get('cart', {})
    cart_items = []
    total = 0

    for item_id, qty in cart_data.items():
        item = db.session.get(Menu, int(item_id))
        subtotal = item.price * qty
        total += subtotal

        cart_items.append({
            'name': item.name,
            'qty': qty,
            'subtotal': subtotal
        })

    return render_template("bill.html", items=cart_items, total=total)

# -------------------- CHECKOUT --------------------

@app.route('/checkout')
def checkout():
    cart_data = session.get('cart', {})

    if not cart_data:
        return redirect(url_for('cart'))

    total = 0
    order = Order(total=0)
    db.session.add(order)
    db.session.commit()   # generate order.id

    for item_id, qty in cart_data.items():
        item = db.session.get(Menu, int(item_id))
        subtotal = item.price * qty
        total += subtotal

        order_item = OrderItem(
            order_id=order.id,
            item_name=item.name,
            qty=qty,
            price=item.price
        )
        db.session.add(order_item)

    order.total = total
    db.session.commit()

    # 🔥 Clear cart ONLY from frontend
    session.pop('cart', None)

    return render_template("checkout.html", order_id=order.id, total=total)


#cancel order
@app.route('/cancel')
def cancel_order():
    session.pop('cart', None)   # clear frontend cart only
    return render_template("cancel.html")

# -------------------- START APP --------------------
#order history route
@app.route('/orders')
def order_history():
    orders = Order.query.order_by(Order.date.desc()).all()
    return render_template(
        "orders.html",
        orders=orders,
        utc_to_ist=utc_to_ist
    )


@app.route('/yearly-report')
def yearly_report():
    orders = Order.query.all()

    report = {}

    for order in orders:
        ist_date = utc_to_ist(order.date)
        year = ist_date.year

        if year not in report:
            report[year] = {"orders": 0, "revenue": 0}

        report[year]["orders"] += 1
        report[year]["revenue"] += order.total

    return render_template("yearly_report.html", report=report)

@app.route('/item-yearly-report')
def item_yearly_report():
    report = {}

    items = OrderItem.query.all()

    for item in items:
        ist_date = utc_to_ist(item.order.date)
        year = ist_date.year

        if year not in report:
            report[year] = {}

        name = item.item_name

        if name not in report[year]:
            report[year][name] = 0

        report[year][name] += item.qty * item.price

    return render_template(
        "item_yearly_report.html",
        report=report
    )


from collections import defaultdict
from flask import request

from collections import defaultdict

@app.route('/monthly-report')
def monthly_report():
    orders = Order.query.all()

    report = defaultdict(lambda: {"orders": 0, "revenue": 0})

    for order in orders:
        ist_date = utc_to_ist(order.date)   # convert UTC → IST
        month_key = ist_date.strftime("%B %Y")

        report[month_key]["orders"] += 1
        report[month_key]["revenue"] += order.total

    return render_template("monthly_report.html", report=report)



@app.route('/monthly-chart', methods=['GET', 'POST'])
def monthly_chart():
    selected_month = None
    labels = []
    values = []
    months = set()

    items = OrderItem.query.all()

    # collect available months
    for item in items:
        ist_date = utc_to_ist(item.order.date)
        months.add(ist_date.strftime("%Y-%m"))

    months = sorted(months, reverse=True)

    if request.method == 'POST':
        selected_month = request.form.get('month')

        sales = defaultdict(int)

        for item in items:
            ist_date = utc_to_ist(item.order.date)
            month_key = ist_date.strftime("%Y-%m")

            if month_key == selected_month:
                sales[item.item_name] += item.qty

        labels = list(sales.keys())
        values = list(sales.values())

    return render_template(
        "monthly_chart.html",
        months=months,
        selected_month=selected_month,
        labels=labels,
        values=values
    )



@app.route('/order/<int:order_id>')
def order_details(order_id):
    order = Order.query.get_or_404(order_id)
    items = OrderItem.query.filter_by(order_id=order_id).all()

    return render_template(
        "order_details.html",
        order=order,
        items=items,
        utc_to_ist=utc_to_ist
    )



if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))


