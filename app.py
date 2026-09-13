from flask import Flask, render_template, request, redirect, url_for, session, abort
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'super_secret_store_key_freshmart_2026'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///store.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# ----------------------------------------------------
# Database Models
# ----------------------------------------------------

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    category = db.Column(db.String(50), nullable=False)
    unit = db.Column(db.String(30), nullable=False)
    price = db.Column(db.Float, nullable=False)
    image_url = db.Column(db.String(255), default='default.jpg')
    is_available = db.Column(db.Boolean, default=True)

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    customer_name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    address = db.Column(db.Text, nullable=False)
    order_items = db.Column(db.Text, nullable=False)
    total_amount = db.Column(db.Float, nullable=False)
    payment_method = db.Column(db.String(50), nullable=False)
    status = db.Column(db.String(30), default='Received')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

with app.app_context():
    db.create_all()
    if not db.session.execute(db.select(Product)).first():
        sample_items = [
            Product(name="Fresh Farm Milk", category="Dairy", unit="1 Litre", price=66.0),
            Product(name="Whole Wheat Bread", category="Bakery", unit="400g Pack", price=45.0),
            Product(name="Organic Basmati Rice", category="Staples", unit="5 kg Bag", price=450.0),
            Product(name="Paneer Butter Masala", category="Meals", unit="Full (Serves 2)", price=240.0),
            Product(name="Fresh Butter Naan", category="Meals", unit="2 pcs", price=70.0),
        ]
        db.session.bulk_save_objects(sample_items)
        db.session.commit()

# ----------------------------------------------------
# Public Storefront & Cart Routes
# ----------------------------------------------------

@app.route('/')
def storefront():
    selected_cat = request.args.get('category')
    if selected_cat:
        products = Product.query.filter_by(category=selected_cat, is_available=True).all()
    else:
        products = Product.query.filter_by(is_available=True).all()
    categories = [row[0] for row in db.session.query(Product.category).distinct()]
    return render_template('index.html', products=products, categories=categories, current_cat=selected_cat)

@app.route('/cart/add/<int:product_id>')
def add_to_cart(product_id):
    cart = session.get('cart', {})
    str_id = str(product_id)
    cart[str_id] = cart.get(str_id, 0) + 1
    session['cart'] = cart
    return redirect(url_for('cart'))

@app.route('/cart/update/<int:product_id>/<action>')
def update_cart_quantity(product_id, action):
    cart = session.get('cart', {})
    str_id = str(product_id)
    if str_id in cart:
        if action == 'increase':
            cart[str_id] += 1
        elif action == 'decrease':
            cart[str_id] -= 1
            if cart[str_id] <= 0:
                del cart[str_id]
    session['cart'] = cart
    return redirect(url_for('cart'))

@app.route('/cart')
def cart():
    cart = session.get('cart', {})
    cart_items = []
    subtotal = 0.0
    for prod_id, qty in cart.items():
        product = db.session.get(Product, int(prod_id))
        if product:
            item_total = product.price * qty
            subtotal += item_total
            cart_items.append({
                'id': product.id,
                'name': product.name,
                'unit': product.unit,
                'price': product.price,
                'qty': qty,
                'total': item_total
            })
    delivery_charge = 40.0 if 0 < subtotal < 500 else 0.0
    grand_total = subtotal + delivery_charge
    return render_template('cart.html', items=cart_items, subtotal=subtotal, delivery=delivery_charge, grand_total=grand_total)

@app.route('/checkout', methods=['POST'])
def checkout():
    cart = session.get('cart', {})
    if not cart:
        return redirect(url_for('storefront'))
    name = request.form.get('customer_name')
    phone = request.form.get('phone')
    address = request.form.get('address')
    payment_mode = request.form.get('payment_method')
    order_items_text = []
    subtotal = 0.0
    for prod_id, qty in cart.items():
        prod = db.session.get(Product, int(prod_id))
        if prod:
            subtotal += prod.price * qty
            order_items_text.append(f"{prod.name} ({prod.unit}) x {qty}")
    delivery = 40.0 if subtotal < 500 else 0.0
    total = subtotal + delivery
    new_order = Order(
        customer_name=name,
        phone=phone,
        address=address,
        order_items=", ".join(order_items_text),
        total_amount=total,
        payment_method=payment_mode,
        status='Received'
    )
    db.session.add(new_order)
    db.session.commit()
    session.pop('cart', None)
    return render_template('order_success.html', order=new_order)

# ----------------------------------------------------
# Owner Authentication & Dashboard Routes
# ----------------------------------------------------

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        # Admin credentials
        if username == 'admin' and password == 'Admin@123':
            session['is_admin'] = True
            return redirect(url_for('admin'))
        else:
            error = 'Invalid username or password'

    return render_template('login.html', error=error)

@app.route('/logout')
def logout():
    session.pop('is_admin', None)
    return redirect(url_for('storefront'))

@app.route('/admin')
def admin():
    if not session.get('is_admin'):
        return redirect(url_for('login'))
    orders = Order.query.order_by(Order.id.desc()).all()
    products = Product.query.all()
    return render_template('admin.html', orders=orders, products=products)

@app.route('/admin/add-product', methods=['POST'])
def add_product():
    if not session.get('is_admin'):
        return redirect(url_for('login'))
    name = request.form.get('name')
    category = request.form.get('category')
    unit = request.form.get('unit')
    price = float(request.form.get('price'))
    new_item = Product(name=name, category=category, unit=unit, price=price)
    db.session.add(new_item)
    db.session.commit()
    return redirect(url_for('admin'))

@app.route('/admin/order-status/<int:order_id>/<status>')
def update_order_status(order_id, status):
    if not session.get('is_admin'):
        return redirect(url_for('login'))
    order = db.session.get(Order, order_id)
    if not order:
        abort(404)
    order.status = status
    db.session.commit()
    return redirect(url_for('admin'))

@app.route('/admin/delete_order/<int:order_id>', methods=['POST'])
def delete_order(order_id):
    if not session.get('is_admin'):
        return redirect(url_for('login'))
    order = db.session.get(Order, order_id)
    if not order:
        abort(404)
    db.session.delete(order)
    db.session.commit()
    return redirect(url_for('admin'))

if __name__ == '__main__':
    app.run(debug=True, port=5000)