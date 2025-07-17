from flask import Flask, render_template, request, redirect, url_for # type: ignore
import mysql.connector # type: ignore

app = Flask(__name__)

# DB Connection function
def get_db_connection():
    return mysql.connector.connect(
        host='localhost',
        user='your_mysql_user',
        password='your_mysql_password',
        database='product_inventory'
    )

### PRODUCT MANAGEMENT ###

@app.route('/')
@app.route('/products')
def products():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM products")
    products = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('products.html', products=products)

@app.route('/product/add', methods=['GET', 'POST'])
def add_product():
    if request.method == 'POST':
        name = request.form['name']
        description = request.form['description']
        price = float(request.form['price'])
        quantity = int(request.form['quantity'])

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO products (name, description, price, quantity) VALUES (%s, %s, %s, %s)",
                       (name, description, price, quantity))
        conn.commit()
        cursor.close()
        conn.close()
        return redirect(url_for('products'))
    return render_template('add_product.html')

@app.route('/product/edit/<int:id>', methods=['GET', 'POST'])
def edit_product(id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    if request.method == 'POST':
        name = request.form['name']
        description = request.form['description']
        price = float(request.form['price'])
        quantity = int(request.form['quantity'])

        cursor.execute("UPDATE products SET name=%s, description=%s, price=%s, quantity=%s WHERE id=%s",
                       (name, description, price, quantity, id))
        conn.commit()
        cursor.close()
        conn.close()
        return redirect(url_for('products'))

    cursor.execute("SELECT * FROM products WHERE id=%s", (id,))
    product = cursor.fetchone()
    cursor.close()
    conn.close()
    return render_template('edit_product.html', product=product)

@app.route('/product/delete/<int:id>', methods=['POST'])
def delete_product(id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM products WHERE id=%s", (id,))
    conn.commit()
    cursor.close()
    conn.close()
    return redirect(url_for('products'))

### INVENTORY MANAGEMENT ###

@app.route('/inventory')
def inventory():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT ib.batch_id, p.name, ib.batch_code, ib.quantity 
        FROM inventory_batches ib
        JOIN products p ON ib.product_id = p.id
    """)
    batches = cursor.fetchall()
    cursor.execute("SELECT id, name FROM products")
    products = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('inventory.html', batches=batches, products=products)

@app.route('/inventory/add', methods=['POST'])
def add_inventory_batch():
    product_id = int(request.form['product_id'])
    batch_code = request.form['batch_code']
    quantity = int(request.form['quantity'])

    conn = get_db_connection()
    cursor = conn.cursor()

    # Insert batch record
    cursor.execute(
        "INSERT INTO inventory_batches (product_id, batch_code, quantity) VALUES (%s, %s, %s)",
        (product_id, batch_code, quantity)
    )

    # Update product total quantity
    cursor.execute("UPDATE products SET quantity = quantity + %s WHERE id = %s", (quantity, product_id))

    conn.commit()
    cursor.close()
    conn.close()
    return redirect(url_for('inventory'))

@app.route('/inventory/remove', methods=['POST'])
def remove_inventory_batch():
    batch_id = int(request.form['batch_id'])
    quantity_to_remove = int(request.form['quantity'])

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Get current quantity for batch
    cursor.execute("SELECT product_id, quantity FROM inventory_batches WHERE batch_id=%s", (batch_id,))
    batch = cursor.fetchone()
    if batch and batch['quantity'] >= quantity_to_remove:
        new_batch_quantity = batch['quantity'] - quantity_to_remove
        cursor.execute("UPDATE inventory_batches SET quantity=%s WHERE batch_id=%s", (new_batch_quantity, batch_id))
        cursor.execute("UPDATE products SET quantity = quantity - %s WHERE id=%s", (quantity_to_remove, batch['product_id']))
        conn.commit()

    cursor.close()
    conn.close()
    return redirect(url_for('inventory'))

### BILLING SYSTEM ###

@app.route('/billing', methods=['GET', 'POST'])
def billing():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    if request.method == 'POST':
        customer_name = request.form['customer_name']
        product_ids = request.form.getlist('product_id')
        quantities = request.form.getlist('quantity')

        total = 0
        items = []

        # Calculate total cost and prepare items
        for pid, qty in zip(product_ids, quantities):
            qty = int(qty)
            if qty <= 0:
                continue
            cursor.execute("SELECT price, quantity FROM products WHERE id=%s", (pid,))
            product = cursor.fetchone()
            if product and product['quantity'] >= qty:
                price = float(product['price'])
                total += price * qty
                items.append((int(pid), qty, price))

        tax = total * 0.1  # 10% tax
        discount = 0
        if total > 500:
            discount = total * 0.05  # 5% discount if total > 500
        grand_total = total + tax - discount

        # Insert bill
        cursor.execute("INSERT INTO bills (customer_name, total) VALUES (%s, %s)", (customer_name, grand_total))
        bill_id = cursor.lastrowid

        # Insert bill items and update product quantities
        for pid, qty, price in items:
            cursor.execute("INSERT INTO bill_items (bill_id, product_id, quantity, price) VALUES (%s, %s, %s, %s)",
                           (bill_id, pid, qty, price))
            # Reduce quantity from products and inventory batches (simplified: reduce product quantity)
            cursor.execute("UPDATE products SET quantity = quantity - %s WHERE id=%s", (qty, pid))

        conn.commit()
        cursor.close()
        conn.close()

        return render_template('bill_generated.html', customer_name=customer_name, items=items,
                               total=total, tax=tax, discount=discount, grand_total=grand_total)

    # GET request: Show products to add to bill
    cursor.execute("SELECT * FROM products WHERE quantity > 0")
    products = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('billing.html', products=products)


if __name__ == '__main__':
    app.run(debug=True)
