from flask import Flask, render_template, request, redirect, url_for, flash, session
from models import db, User, ParkingLot, ParkingSpot, Reservation
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from zoneinfo import ZoneInfo




app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = 'your-very-secret-key' 

db.init_app(app)


# Create tables and admin user if not exists
with app.app_context():
    db.create_all()
    if not User.query.filter_by(email="admin@example.com").first():
        admin = User(
            full_name="Admin User",
            email="admin@example.com",
            phone="0000000000",
            password=generate_password_hash("AdminPass123"),
            role="admin"
        )
        db.session.add(admin)
        db.session.commit()

@app.route('/')
def home():
    return render_template('home.html')

# -------------------- Authentication --------------------

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email'].strip()
        password = request.form['password'].strip()
        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password, password):
            session['user_id'] = user.id
            session['email'] = user.email
            if user.role == 'admin':
                flash('Welcome Admin!', 'success')
                return redirect(url_for('admin_dashboard'))
            else:
                flash(f'Welcome {user.full_name}!', 'success')
                return redirect(url_for('user_dashboard'))
        else:
            flash('Invalid credentials.', 'error')
            return redirect(url_for('login'))
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        full_name = request.form['full_name'].strip()
        email = request.form['email'].strip()
        phone = request.form.get('phone', '').strip()
        password = request.form['password'].strip()
        role = request.form.get('role', 'user').strip()
        vehicle_number = request.form.get("vehicle_number")
        if not full_name or not email or not password:
            flash('Full name, email and password are required.', 'error')
            return redirect(url_for('register'))
        if User.query.filter_by(email=email).first():
            flash('User already exists with this email.', 'error')
            return redirect(url_for('register'))
        hashed_password = generate_password_hash(password)
        new_user = User(full_name=full_name, email=email, phone=phone, password=hashed_password, role=role, vehicle_number=vehicle_number)
        db.session.add(new_user)
        db.session.commit()
        flash('Registration successful! Please log in.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.clear()
    flash("Logged out successfully!", "info")
    return redirect(url_for('login'))

# -------------------- Admin Dashboard & Management --------------------

@app.route('/admin_dashboard')
def admin_dashboard():
    if 'email' not in session:
        return redirect(url_for('login'))
    admin = User.query.filter_by(email=session['email']).first()
    lots = ParkingLot.query.all()
    for lot in lots:
        spots = ParkingSpot.query.filter_by(lot_id=lot.id).all()
        lot.spots = spots
        lot.occupied_count = sum(1 for s in spots if s.status == 'O')
        lot.available_count = sum(1 for s in spots if s.status == 'A')
        lot.total_spots = len(spots)
    return render_template('admin_dashboard.html', lots=lots, admin=admin)

@app.route('/admin/manage-parking', methods=['GET', 'POST'])
def manage_parking():
    if request.method == 'POST':
        prime_location = request.form['prime_location']
        address = request.form['address']
        price = float(request.form['price'])
        pin_code = request.form['pin_code']
        total_spots = int(request.form['total_spots'])
        new_lot = ParkingLot(
            prime_location=prime_location,
            address=address,
            price=price,
            pin_code=pin_code,
            total_spots=total_spots
        )
        db.session.add(new_lot)
        db.session.flush()
        for spot_number in range(1, total_spots + 1):
            new_spot = ParkingSpot(
                lot_id=new_lot.id,
                status='A',
                spot_number=spot_number
            )
            db.session.add(new_spot)
        db.session.commit()
        flash(f"Parking lot created with {total_spots} spots!", "admin")

        return redirect(url_for('manage_parking'))
    all_lots = ParkingLot.query.all()
    return render_template('create_lot.html', lots=all_lots)

@app.route('/admin/edit-lot/<int:lot_id>', methods=['GET', 'POST'])
def edit_lot(lot_id):
    lot = ParkingLot.query.get_or_404(lot_id)
    spots = ParkingSpot.query.filter_by(lot_id=lot.id).all()
    current_spot_count = len(spots)
    if request.method == 'POST':
        lot.prime_location = request.form['prime_location']
        lot.address = request.form['address']
        lot.price = float(request.form['price'])
        lot.pin_code = request.form['pin_code']
        new_total_spots = int(request.form['total_spots'])
        if new_total_spots > current_spot_count:
            for spot_number in range(current_spot_count + 1, new_total_spots + 1):
                new_spot = ParkingSpot(
                    lot_id=lot.id,
                    spot_number=spot_number,
                    status='A'
                )
                db.session.add(new_spot)
        elif new_total_spots < current_spot_count:
            removable_spots = ParkingSpot.query.filter(
                ParkingSpot.lot_id == lot.id,
                ParkingSpot.spot_number > new_total_spots,
                ParkingSpot.status == 'A'
            ).order_by(ParkingSpot.spot_number.desc()).all()
            for spot in removable_spots:
                db.session.delete(spot)
        lot.total_spots = new_total_spots
        db.session.commit()
        flash("Parking lot updated successfully!", "success")
        return redirect(url_for('manage_parking'))
    return render_template('edit_lot.html', lot=lot)

@app.route('/admin/delete-lot/<int:lot_id>', methods=['POST'])
def delete_lot(lot_id):
    lot = ParkingLot.query.get_or_404(lot_id)
   
    active_reservations = Reservation.query.filter_by(lot_id=lot.id, leaving_timestamp=None).count()
    if active_reservations > 0:
        flash("Cannot delete lot: Some spots have active reservations.", "error")
        return redirect(url_for('manage_parking'))
    
    ParkingSpot.query.filter_by(lot_id=lot.id).delete()
    db.session.delete(lot)
    db.session.commit()
    flash("Parking lot deleted successfully!", "info")
    return redirect(url_for('manage_parking'))


@app.route('/admin/view-reservations')
def view_all_reservations():
    reservations = Reservation.query.all()
    total_revenue = sum(res.total_cost or 0 for res in reservations if res.total_cost is not None)
    return render_template("admin_reservations.html", reservations=reservations, total_revenue=total_revenue)


@app.route('/admin/view-users')
def view_users():
    users = User.query.filter(User.role != 'admin').all()
    return render_template('admin_users.html', users=users)

@app.route('/admin/summary')
def admin_summary():
    lots = ParkingLot.query.all()
    lot_names = []
    lot_revenues = []
    total_revenue = 0

    total_spots = 0
    reserved_spots = 0

    for lot in lots:
        spots = ParkingSpot.query.filter_by(lot_id=lot.id).all()
        total_spots += len(spots)
        reserved_spots += sum(1 for s in spots if s.status == 'O')

        # Revenue part
        reservations = Reservation.query.filter_by(lot_id=lot.id).all()
        revenue = sum(r.total_cost or 0 for r in reservations)
        lot_names.append(lot.prime_location)
        lot_revenues.append(revenue)
        total_revenue += revenue

    available_spots = total_spots - reserved_spots

    return render_template(
        'admin_summary.html',
        total_spots=total_spots,
        reserved_spots=reserved_spots,
        available_spots=available_spots,
        lot_names=lot_names,
        lot_revenues=lot_revenues,
        total_revenue=total_revenue
    )

@app.route('/admin/edit-profile', methods=['GET', 'POST'])
def admin_edit_profile():
    if 'email' not in session:
        flash("Please log in to edit profile.", "error")
        return redirect(url_for('login'))
    user = User.query.filter_by(email=session['email']).first()
    if not user:
        flash("User not found.", "error")
        return redirect(url_for('login'))
    if request.method == 'POST':
        user.full_name = request.form['full_name']
        new_email = request.form['email']
        if new_email != user.email:
            if User.query.filter(User.email == new_email, User.id != user.id).first():
                flash("Email already in use by another account.", "error")
                return redirect(url_for('admin_edit_profile'))
            user.email = new_email
            session['email'] = new_email
        if request.form.get('password'):
            user.password_hash = generate_password_hash(request.form['password'])
        db.session.commit()
        flash("Profile updated successfully!", "success")
        return redirect(url_for('admin_dashboard'))
    return render_template('admin_edit_profile.html', user=user)

# -------------------- User Dashboard & Actions --------------------

@app.route('/user/dashboard')
def user_dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    reservations = Reservation.query.filter_by(user_id=user.id).order_by(Reservation.parking_timestamp.desc()).all()
    active_reservations = [r for r in reservations if not r.leaving_timestamp]
    total_spent = sum(r.total_cost for r in reservations if r.total_cost)
    return render_template('user_dashboard.html',
                           user=user,
                           reservations=reservations[:6],
                           active_reservations=active_reservations,
                           total_spent=total_spent)

@app.route('/user/edit-profile', methods=['GET', 'POST'])
def user_edit_profile():
    if 'email' not in session:
        flash("Please log in to edit your profile.", "error")
        return redirect(url_for('login'))
    user = User.query.filter_by(email=session['email']).first()
    if not user:
        flash("User not found.", "error")
        return redirect(url_for('login'))
    if request.method == 'POST':
        user.full_name = request.form['full_name']
        user.vehicle_number = request.form['vehicle_number']
        new_email = request.form['email']
        if new_email != user.email:
            if User.query.filter(User.email == new_email, User.id != user.id).first():
                flash("Email already in use by another account.", "error")
                return redirect(url_for('user_edit_profile'))
            user.email = new_email
            session['email'] = new_email
        if request.form.get('password'):
            user.password_hash = generate_password_hash(request.form['password'])
        db.session.commit()
        flash("Profile updated successfully!", "success")
        return redirect(url_for('user_dashboard'))
    return render_template('user_edit_profile.html', user=user)

@app.route('/user/view-parking', methods=['GET', 'POST'])
def view_parking():
    lots = ParkingLot.query.all()
    for lot in lots:
        spots = ParkingSpot.query.filter_by(lot_id=lot.id).all()
        lot.available_count = sum(1 for spot in spots if spot.status == 'A')
        lot.spots = spots
    return render_template('view_parking.html', lots=lots)

@app.route('/user/my-reservations')
def my_reservations():
    if 'email' not in session:
        flash("Please log in to view reservations.", "error")
        return redirect(url_for('login'))
    user = User.query.filter_by(email=session['email']).first()
    if not user:
        flash("User not found.", "error")
        return redirect(url_for('login'))
    reservations = Reservation.query.filter(
        Reservation.user_id == user.id,
        Reservation.leaving_timestamp == None
    ).order_by(Reservation.parking_timestamp.desc()).all()
    return render_template('my_reservations.html', reservations=reservations)

@app.route('/user/search-by-pincode', methods=['GET'])
def search_by_pincode():
    pincode = request.args.get('pincode')
    if not pincode:
        return redirect(url_for('view_parking'))
    matching_lots = ParkingLot.query.filter(
        ParkingLot.pin_code.like(f'%{pincode}%')
    ).all()
    for lot in matching_lots:
        spots = ParkingSpot.query.filter_by(lot_id=lot.id).all()
        lot.spots = spots
        lot.available_count = sum(1 for s in spots if s.status == 'A')
        lot.occupied_count = sum(1 for s in spots if s.status == 'O')
    return render_template('search_pincode.html',
                          lots=matching_lots,
                          pincode=pincode)

@app.route('/user/reserve/<int:lot_id>', methods=['POST'])
def reserve_spot(lot_id):
    if 'email' not in session:
        flash("Please log in to reserve a spot.", "error")
        return redirect(url_for('login'))
    user = User.query.filter_by(email=session['email']).first()
    if not user:
        flash("User not found.", "error")
        return redirect(url_for('login'))
    active_reservation = Reservation.query.filter_by(
        user_id=user.id,
        leaving_timestamp=None
    ).first()
    if active_reservation:
        flash("You already have an active reservation. Release your current spot before booking a new one.", "error")
        return redirect(url_for('view_parking'))
    selected_lot = ParkingLot.query.get_or_404(lot_id)
    selected_spot = ParkingSpot.query.filter_by(
        lot_id=selected_lot.id,
        status='A'
    ).first()
    if not selected_spot:
        flash("No available spots in this lot!", "error")
        return redirect(url_for('view_parking'))
    reservation = Reservation(
        user_id=user.id,
        spot_id=selected_spot.id,
        lot_id=selected_lot.id,
        parking_timestamp=datetime.now(ZoneInfo("Asia/Kolkata")),
        cost_per_hour=selected_lot.price,
    )
    selected_spot.status = 'O'
    selected_spot.current_reservation = reservation
    db.session.add(reservation)
    db.session.commit()
    flash(f"Spot {selected_spot.spot_number} reserved successfully at {selected_lot.prime_location}!", "success")
    return redirect(url_for('my_reservations'))

@app.route('/vacate-spot/<int:reservation_id>', methods=['POST'])
def vacate_spot(reservation_id):
    reservation = Reservation.query.get_or_404(reservation_id)
    reservation.leaving_timestamp = datetime.now(ZoneInfo("Asia/Kolkata"))
    parking_time = reservation.parking_timestamp.replace(tzinfo=None)
    leaving_time = reservation.leaving_timestamp.replace(tzinfo=None)
    duration = (leaving_time - parking_time).total_seconds() / 3600
    total_cost = round(duration * reservation.cost_per_hour, 2)
    reservation.total_cost = total_cost
    spot = reservation.spot
    spot.status = 'A'
    db.session.commit()
    flash(f"Spot vacated successfully! Total cost: ₹{total_cost}", "success")
    return redirect(url_for('my_reservations'))

# -------------------- Search by Spot or Lot ID --------------------

@app.route('/search_spot')
def search_spot():
    query = request.args.get('query')
    if not query:
        return render_template('search_result.html', not_found=True)
    try:
        query_id = int(query.strip())
        spot = ParkingSpot.query.filter_by(id=query_id).first()
        if spot:
            return render_template('search_result.html', spot=spot)
        lot = ParkingLot.query.filter_by(id=query_id).first()
        if lot:
            spots = ParkingSpot.query.filter_by(lot_id=lot.id).all()
            return render_template('search_result.html', spots=spots)
    except ValueError:
        pass
    return render_template('search_result.html', not_found=True)

if __name__ == '__main__':
    app.run(debug=True)
