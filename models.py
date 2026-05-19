from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class User(db.Model):

    id = db.Column(db.Integer, primary_key=True)

    name = db.Column(db.String(100))

    email = db.Column(db.String(100), unique=True)

    password = db.Column(db.String(100))

    role = db.Column(db.String(50))


class Goal(db.Model):

    id = db.Column(db.Integer, primary_key=True)

    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.String(500))

    # NEW (Requirement: Thrust Area)
    thrust_area = db.Column(db.String(100))

    # Unit of Measurement
    uom = db.Column(db.String(50))  # Numeric / % / Timeline / Zero

    target_value = db.Column(db.Float, nullable=False)

    # PHASE 2 (IMPORTANT)
    actual_value = db.Column(db.Float, default=0)

    status = db.Column(db.String(50), default='Not Started')
    approval_status = db.Column(db.String(50), default='Pending')

    weightage = db.Column(db.Integer, nullable=False)

    employee_id = db.Column(db.Integer, db.ForeignKey('user.id'))

    # IMPORTANT FOR REQUIREMENT
    is_locked = db.Column(db.Boolean, default=False)

    quarter = db.Column(db.String(10), default="Q1")
    checkin_comment = db.Column(db.String(500))
    is_shared = db.Column(db.Boolean, default=False)

    shared_owner_id = db.Column(db.Integer, nullable=True)
class AuditLog(db.Model):

    id = db.Column(db.Integer, primary_key=True)

    goal_id = db.Column(db.Integer)

    action = db.Column(db.String(300))

    old_value = db.Column(db.String(500))

    new_value = db.Column(db.String(500))

    changed_by = db.Column(db.String(100))

    changed_at = db.Column(
        db.DateTime,
        default=db.func.current_timestamp()
    )