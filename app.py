from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from functools import wraps
import csv
from flask import send_file

from models import db, User, Goal, AuditLog

app = Flask(__name__)

app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:pict12345@localhost/goaltracker'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

app.secret_key = "goaltracker123"

db.init_app(app)

with app.app_context():
    db.create_all()
    print("Tables Created Successfully")


# ====================================================
# ROLE-BASED ACCESS CONTROL
# ====================================================

def login_required(f):

    @wraps(f)
    def decorated_function(*args, **kwargs):

        if 'user_id' not in session:

            flash("Please login first", "danger")

            return redirect(url_for('login'))

        return f(*args, **kwargs)

    return decorated_function


def employee_required(f):

    @wraps(f)
    def decorated_function(*args, **kwargs):

        if 'user_id' not in session:

            flash("Please login first", "danger")

            return redirect(url_for('login'))

        if session.get('role') != 'employee':

            flash("Access denied", "danger")

            return redirect(url_for('login'))

        return f(*args, **kwargs)

    return decorated_function


def manager_required(f):

    @wraps(f)
    def decorated_function(*args, **kwargs):

        if 'user_id' not in session:

            flash("Please login first", "danger")

            return redirect(url_for('login'))

        if session.get('role') != 'manager':

            flash("Access denied", "danger")

            return redirect(url_for('login'))

        return f(*args, **kwargs)

    return decorated_function


def admin_required(f):

    @wraps(f)
    def decorated_function(*args, **kwargs):

        if 'user_id' not in session:

            flash("Please login first", "danger")

            return redirect(url_for('login'))

        if session.get('role') != 'admin':

            flash("Access denied", "danger")

            return redirect(url_for('login'))

        return f(*args, **kwargs)

    return decorated_function


# ====================================================
# SCORE CALCULATION
# ====================================================

def calculate_score(goal):

    if not goal.target_value or goal.target_value == 0:
        return 0

    actual = goal.actual_value or 0

    if goal.uom in ["Numeric", "%"]:

        return round((actual / goal.target_value) * 100, 2)

    elif goal.uom == "Max":

        return round((goal.target_value / actual) * 100, 2) if actual != 0 else 0

    elif goal.uom == "Zero":

        return 100 if actual == 0 else 0

    return 0


# ====================================================
# PROGRESS CALCULATION
# ====================================================

def calculate_progress(goal):

    if not goal.target_value or goal.target_value == 0:
        return 0

    actual = goal.actual_value or 0

    progress = (actual / goal.target_value) * 100

    return round(progress, 2)


# ====================================================
# AUTO STATUS
# ====================================================

def get_status(goal):

    progress = calculate_progress(goal)

    if progress >= 100:

        return "Completed"

    elif progress >= 70:

        return "On Track"

    else:

        return "At Risk"


# ====================================================
# QUARTER VALIDATION
# ====================================================

def allowed_quarter():

    current_month = datetime.now().month

    if current_month == 5:
        return "Goal Setting"

    elif current_month == 7:
        return "Q1"

    elif current_month == 10:
        return "Q2"

    elif current_month == 1:
        return "Q3"

    elif current_month in [3, 4]:
        return "Q4"

    return "Closed"


# ====================================================
# LOGIN
# ====================================================

@app.route('/', methods=['GET', 'POST'])
def login():

    if request.method == 'POST':

        email = request.form['email']
        password = request.form['password']

        user = User.query.filter_by(
            email=email,
            password=password
        ).first()

        if user:

            session['user_id'] = user.id
            session['role'] = user.role
            session['name'] = user.name

            flash(f"Welcome {user.name}", "success")

            if user.role == 'employee':
                return redirect(url_for('employee_dashboard'))

            elif user.role == 'manager':
                return redirect(url_for('manager_dashboard'))

            elif user.role == 'admin':
                return redirect(url_for('admin_goals'))

        else:

            flash("Invalid Credentials", "danger")

    return render_template('login.html')


# ====================================================
# EMPLOYEE DASHBOARD
# ====================================================

@app.route('/employee/dashboard')
@employee_required
def employee_dashboard():

    return render_template('employee_dashboard.html')


# ====================================================
# MANAGER DASHBOARD
# ====================================================

@app.route('/manager/dashboard')
@manager_required
def manager_dashboard():

    return render_template('manager_dashboard.html')


# ====================================================
# LOGOUT
# ====================================================

@app.route('/logout')
@login_required
def logout():

    session.clear()

    flash("Logged out successfully", "success")

    return redirect(url_for('login'))


# ====================================================
# CREATE GOAL
# ====================================================

@app.route('/create-goal', methods=['GET', 'POST'])
@employee_required
def create_goal():

    if request.method == 'POST':

        title = request.form['title']
        description = request.form['description']
        thrust_area = request.form['thrust_area']
        uom = request.form['uom']
        target_value = float(request.form['target_value'])
        weightage = int(request.form['weightage'])

        if weightage < 10:

            flash("Minimum weightage per goal is 10%", "danger")

            return redirect(url_for('create_goal'))

        existing_goals = Goal.query.filter_by(
            employee_id=session['user_id']
        ).count()

        if existing_goals >= 8:

            flash("Maximum 8 goals allowed", "danger")

            return redirect(url_for('create_goal'))

        total_weightage = db.session.query(
            db.func.sum(Goal.weightage)
        ).filter_by(
            employee_id=session['user_id']
        ).scalar()

        if total_weightage is None:
            total_weightage = 0

        if total_weightage + weightage > 100:

            flash("Total weightage cannot exceed 100%", "danger")

            return redirect(url_for('create_goal'))

        goal = Goal(
            title=title,
            description=description,
            thrust_area=thrust_area,
            uom=uom,
            target_value=target_value,
            weightage=weightage,
            employee_id=session['user_id']
        )

        db.session.add(goal)
        db.session.commit()

        # AUDIT LOG FIXED
        audit = AuditLog(
            goal_id=goal.id,
            action="Goal Created",
            old_value="No Goal",
            new_value=title,
            changed_by=session['name']
        )

        db.session.add(audit)
        db.session.commit()

        flash("Goal Created Successfully", "success")

        return redirect(url_for('view_goals'))

    return render_template('create_goal.html')


# ====================================================
# VIEW GOALS
# ====================================================

@app.route('/view-goals')
@employee_required
def view_goals():

    goals = Goal.query.filter_by(
        employee_id=session['user_id']
    ).all()

    return render_template(
        'view_goals.html',
        goals=goals,
        calculate_progress=calculate_progress,
        calculate_score=calculate_score,
        get_status=get_status
    )


# ====================================================
# EDIT GOAL
# ====================================================

@app.route('/edit-goal/<int:goal_id>', methods=['GET', 'POST'])
@employee_required
def edit_goal(goal_id):

    goal = Goal.query.get_or_404(goal_id)

    if goal.employee_id != session['user_id']:

        flash("Unauthorized access", "danger")

        return redirect(url_for('view_goals'))

    if goal.is_locked:

        flash("Goal is locked and cannot be edited", "danger")

        return redirect(url_for('view_goals'))

    if request.method == 'POST':

        old_title = goal.title

        goal.title = request.form['title']
        goal.description = request.form['description']
        goal.thrust_area = request.form['thrust_area']

        db.session.commit()

        audit = AuditLog(
            goal_id=goal.id,
            action="Goal Edited",
            old_value=old_title,
            new_value=goal.title,
            changed_by=session['name']
        )

        db.session.add(audit)
        db.session.commit()

        flash("Goal Updated Successfully", "success")

        return redirect(url_for('view_goals'))

    return render_template(
        'edit_goal.html',
        goal=goal
    )

# ====================================================
# DELETE GOAL (EMPLOYEE)
# ====================================================

@app.route('/delete-goal/<int:goal_id>')
@employee_required
def delete_goal(goal_id):

    goal = Goal.query.get_or_404(goal_id)

    if goal.employee_id != session['user_id']:

        flash("Unauthorized access", "danger")

        return redirect(url_for('view_goals'))

    db.session.delete(goal)

    audit = AuditLog(
        goal_id=goal.id,
        action="Goal Deleted",
        old_value=goal.title,
        new_value="Deleted",
        changed_by=session['name']
    )

    db.session.add(audit)

    db.session.commit()

    flash("Goal Deleted Successfully", "success")

    return redirect(url_for('view_goals'))

# ====================================================
# MANAGER GOALS
# ====================================================

@app.route('/manager/goals')
@manager_required
def manager_goals():

    status = request.args.get('status', 'Pending')

    if status == 'All':

        goals = Goal.query.all()

    else:

        goals = Goal.query.filter_by(
            approval_status=status
        ).all()

    return render_template(
        'manager_goals.html',
        goals=goals,
        current_status=status
    )


# ====================================================
# MANAGER EDIT GOAL
# ====================================================

@app.route('/manager/edit-goal/<int:goal_id>', methods=['GET', 'POST'])
@manager_required
def manager_edit_goal(goal_id):

    goal = Goal.query.get_or_404(goal_id)

    if request.method == 'POST':

        old_target = goal.target_value

        goal.target_value = float(request.form['target_value'])
        goal.weightage = int(request.form['weightage'])

        db.session.commit()

        audit = AuditLog(
            goal_id=goal.id,
            action="Manager Edited Goal",
            old_value=str(old_target),
            new_value=str(goal.target_value),
            changed_by=session['name']
        )

        db.session.add(audit)
        db.session.commit()

        flash("Goal Updated Successfully", "success")

        return redirect(url_for('manager_goals'))

    return render_template(
        'edit_goal.html',
        goal=goal
    )

# ====================================================
# MANAGER DELETE GOAL
# ====================================================

@app.route('/manager/delete-goal/<int:goal_id>')
@manager_required
def manager_delete_goal(goal_id):

    goal = Goal.query.get_or_404(goal_id)

    db.session.delete(goal)

    audit = AuditLog(
        goal_id=goal.id,
        action="Manager Deleted Goal",
        old_value=goal.title,
        new_value="Deleted",
        changed_by=session['name']
    )

    db.session.add(audit)

    db.session.commit()

    flash("Goal Deleted Successfully", "success")

    return redirect(url_for('manager_goals'))

# ====================================================
# APPROVE GOAL
# ====================================================

@app.route('/approve/<int:goal_id>')
@manager_required
def approve_goal(goal_id):

    goal = Goal.query.get_or_404(goal_id)

    goal.approval_status = "Approved"
    goal.is_locked = True

    db.session.commit()

    audit = AuditLog(
        goal_id=goal.id,
        action="Goal Approved",
        old_value="Pending",
        new_value="Approved",
        changed_by=session['name']
    )

    db.session.add(audit)
    db.session.commit()

    flash("Goal Approved Successfully", "success")

    return redirect(url_for('manager_goals'))


# ====================================================
# REJECT GOAL
# ====================================================

@app.route('/reject/<int:goal_id>')
@manager_required
def reject_goal(goal_id):

    goal = Goal.query.get_or_404(goal_id)

    goal.approval_status = "Rejected"
    goal.is_locked = True

    db.session.commit()

    audit = AuditLog(
        goal_id=goal.id,
        action="Goal Rejected",
        old_value="Pending",
        new_value="Rejected",
        changed_by=session['name']
    )

    db.session.add(audit)
    db.session.commit()

    flash("Goal Rejected Successfully", "danger")

    return redirect(url_for('manager_goals'))


# ====================================================
# UPDATE ACHIEVEMENT
# ====================================================

@app.route('/update-achievement/<int:goal_id>', methods=['GET', 'POST'])
@employee_required
def update_achievement(goal_id):

    goal = Goal.query.get_or_404(goal_id)

    if goal.employee_id != session['user_id']:
        flash("Unauthorized access", "danger")
        return redirect(url_for('view_goals'))

    if request.method == 'POST':

        old_actual = goal.actual_value

        goal.actual_value = float(request.form['actual_value'])

        goal.status = get_status(goal)

        goal.quarter = request.form['quarter']

        goal.checkin_comment = request.form['checkin_comment']

        db.session.commit()

        audit = AuditLog(
            goal_id=goal.id,
            action="Achievement Updated",
            old_value=f"Actual={old_actual}",
            new_value=f"Actual={goal.actual_value}",
            changed_by=session['name']
        )

        db.session.add(audit)
        db.session.commit()

        flash("Achievement Updated Successfully", "success")

        return redirect(url_for('view_goals'))

    return render_template(
        'update_achievement.html',
        goal=goal
    )


# ====================================================
# MANAGER CHECK-IN
# ====================================================

@app.route('/manager/checkin/<int:goal_id>', methods=['GET', 'POST'])
@manager_required
def manager_checkin(goal_id):

    goal = Goal.query.get_or_404(goal_id)

    if request.method == 'POST':

        manager_comment = request.form['manager_comment']

        audit = AuditLog(
            goal_id=goal.id,
            action="Manager Check-In",
            old_value="No Comment",
            new_value=manager_comment,
            changed_by=session['name']
        )

        db.session.add(audit)
        db.session.commit()

        flash("Manager Check-In Added", "success")

        return redirect(url_for('manager_goals'))

    return render_template(
        'manager_checkin.html',
        goal=goal
    )


# ====================================================
# CREATE SHARED GOAL
# ====================================================

@app.route('/create-shared-goal', methods=['GET', 'POST'])
@manager_required
def create_shared_goal():

    employees = User.query.filter_by(role='employee').all()

    if request.method == 'POST':

        employee_ids = request.form.getlist('employee_ids')

        if not employee_ids:

            flash("Please select employees", "danger")

            return redirect(url_for('create_shared_goal'))

        for emp_id in employee_ids:

            goal = Goal(
                title=request.form['title'],
                description=request.form['description'],
                thrust_area=request.form['thrust_area'],
                uom=request.form['uom'],
                target_value=float(request.form['target_value']),
                weightage=int(request.form['weightage']),
                employee_id=int(emp_id),
                is_shared=True
            )

            db.session.add(goal)

        db.session.commit()

        # AUDIT TRAIL
        for emp_id in employee_ids:

            audit = AuditLog(
                goal_id=0,
                action="Shared Goal Created",
                old_value="N/A",
                new_value=request.form['title'],
                changed_by=session['name']
            )

            db.session.add(audit)

        db.session.commit()

        flash(
            "Shared Goal Created Successfully For Selected Employees",
            "success"
        )

        return redirect(url_for('manager_goals'))

    return render_template(
        'create_shared_goal.html',
        employees=employees
    )
# ====================================================
# ADMIN DASHBOARD
# ====================================================

@app.route('/admin/goals')
@admin_required
def admin_goals():

    goals = Goal.query.all()

    total_goals = Goal.query.count()

    approved_goals = Goal.query.filter_by(
        approval_status="Approved"
    ).count()

    pending_goals = Goal.query.filter_by(
        approval_status="Pending"
    ).count()

    completed_goals = Goal.query.filter_by(
        status="Completed"
    ).count()

    completion_percentage = 0

    if total_goals > 0:

        completion_percentage = round(
            (completed_goals / total_goals) * 100,
            2
        )

    return render_template(
        'admin_goals.html',
        goals=goals,
        total_goals=total_goals,
        approved_goals=approved_goals,
        pending_goals=pending_goals,
        completed_goals=completed_goals,
        completion_percentage=completion_percentage
    )


# ====================================================
# UNLOCK GOAL
# ====================================================

@app.route('/unlock-goal/<int:goal_id>')
@admin_required
def unlock_goal(goal_id):

    goal = Goal.query.get_or_404(goal_id)

    goal.is_locked = False

    db.session.commit()

    audit = AuditLog(
        goal_id=goal.id,
        action="Goal Unlocked",
        old_value="Locked",
        new_value="Unlocked",
        changed_by=session['name']
    )

    db.session.add(audit)
    db.session.commit()

    flash("Goal Unlocked Successfully", "success")

    return redirect(url_for('admin_goals'))


# ====================================================
# AUDIT LOGS
# ====================================================

@app.route('/audit-logs')
@admin_required
def audit_logs():

    logs = AuditLog.query.order_by(
        AuditLog.changed_at.desc()
    ).all()

    return render_template(
        'audit_logs.html',
        logs=logs
    )


# ====================================================
# EXPORT CSV REPORT
# ====================================================

@app.route('/export-report')
@admin_required
def export_report():

    goals = Goal.query.all()

    filename = "achievement_report.csv"

    with open(filename, mode='w', newline='') as file:

        writer = csv.writer(file)

        writer.writerow([
            "Goal ID",
            "Title",
            "Employee ID",
            "Status",
            "Progress %",
            "Score"
        ])

        for goal in goals:

            writer.writerow([
                goal.id,
                goal.title,
                goal.employee_id,
                goal.status,
                calculate_progress(goal),
                calculate_score(goal)
            ])

    return send_file(
        filename,
        as_attachment=True
    )


# ====================================================
# RUN APP
# ====================================================

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
