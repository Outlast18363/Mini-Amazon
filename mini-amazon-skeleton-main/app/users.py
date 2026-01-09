from flask import render_template, redirect, url_for, flash, request
from werkzeug.urls import url_parse
from flask_login import login_user, logout_user, current_user, login_required
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField, DecimalField, RadioField
from wtforms.validators import ValidationError, DataRequired, Email, EqualTo, NumberRange
from werkzeug.security import generate_password_hash

from .models.user import User
from .models.purchase import Purchase
from .models.order import Order
from .models.seller import Seller
from .models.seller_review import SellerReview

from flask import Blueprint
bp = Blueprint('users', __name__)


########################################
# Forms
########################################

class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    remember_me = BooleanField('Remember Me')
    submit = SubmitField('Sign In')


class RegistrationForm(FlaskForm):
    full_name = StringField('Full Name', validators=[DataRequired()])
    address = StringField('Address', validators=[DataRequired()])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    password2 = PasswordField(
        'Repeat Password', validators=[DataRequired(),
                                       EqualTo('password')])
    submit = SubmitField('Register')

    def validate_email(self, email):
        if User.email_exists(email.data):
            raise ValidationError('Already a user with this email.')


class AccountUpdateForm(FlaskForm):
    full_name = StringField('Full Name', validators=[DataRequired()])
    address = StringField('Address', validators=[DataRequired()])
    email = StringField('Email', validators=[DataRequired(), Email()])

    password = PasswordField('New Password (leave blank to keep current)')
    password2 = PasswordField(
        'Repeat New Password',
        validators=[EqualTo('password', message='Passwords must match')]
    )

    submit = SubmitField('Update')

    def validate_email(self, email):
        if User.email_taken_by_other(current_user.id, email.data):
            raise ValidationError('Email already in use.')


class BalanceForm(FlaskForm):
    amount = DecimalField('Amount', validators=[DataRequired(), NumberRange(min=0.01)])
    action = RadioField('Action', choices=[('add', 'Top Up'), ('sub', 'Withdraw')], default='add', validators=[DataRequired()])
    submit = SubmitField('Apply')


########################################
# Auth routes
########################################

@bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index.index'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.get_by_auth(form.email.data, form.password.data)
        if user is None:
            flash('Invalid email or password')
            return redirect(url_for('users.login'))
        login_user(user)
        next_page = request.args.get('next')
        if not next_page or url_parse(next_page).netloc != '':
            next_page = url_for('index.index')
        return redirect(next_page)
    return render_template('login.html', title='Sign In', form=form)


@bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index.index'))
    form = RegistrationForm()
    if form.validate_on_submit():
        if User.register(form.email.data,
                         form.password.data,
                         form.full_name.data,
                         form.address.data):
            flash('Congratulations, you are now a registered user!')
            return redirect(url_for('users.login'))
    return render_template('register.html', title='Register', form=form)


@bp.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('index.index'))


########################################
# Account settings (profile update)
########################################

@bp.route('/account', methods=['GET', 'POST'])
@login_required
def account():
    # show + update profile
    form = AccountUpdateForm()
    balance_form = BalanceForm()

    if request.method == 'GET':
        # 预填充表单
        form.full_name.data = current_user.full_name
        form.address.data = current_user.address
        form.email.data = current_user.email
        return render_template('account/account.html', form=form, balance_form=balance_form, user_id=current_user.id)

    # POST
    if form.validate_on_submit():
        new_full_name = form.full_name.data
        new_address = form.address.data
        new_email = form.email.data

        if form.password.data:
            new_password = form.password.data
        else:
            new_password = None

        ok, msg = User.update_profile(
            user_id=current_user.id,
            full_name=new_full_name,
            address=new_address,
            email=new_email,
            new_password_or_none=new_password
        )

        if ok:
            flash('Profile updated.')
        else:
            flash(msg or 'Update failed.')

        # update current_user object
        updated = User.get(current_user.id)
        if updated:
            current_user.full_name = updated.full_name
            current_user.address = updated.address
            current_user.email = updated.email
            current_user.balance = updated.balance

        return redirect(url_for('users.account'))

    # If form validation failed
    if form.errors:
        flash('Invalid form input.')
    
    return render_template('account/account.html', form=form, balance_form=balance_form, user_id=current_user.id)


@bp.route('/account/balance', methods=['POST'])
@login_required
def update_balance():
    form = BalanceForm()
    if form.validate_on_submit():
        amount = form.amount.data
        action = form.action.data
        
        if action == 'sub':
            # Check if enough balance
            if current_user.balance < amount:
                flash('Insufficient funds.')
                return redirect(url_for('users.account'))
            delta = -amount
        else:
            delta = amount
            
        User.add_balance(current_user.id, delta)
        flash('Balance updated!')
        return redirect(url_for('users.account'))
        
    flash('Invalid balance input.')
    return redirect(url_for('users.account'))


########################################
# Purchase history / Orders
########################################

@bp.route('/history', methods=['GET'])
@login_required
def orders():
    user_id = current_user.id

    limit = request.args.get('limit', default=10, type=int)
    offset = request.args.get('offset', default=0, type=int)

    q = request.args.get('q', default=None, type=str)
    seller = request.args.get('seller', default=None, type=str)
    start_date = request.args.get('start', default=None, type=str)
    end_date = request.args.get('end', default=None, type=str)

    seller_id = int(seller) if seller and seller.isdigit() else None

    orders_history = Order.get_history(
        user_id,
        limit=limit,
        offset=offset,
        q=q,
        seller_id=seller_id,
        start_date=start_date,
        end_date=end_date
    )

    distinct_orders = len(orders_history)
    total_cents = sum(o['total_cents'] for o in orders_history)
    total_dollars = total_cents / 100.0

    # 4. 把筛选条件准备给模板显示
    active_filters = {
        "keyword": q or "",
        "seller_id": seller or "",
        "start_date": start_date or "",
        "end_date": end_date or ""
    }

    return render_template(
        'account/orders.html',
        user_id=user_id,
        orders=orders_history,
        limit=limit,
        offset=offset,
        q=q or '',
        seller=seller or '',
        start_date=start_date or '',
        end_date=end_date or '',
        row_count=len(orders_history),
        distinct_orders=distinct_orders,
        total_dollars=total_dollars,
        active_filters=active_filters
    )


@bp.route('/public/<int:user_id>')
def public_profile(user_id):
    from flask import current_app as app
    user = User.get(user_id)
    if not user:
        return render_template('404.html'), 404
    
    is_seller = Seller.is_user_seller(user_id)
    reviews = []
    can_review = False
    existing_review = None
    seller_id = None
    
    if is_seller:
        # SellerReview.for_seller expects seller_user_id which is the ID from the sellers table
        # We need to get the seller ID from the user ID first
        seller = Seller.get_by_user_id(user_id)
        if seller:
            seller_id = seller.id
            reviews = SellerReview.for_seller(seller.id)
            
            # Check if current user can review this seller
            if current_user.is_authenticated and current_user.id != user_id:
                # Check if user has a fulfilled order from this seller
                fulfilled_order = app.db.query_one('''
                    SELECT o.order_id 
                    FROM orders o
                    JOIN order_items oi ON oi.order_id = o.order_id
                    WHERE o.buyer_id = :buyer_id 
                      AND oi.seller_id = :seller_id 
                      AND oi.fulfilled_at IS NOT NULL
                    LIMIT 1
                ''', buyer_id=current_user.id, seller_id=seller.id)
                
                can_review = fulfilled_order is not None
                
                # Check if user already has a review for this seller
                if can_review:
                    existing_review = app.db.query_one('''
                        SELECT review_id, rating, title, body
                        FROM seller_reviews
                        WHERE author_user_id = :author_id AND seller_user_id = :seller_id
                    ''', author_id=current_user.id, seller_id=seller.id)
        
    return render_template('account/public_profile.html', 
                           user=user, 
                           profile_is_seller=is_seller, 
                           reviews=reviews,
                           can_review=can_review,
                           existing_review=existing_review,
                           seller_id=seller_id)


@bp.route('/search')
def search():
    keyword = request.args.get('keyword')
    if not keyword:
        flash("Please enter a search term.")
        return redirect(url_for('index.index'))
    
    results = User.search(keyword)
    if len(results) == 1:
        return redirect(url_for('users.public_profile', user_id=results[0].id))
    
    return render_template('account/search_results.html', results=results, keyword=keyword)
