from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from datetime import datetime
from flask_login import login_required, current_user
from flask import current_app as app
from app.models.cart_item import CartItem
from sqlalchemy import text
from .csv_sync import (
    export_cart_items,
    export_users,
    export_inventory,
    export_orders,
    export_order_items,
)


bp = Blueprint('cart', __name__)


@bp.route('/cart')
@login_required
def view():
    # TODO (Johnson): fetch cart and saved-for-later items for current user

    cart_items = CartItem.for_user(current_user.id, in_cart=True)
    saved_items = CartItem.for_user(current_user.id, in_cart=False)
    cart_total_cents = sum((ci.unit_price_cents or 0) * ci.quantity for ci in cart_items)

    # fetch fresh balance from DB to avoid stale session data
    # app.db.execute returns a list of rows/tuples
    rows = app.db.execute('SELECT balance FROM users WHERE id = :uid', uid=current_user.id)
    user_balance_cents = int(rows[0][0] * 100) if rows and rows[0][0] is not None else 0
    
    # Coupon Logic
    coupon_code = session.get('coupon_code')
    discount_amount_cents = 0
    
    if coupon_code:
        # Check if coupon is valid
        # Removing text() wrapper, using kwargs, handling list return
        coupon_rows = app.db.execute('''
            SELECT discount_percent, product_id, category_id 
            FROM coupons 
            WHERE code = :code AND expiration_time > NOW()
        ''', code=coupon_code) 
        
        # NOTE: create.sql uses 'discount_percent', NOT 'percent'. Correcting this query.
        coupon_rows = app.db.execute('''
            SELECT discount_percent, product_id, category_id
            FROM coupons
            WHERE code = :code AND expiration_time > NOW()
        ''', code=coupon_code)
        
        if coupon_rows:
            discount_percent, scope_pid, scope_catid = coupon_rows[0]
            
            # Fetch detailed cart info joined with products to get category
            # app.db.execute returns list of rows/tuples
            cart_details = app.db.execute('''
                SELECT c.product_id, c.quantity, p.category_id, i.price_cents
                FROM cart_items c
                JOIN products p ON c.product_id = p.id
                JOIN inventory i ON c.seller_id = i.seller_id AND c.product_id = i.product_id
                WHERE c.user_id = :uid AND c.is_in_cart = TRUE
            ''', uid=current_user.id)
            
            for pid, qty, cat_id, price_cents in cart_details:
                # Check scope
                applies = False
                if scope_pid is None and scope_catid is None:
                    applies = True
                elif scope_pid is not None and scope_pid == pid:
                    applies = True
                elif scope_catid is not None and scope_catid == cat_id:
                    applies = True
                
                if applies:
                    # Discount is percentage of (price * qty)
                    # Integer arithmetic: (price * qty * percent) // 100
                    item_total = price_cents * qty
                    discount = (item_total * discount_percent) // 100
                    discount_amount_cents += discount
        else:
            # Expired or invalid, clear it
            session.pop('coupon_code', None)
            flash('Coupon expired or invalid.', 'warning')

    cart_total_final_cents = cart_total_cents - discount_amount_cents
    if cart_total_final_cents < 0: cart_total_final_cents = 0

    return render_template('cart/view.html', 
    cart_items=cart_items, 
    saved_items=saved_items,
    cart_total_cents=cart_total_final_cents, # Display discounted total
    original_cart_total_cents=cart_total_cents, # For showing strike-through if wanted
    discount_amount_cents=discount_amount_cents,
    coupon_code=coupon_code,
    user_balance_cents=user_balance_cents)


@bp.route('/cart/add', methods=['POST'])
@login_required
def add_to_cart():
    product_id = request.form.get('product_id', type=int)
    seller_id = request.form.get('seller_id', type=int)
    quantity = request.form.get('quantity', type=int)

    if not product_id or not seller_id or not quantity:
        flash("Invalid request", "danger")
        return redirect(url_for('products.browse'))

    CartItem.add_to_cart(user_id=current_user.id, product_id=product_id,
                         seller_id=seller_id, quantity=quantity)

    flash(f"Added {quantity} item(s) to your cart.", "success")
    return redirect(url_for('products.detail', product_id=product_id))


@bp.route('/cart/update', methods=['POST'])
@login_required
def update_quantity():
    try:
        product_id = int(request.form.get('product_id', '0'))
        seller_id = int(request.form.get('seller_id', '0'))
        quantity = int(request.form.get('quantity', '1'))
    except ValueError:
        flash('Invalid quantity', 'danger')
        return redirect(url_for('cart.view'))
    if quantity < 1:
        flash('Quantity must be at least 1', 'danger')
        return redirect(url_for('cart.view'))
    with app.db.engine.begin() as conn:
        res = conn.execute(text('''
        UPDATE cart_items
        SET quantity = :q
        WHERE user_id = :uid AND product_id = :pid AND seller_id = :sid AND is_in_cart = TRUE
        '''), dict(q=quantity, uid=current_user.id, pid=product_id, sid=seller_id))
    export_cart_items()
    flash('Quantity updated', 'success')
    return redirect(url_for('cart.view'))


@bp.route('/cart/remove', methods=['POST'])
@login_required
def remove_item():
    try: # request.form is the form sent by front end
        product_id = int(request.form.get('product_id', '0'))
        seller_id = int(request.form.get('seller_id', '0'))
        is_in_cart_raw = request.form.get('is_in_cart', 'false')
        is_in_cart = str(is_in_cart_raw).lower() in ('true','1','t','yes','on')
    except ValueError:
        flash('Invalid item', 'danger')
        return redirect(url_for('cart.view'))
    with app.db.engine.begin() as conn:
        conn.execute(text('''
DELETE FROM cart_items
WHERE user_id = :uid AND product_id = :pid AND seller_id = :sid AND is_in_cart = :is_in_cart
'''), dict(uid=current_user.id, pid=product_id, sid=seller_id, is_in_cart=is_in_cart))
    export_cart_items()
    flash('Item removed from cart', 'success')
    return redirect(url_for('cart.view'))

@bp.route('/cart/move_to_save', methods=['POST'])
@login_required
def move_to_save():
    try:
        product_id = int(request.form.get('product_id', '0'))
        seller_id = int(request.form.get('seller_id', '0'))
        qty = int(request.form.get('quantity', '0')) # defualt: 0
    except ValueError:
        flash('Invalid item to move to cart', 'danger')
        return redirect(url_for('cart.view'))
    
    with app.db.engine.begin() as conn: # execute as a transaction
        # update the quanity of the corresponding item in save list
        sql_insert = """
        INSERT INTO cart_items (user_id, product_id, seller_id, quantity, is_in_cart)
        VALUES (:uid, :pid, :sid, :qty, FALSE)
        ON CONFLICT (user_id, product_id, seller_id, is_in_cart)
        DO UPDATE SET quantity = cart_items.quantity + EXCLUDED.quantity
        """

        sql_update = """
        UPDATE cart_items
        SET quantity = quantity - :qty
        WHERE user_id = :uid
        AND product_id = :pid
        AND seller_id = :sid
        AND is_in_cart = TRUE
        AND quantity > :qty
        """

        sql_delete = """
        DELETE FROM cart_items
        WHERE user_id = :uid
        AND product_id = :pid
        AND seller_id = :sid
        AND is_in_cart = TRUE
        AND quantity <= :qty
        """
        
        conn.execute(text(sql_insert), dict(uid=current_user.id, pid=product_id, sid=seller_id, qty=qty))
        
        # 3. reudce quantity of the save for later list entry
        conn.execute(text(sql_update), dict(uid=current_user.id, pid=product_id, sid=seller_id, qty=qty))
        
        # 4. Delete the source entry if quantity <= 0
        conn.execute(text(sql_delete), dict(uid=current_user.id, pid=product_id, sid=seller_id, qty=qty))

    export_cart_items()
    flash('Item moved to save list', 'success')
    return redirect(url_for('cart.view'))


@bp.route('/cart/move_to_cart', methods=['POST'])
@login_required
def move_to_cart():
    try:
        product_id = int(request.form.get('product_id', '0'))
        seller_id = int(request.form.get('seller_id', '0'))
        qty = int(request.form.get('quantity', '0')) # defualt: 0
    except ValueError:
        flash('Invalid item to move to cart', 'danger')
        return redirect(url_for('cart.view'))
    
    with app.db.engine.begin() as conn: # toggle the is_in_cart attri to False

        sql_insert = """
        INSERT INTO cart_items (user_id, product_id, seller_id, quantity, is_in_cart)
        VALUES (:uid, :pid, :sid, :qty, TRUE)
        ON CONFLICT (user_id, product_id, seller_id, is_in_cart)
        DO UPDATE SET quantity = cart_items.quantity + EXCLUDED.quantity
        """

        sql_update = """
        UPDATE cart_items
        SET quantity = quantity - :qty
        WHERE user_id = :uid
        AND product_id = :pid
        AND seller_id = :sid
        AND is_in_cart = FALSE
        AND quantity > :qty
        """

        sql_delete = """
        DELETE FROM cart_items
        WHERE user_id = :uid
        AND product_id = :pid
        AND seller_id = :sid
        AND is_in_cart = FALSE
        AND quantity <= :qty
        """
        
        # 2. update the quanity of the corresponding item in the cart
        conn.execute(text(sql_insert), dict(uid=current_user.id, pid=product_id, sid=seller_id, qty=qty))
        
        # 3. reduce quantity of the save for later list entry (only if quantity > qty)
        conn.execute(text(sql_update), dict(uid=current_user.id, pid=product_id, sid=seller_id, qty=qty))
        
        # 4. Delete the source entry if quantity <= qty (would become 0 or negative)
        conn.execute(text(sql_delete), dict(uid=current_user.id, pid=product_id, sid=seller_id, qty=qty))

    export_cart_items()
    flash('Item moved to cart', 'success')
    return redirect(url_for('cart.view'))


@bp.route('/cart/apply_coupon', methods=['POST'])
@login_required
def apply_coupon():
    code = request.form.get('coupon_code')
    if not code:
        flash('Please enter a coupon code.', 'warning')
        return redirect(url_for('cart.view'))
    
    # Check if validity
    # Remove text(), use kwargs, handle list return logic
    coupon_rows = app.db.execute('''
        SELECT id FROM coupons 
        WHERE code = :code AND expiration_time > NOW()
    ''', code=code)
    
    if coupon_rows:
        session['coupon_code'] = code
        flash(f'Coupon "{code}" applied!', 'success')
    else:
        session.pop('coupon_code', None)
        flash('Invalid or expired coupon code.', 'danger')
        
    return redirect(url_for('cart.view'))


@bp.route('/cart/checkout', methods=['POST'])
@login_required
def checkout():
    # Transactional checkout
    try:
        with app.db.engine.begin() as conn:
            # Lock buyer row and get balance/address
            # conn.execute IS standard SQLAlchemy, so text() and dict() are CORRECT here.
            buyer_row = conn.execute(text('''
SELECT balance, address FROM users WHERE id = :uid FOR UPDATE
'''), dict(uid=current_user.id)).first()
            if not buyer_row:
                flash('User not found', 'danger')
                return redirect(url_for('cart.view'))
            buyer_balance_cents = int(buyer_row[0] * 100) if buyer_row[0] is not None else 0
            shipping_address = buyer_row[1]

            # Load cart items with inventory, lock inventory rows
            rows = conn.execute(text('''
SELECT c.product_id, c.seller_id, c.quantity,
       i.price_cents, i.quantity_on_hand,
       s.user_id AS seller_user_id,
       p.category_id
FROM cart_items c
JOIN inventory i ON i.seller_id = c.seller_id AND i.product_id = c.product_id
JOIN sellers s ON s.id = c.seller_id
JOIN products p ON c.product_id = p.id
WHERE c.user_id = :uid AND c.is_in_cart = TRUE
FOR UPDATE OF i
'''), dict(uid=current_user.id)).fetchall()
            if not rows:
                flash('Cart is empty', 'warning')
                return redirect(url_for('cart.view'))

            # Coupon Validation
            coupon_code = session.get('coupon_code')
            discount_percent = 0
            scope_pid = None
            scope_catid = None
            
            if coupon_code:
                # conn.execute uses standard SQLAlchemy
                coupon_row = conn.execute(text('''
                    SELECT discount_percent, product_id, category_id
                    FROM coupons
                    WHERE code = :code AND expiration_time > NOW()
                '''), dict(code=coupon_code)).first()
                if coupon_row:
                    discount_percent, scope_pid, scope_catid = coupon_row
                else:
                    # Invalid/Expired during checkout process - ignore
                    pass

            # Validate inventory and compute totals
            total_cents = 0
            insufficient = []
            per_seller_user_total = {}
            final_order_items = [] # Store tuple for insertion later: (pid, sid, qty, final_price, discount, seller_uid)

            for pid, sid, qty, price_cents, qty_on_hand, seller_user_id, cat_id in rows:
                if qty > qty_on_hand:
                    insufficient.append((pid, sid))
                
                # Calculate Line Discount
                line_original_total = price_cents * qty
                line_discount = 0
                
                applies = False
                if discount_percent > 0:
                    if scope_pid is None and scope_catid is None:
                        applies = True
                    elif scope_pid == pid:
                        applies = True
                    elif scope_catid == cat_id:
                        applies = True
                
                if applies:
                    line_discount = (line_original_total * discount_percent) // 100
                
                line_final_total = line_original_total - line_discount
                
                total_cents += line_final_total
                per_seller_user_total[seller_user_id] = per_seller_user_total.get(seller_user_id, 0) + line_final_total
                
                final_order_items.append({
                    'pid': pid, 'sid': sid, 'qty': qty, 
                    'price': price_cents, # This is UNIT price (original)
                    'discount_cents': line_discount, # Total discount for this line? 
                    'line_discount_cents': line_discount 
                })

            if insufficient:
                flash('Insufficient inventory for some items', 'danger')
                return redirect(url_for('cart.view'))
            if buyer_balance_cents < total_cents:
                flash('Insufficient balance', 'danger')
                return redirect(url_for('cart.view'))

            # Create order
            order_row = conn.execute(text('''
INSERT INTO orders(buyer_id, shipping_address, status)
VALUES(:uid, :addr, 'PENDING')
RETURNING order_id
'''), dict(uid=current_user.id, addr=shipping_address)).first()
            order_id = order_row[0]

            # Insert order items and update inventory
            for item in final_order_items:
                conn.execute(text('''
INSERT INTO order_items(order_id, product_id, seller_id, quantity, unit_price_final_cents, discount_cents, fulfilled_at)
VALUES(:oid, :pid, :sid, :qty, :price, :disc, NULL)
'''), dict(oid=order_id, pid=item['pid'], sid=item['sid'], qty=item['qty'], 
           price=item['price'], disc=item['line_discount_cents']))
                
                conn.execute(text('''
UPDATE inventory
SET quantity_on_hand = quantity_on_hand - :qty, updated_at = NOW()
WHERE seller_id = :sid AND product_id = :pid
'''), dict(qty=item['qty'], sid=item['sid'], pid=item['pid']))

            # Clear applied coupon from session
            if coupon_code:
                session.pop('coupon_code', None)


            # Update balances
            conn.execute(text('''
UPDATE users SET balance = balance - (:total_cents / 100.0) WHERE id = :uid
'''), dict(total_cents=total_cents, uid=current_user.id))
            
            # Record transaction for buyer
            conn.execute(text('''
INSERT INTO transactions(user_id, amount, order_id)
VALUES(:uid, -(:total_cents / 100.0), :oid)
'''), dict(uid=current_user.id, total_cents=total_cents, oid=order_id))

            for seller_user_id, amount_cents in per_seller_user_total.items():
                conn.execute(text('''
UPDATE users SET balance = balance + (:amount_cents / 100.0) WHERE id = :sid
'''), dict(amount_cents=amount_cents, sid=seller_user_id))
                # Record transaction for seller
                conn.execute(text('''
INSERT INTO transactions(user_id, amount, order_id)
VALUES(:sid, (:amount_cents / 100.0), :oid)
'''), dict(sid=seller_user_id, amount_cents=amount_cents, oid=order_id))

            # Clear cart
            conn.execute(text('''
DELETE FROM cart_items WHERE user_id = :uid AND is_in_cart = TRUE
'''), dict(uid=current_user.id))

        # CSV sync after commit
        export_users()
        export_inventory()
        export_orders()
        export_order_items()
        export_cart_items()
        flash('Order placed successfully', 'success')
    except Exception as e:
        flash(f'Checkout failed: {str(e)}', 'danger')
    return redirect(url_for('cart.view'))

