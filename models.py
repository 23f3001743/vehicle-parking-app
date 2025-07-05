from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

# ------------------ User Model ------------------
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    phone = db.Column(db.String(20))
    password = db.Column(db.String(200), nullable=False)
    vehicle_number = db.Column(db.String(20))
    role = db.Column(db.String(20), default='user')  # 'admin' or 'user'
    reservations = db.relationship("Reservation", backref="user", lazy=True)

# ------------------ Parking Lot Model ------------------
class ParkingLot(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    prime_location = db.Column(db.String(100), nullable=False)
    address = db.Column(db.String(200), nullable=False)
    price = db.Column(db.Float, nullable=False)  # Cost per hour
    pin_code = db.Column(db.String(10), nullable=False)
    total_spots = db.Column(db.Integer, nullable=False)
    spots = db.relationship('ParkingSpot', backref='lot', lazy=True, cascade="all, delete-orphan")
    reservations = db.relationship('Reservation', backref='lot', lazy=True)

# ------------------ Parking Spot Model ------------------
class ParkingSpot(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    lot_id = db.Column(db.Integer, db.ForeignKey('parking_lot.id'), nullable=False)
    status = db.Column(db.Enum('A', 'O'), default='A', nullable=False)   # A = Available, O = Occupied
    spot_number = db.Column(db.Integer, nullable=False)
    current_reservation_id = db.Column(db.Integer, db.ForeignKey('reservation.id'), nullable=True)

    # This relationship is for the current reservation (if any)
    current_reservation = db.relationship(
        "Reservation",
        foreign_keys=[current_reservation_id],
        uselist=False
    )
    # This relationship is for all reservations for this spot
    reservations = db.relationship(
        "Reservation",
        backref="spot",
        lazy=True,
        foreign_keys="[Reservation.spot_id]"
    )

# ------------------ Reservation Model ------------------
class Reservation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    spot_id = db.Column(db.Integer, db.ForeignKey('parking_spot.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    lot_id = db.Column(db.Integer, db.ForeignKey('parking_lot.id'), nullable=False)
    parking_timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    leaving_timestamp = db.Column(db.DateTime, nullable=True)
    cost_per_hour = db.Column(db.Float, nullable=False)
    total_cost = db.Column(db.Float, nullable=True)
