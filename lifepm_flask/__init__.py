from flask import Flask, render_template, redirect, url_for, jsonify, request
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import FlaskForm, CSRFProtect
from wtforms import IntegerField, StringField, SelectField, DateField, TimeField, BooleanField, DateTimeField, SubmitField
from wtforms.validators import DataRequired, Optional, ValidationError
from sqlalchemy import nulls_last, and_, or_

from database.models import metadata, Task, Interval
from database.db_handling import DB_URI

from datetime import date, timedelta
from os import urandom
from typing import List

def OptionalUnless(fieldname, expected_value, msg):
    def _validator(form, field):
        other_field = form[fieldname]
        if other_field.data != expected_value and not field.data:
            raise ValidationError(msg)
    return _validator

class TableRow(FlaskForm):
    id = IntegerField("ID")
    title = StringField("Title", validators=[DataRequired()])
    description = StringField("Description")
    recurring_time = SelectField("Recurring Interval", 
                                 choices=[(period.value, period.name.title()) for period in Interval],
                                 validators=[DataRequired()],
                                 default=Interval.NEVER.value)
    due_date = DateField("Due Date", validators=[OptionalUnless('recurring_time', 0, 'Due Date required if recurring is set!')])
    due_time = TimeField("Due Time", validators=[Optional()])
    time_cost = IntegerField("Time Cost", validators=[DataRequired()])
    reminder = IntegerField("Reminder (Days)", default=0)
    completed = BooleanField("Completed", default=False)
    created = DateTimeField("Created Date")
    
    submit = SubmitField("Update")

db = SQLAlchemy(metadata=metadata)
app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = DB_URI
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config['SECRET_KEY'] = urandom(32)
db.init_app(app)

CSRFProtect(app)

with app.app_context():
    db.create_all()

def flatten_query(tasks) -> List[Task]:
    return [task[0] for task in tasks]

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/table')
def table_view():
    col_names = [col.name for col in Task.__table__.columns]
    tasks = db.session.execute(db.select(Task).order_by(nulls_last(Task.due_date), Task.id)).all()
    
    tasks = flatten_query(tasks)
    return render_template("table.html", cols=col_names, tasks=tasks)

def handle_form(task: Task, form: TableRow, redirect_url: str):
    bad_submit = False
    if form.is_submitted():
        if form.validate():
            form.populate_obj(task)
            db.session.add(task)
            db.session.commit()
            return redirect(redirect_url)
        bad_submit = True
        print(form.errors)
    
    return render_template('create.html', form=form, bad_submit=bad_submit)
    
@app.route('/create', methods=['GET', 'POST'])
def create():
    return handle_form(Task(), TableRow(), url_for('home'))

@app.route('/edit/<int:id>', methods=['GET', 'POST'])
def edit(id):
    task = db.get_or_404(Task, id)
    form = TableRow(obj=task)
    return handle_form(task, form, url_for('table_view'))

@app.route('/get_daily/<int:mins_budget>', methods=['GET'])
def get_daily(mins_budget):
    today = date.today()
    curr_mins = 0
    chosen_tasks = []
    
    due_tasks = db.session.execute(db.select(Task)
                               .filter(and_(~Task.completed, Task.due_date.isnot(None), Task.due_date <= today))
                               .order_by(Task.due_date)).all()
    due_tasks = flatten_query(due_tasks)
    for task in due_tasks:
        curr_mins += task.time_cost
        chosen_tasks.append(task)

    tasks = db.session.execute(db.select(Task)
                               .filter(and_(~Task.completed, or_(Task.due_date.is_(None), Task.due_date > today)))
                               .order_by(Task.time_cost)).all()
    tasks = flatten_query(tasks)
    
    for task in tasks:
        if curr_mins + task.time_cost <= mins_budget:
            curr_mins += task.time_cost
            chosen_tasks.append(task)
            continue
        break

    chosen_tasks = [task.to_dict() for task in chosen_tasks]
    
    notifications = []
    for task in tasks:
        # null due dates are at the bottom
        if task.due_date is None:
            break
        
        # add notifications if today is within reminder
        if today >= task.due_date - timedelta(days=task.reminder):
            notifications.append(task)
    
    notifications = [task.to_dict() for task in notifications]
    
    print(jsonify({'tasks': chosen_tasks, 'notifs': notifications}))
    return jsonify({'tasks': chosen_tasks, 'notifs': notifications})#redirect(url_for('home'))


@app.route('/update_recurring', methods=['GET'])
def update_recurring():
    today = date.today()
    recurring_tasks = db.session.execute(db.select(Task)
                        .filter(and_(~Task.completed, Task.recurring_time.isnot(0), Task.due_date < today))).all()
    recurring_tasks = flatten_query(recurring_tasks)
    
    try:
        for task in recurring_tasks:
            recurring_days = Interval(task.recurring_time)
            
            if recurring_days == Interval.DAILY:
                recurring_days = 1
            elif recurring_days == Interval.WEEKLY:
                recurring_days = 7
            elif recurring_days == Interval.MONTHLY:
                pass
            
            days_over = (today - task.due_date).days
            added_days = days_over % recurring_days
            new_due_date = today + timedelta(days=added_days)
            print(new_due_date)
            task.due_date = new_due_date
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify(e)
        
    return jsonify('Done')