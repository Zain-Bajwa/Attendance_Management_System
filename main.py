import os
import pandas as pd
from PIL import Image
from calendar import monthrange
from flask import Flask, render_template, request, redirect, url_for, session, send_from_directory
import mysql.connector
from datetime import datetime, date, timedelta
import re

app = Flask(__name__, static_url_path='')

# Change this to your secret key (can be anything, it's for extra protection)
app.secret_key = 'your secret key'

# Enter your database connection details below
db_con = mysql.connector.connect(
    host='localhost',
    user='root',
    passwd='root',
    database='attendance_ms'
)

dbCursor = db_con.cursor(buffered=True, dictionary=True)


# return all days of current year and month
def date_iter(year, month):
    all_days = {'date': [], 'day': [], 'presence': []}
    for i in range(1, monthrange(year, month)[1] + 1):
        day = date(year, month, i).strftime('%A')
        # datetime.strptime('2021-08-20', '%Y-%m-%d').date().strftime('%A')
        if day != 'Sunday':
            all_days['date'].append(str(date(year, month, i)))
            all_days['day'].append(day)
            all_days['presence'].append('A')
    return all_days


def single_student_attendance_report(attendance, param):
    attendance = pd.DataFrame(attendance).to_dict(orient="list")
    attendance_report = {'Student ID': [], 'Date': [], 'Day': [], 'Presence': []}
    start_date = datetime.strptime(param['from_date'], '%Y-%m-%d').date()
    end_date = datetime.strptime(param['to_date'], '%Y-%m-%d').date()
    delta = timedelta(days=1)
    while start_date <= end_date:
        if start_date.strftime("%A") != 'Sunday':
            attendance_report['Student ID'].append(param['user_id_search'])
            attendance_report['Date'].append(start_date.strftime("%Y-%m-%d"))
            attendance_report['Day'].append(start_date.strftime("%A"))
            if start_date in attendance['date']:
                attendance_report['Presence'].append('P')
            else:
                attendance_report['Presence'].append('A')
        start_date += delta

    return attendance_report


def set_parameters(param):
    months = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
              "November", "December"]
    if param['month'] and param['month'] in months:
        all_days = date_iter(param['year'], months.index(param['month']) + 1)
        # param['month'] = date(2021, months.index(param['month']) + 1, 20).strftime('%B')
        param['selected'] = True
        return all_days, param
    else:
        all_days = date_iter(param['year'], datetime.now().date().month)
        param['month'] = datetime.now().date().strftime('%B')
        param['selected'] = False
        return all_days, param


@app.route('/', methods=['GET', 'POST'])
def login():
    # Output message if something goes wrong...
    msg = ''
    if request.method == 'GET' and 'loggedin' in session and "username" in session and 'id' in session:
        return redirect(url_for('home'))
    # Check if "username" and "password" POST requests exist (user submitted form)
    if request.method == 'POST' and 'username' in request.form and 'password' in request.form:
        # Create variables for easy access
        username = request.form['username']
        password = request.form['password']
        if username and password:
            # Check if account exists using MySQL
            dbCursor.execute('SELECT * FROM users WHERE username = %s AND password = %s',
                             (username, password,))
            # Fetch one record and return result
            account = dbCursor.fetchone()
            # If account exists in accounts table in out database
            if account:
                # Create session data, we can access this data in other routes
                session['loggedin'] = True
                session['id'] = account['user_id']
                session['username'] = account['username']
                session['name'] = account['name']
                session['type'] = 0
                if account['type'] == 1:
                    session['type'] = 1
                # Redirect to home page
                return redirect(url_for('home'))
            else:
                # Account doesnt exist or username/password incorrect
                msg = 'Incorrect username/password!'
    # Show the login form with message (if any)
    return render_template('index.html', msg=msg)

    # http://localhost:5000/python/logout - this will be the logout page


@app.route('/logout')
def logout():
    # Remove session data, this will log the user out
    session.pop('loggedin', None)
    session.pop('id', None)
    session.pop('username', None)
    session.pop('name', None)
    session.pop('type', None)
    # Redirect to login page
    return redirect(url_for('login'))


# http://localhost:5000/pythinlogin/register - this will be the registration page, we need to use both GET and POST requests
@app.route('/register', methods=['GET', 'POST'])
def register():
    # Output message if something goes wrong...
    msg = {
        "username_msg": "",
        "name_msg": "",
        "email_msg": "",
        "password_msg": "",
        "image_msg": "",
        "account_msg": "",
        "success_msg": "",
        "fill_msg": ""
    }
    # Check if "username", "password" and "email" POST requests exist (user submitted form)
    if request.method == 'POST' and 'username' in request.form and 'name' in request.form and 'password' in request.form and 'email' in request.form and 'address' in request.form:
        # Create variables for easy access
        username = request.form['username']
        name = request.form['name']
        email = request.form['email']
        address = request.form['address']
        password = request.form['password']
        image = request.files['file']
        confirm_password = request.form['confirm-password']
        if username and email and address and password and confirm_password:
            dbCursor.execute('SELECT * FROM users WHERE name = %s', (username,))
            account = dbCursor.fetchone()
            # If account exists show error and validation checks
            if account:
                msg["account_msg"] = 'Account already exists!'
            elif not re.match(r'^[A-Za-z0-9_]+$', username):
                msg["username_msg"] = 'Username must be characters/underscore/numbers!'
            elif not re.match(r'^[A-Za-z0-9_ ]+$', name):
                msg["name_msg"] = 'Only alphabets/underscore/numbers/space!'
            elif not re.match(r'[\w][\w\d]+@[\w]+\.[\w]+', email):
                msg["email_msg"] = 'Invalid email address!'
            elif password != confirm_password:
                msg["password_msg"] = "Password don't match!"
            elif not image:
                msg["image_msg"] = "Please select an image."
            else:
                # convert into ASCII
                file_name = ''.join(str(ord(c)) for c in username)
                # join ASCII, . and file extention.
                im = Image.open(image)
                im = im.convert("RGB")
                im.save("static/pictures/" + file_name + ".jpg")
                # file_name = file_name + "." + image.filename.rsplit('.', 1)[1]
                # image.save(os.path.join('static/pictures', file_name))
                # Account doesnt exists and the form data is valid, now insert new account into accounts table
                dbCursor.execute('INSERT INTO users VALUES (NULL, %s, %s, %s, %s, %s, %s)',
                                 (username, name, email, password, 0, address))
                db_con.commit()
                msg["success_msg"] = 'You have successfully registered!'
        # elif request.method == 'POST':
        # Form is empty... (no POST data)
        else:
            msg["fill_msg"] = 'Please fill out the form!'
    # Show registration form with message (if any)
    return render_template('register.html', msg=msg)


# http://localhost:5000/pythinlogin/home - this will be the home page, only accessible for loggedin users
@app.route('/home', methods=['GET', 'POST'])
def home():
    # Check if user is loggedin
    if 'loggedin' in session and "username" in session and "name" in session and 'id' in session:
        parameters = {'name': session['name'], 'msg': '', 'attendance': 0,
                      'today_date': datetime.now().date().strftime('%d-%b-%Y'),
                      'date': request.args.get("date", default="", type=str),
                      'from_date': request.args.get("from_date", default="", type=str),
                      'to_date': request.args.get("to_date", default="", type=str),
                      'message': request.args.get("message", default="", type=str),
                      'search_name': request.args.get("search_name", default="", type=str),
                      'show_all_students': request.args.get("show_all_students", default="", type=str),
                      'img_path': 'pictures/' + ''.join(str(ord(c)) for c in session["username"]) + ".jpg"}

        sql_date = datetime.now().date().strftime('%Y-%m-%d')
        sql_day = datetime.now().date().strftime('%A')

        dbCursor.execute('SELECT * FROM users WHERE user_id = %s', (session['id'],))
        user = dbCursor.fetchone()
        if user:
            if user['type'] == 0:
                dbCursor.execute('SELECT * FROM attendances WHERE user_id = %s AND date = %s',
                                 (session['id'], sql_date))
                record = dbCursor.fetchone()
                if record:
                    parameters['attendance'] = 1
                if parameters['date'] and parameters['message']:
                    if datetime.strptime(parameters['date'],
                                         '%Y-%m-%d').date() >= datetime.now().date() and datetime.strptime(
                            parameters['date'], '%Y-%m-%d').date().strftime('%A') != 'Sunday':
                        month = datetime.strptime(parameters['date'], '%Y-%m-%d').date().strftime('%B')
                        dbCursor.execute('SELECT * FROM leaves WHERE user_id = %s AND monthname(date)= %s',
                                         (session['id'], month))
                        if dbCursor.rowcount <= 1:
                            leaves = dbCursor.fetchall()
                            if leaves:
                                if datetime.strptime(parameters['date'], '%Y-%m-%d').date() not in \
                                        pd.DataFrame(leaves).to_dict(orient='list')['date']:
                                    dbCursor.execute('INSERT INTO leaves VALUES(%s, %s, %s, %s)',
                                                     (session['id'], parameters['date'], 0, parameters['message']))
                                    db_con.commit()
                                    parameters[
                                        'msg'] = "You have successfully requested for leave in " + datetime.strptime(
                                        parameters['date'], '%Y-%m-%d').date().strftime('%d-%b-%Y') + "."
                                    return render_template('home.html', parameters=parameters)
                                else:
                                    parameters['msg'] = "You have already requested for date " + datetime.strptime(
                                        parameters['date'], '%Y-%m-%d').date().strftime('%d-%b-%Y') + "."
                                    return render_template('home.html', parameters=parameters)
                            else:
                                dbCursor.execute('INSERT INTO leaves VALUES(%s, %s, %s, %s)',
                                                 (session['id'], parameters['date'], 0, parameters['message']))
                                db_con.commit()
                                parameters['msg'] = "You have successfully requested for leave in " + datetime.strptime(
                                    parameters['date'], '%Y-%m-%d').date().strftime('%d-%b-%Y') + "."
                                return render_template('home.html', parameters=parameters)
                        else:
                            parameters['msg'] = "You can't request for leave more than 2 times in a month."
                            return render_template('home.html', parameters=parameters)
                    else:
                        parameters['msg'] = "You can't request for leave in previous date or 'Sunday'."
                        return render_template('home.html', parameters=parameters)

                if request.method == 'GET':
                    return render_template('home.html', parameters=parameters)
                elif sql_day == 'Sunday':
                    parameters['msg'] = "Waoo... today is 'Sunday'."
                    return render_template('home.html', parameters=parameters)

                elif request.method == 'POST' and 'attendance' in request.form and parameters['attendance'] == 0:
                    dbCursor.execute('INSERT INTO attendances VALUES(%s, %s)',
                                     (session['id'], sql_date))
                    db_con.commit()
                    parameters['msg'] = "You have successfully marked your attendance."
                    parameters['attendance'] = 1
                    # User is loggedin show them the home page
                    return render_template('home.html', parameters=parameters)

                elif request.method == 'POST' and 'attendance' in request.form and parameters['attendance'] == 1:
                    parameters['msg'] = 'You have already marked your attendance.'
                    return render_template('home.html', parameters=parameters)

                elif request.method == 'POST' and ('attendance' not in request.form) and parameters['attendance'] == 0:
                    parameters['msg'] = 'Please mark your attendance and click on submit!'
                    return render_template('home.html', parameters=parameters)

                else:
                    return render_template('home.html', parameters=parameters)


            elif user['type'] == 1:
                all_students = []

                if parameters['search_name']:
                    dbCursor.execute("SELECT * FROM users where name like %s and type = %s",
                                     ('%' + parameters['search_name'] + '%', 0))
                    all_students = dbCursor.fetchall()
                    if all_students:
                        return render_template('admin_home.html', parameters=parameters, all_students=all_students)
                elif parameters['show_all_students'] and parameters['show_all_students'] == '1':
                    dbCursor.execute("SELECT * FROM users where type = %s", (0,))
                    all_students = dbCursor.fetchall()
                    if all_students:
                        return render_template('admin_home.html', parameters=parameters, all_students=all_students)
                #     Report of all students.
                elif parameters['from_date'] and parameters['to_date']:
                    dbCursor.execute(
                        "SELECT ROW_NUMBER() OVER (ORDER BY users.user_id) AS '#', users.user_id as 'Student ID', users.name as 'Name', users.username as 'UserName', users.email as 'Email', users.address as 'Address', MONTHNAME(attendances.date) as 'Month', count(attendances.user_id) as 'Present', count(attendances.date) as 'Absent', ROUND(count(*)/26*100, 2) as 'Percentage' FROM users JOIN attendances ON users.user_id=attendances.user_id WHERE users.type = %s and date BETWEEN %s AND %s GROUP BY users.user_id, MONTH(attendances.date) ORDER BY users.user_id",
                        (0, parameters['from_date'], parameters['to_date']))
                    attendances = dbCursor.fetchall()
                    if attendances:
                        attendances = pd.DataFrame(attendances)
                        attendances['Absent'] = 26 - attendances['Present']
                        attendances['Percentage'] = round(attendances['Present'] / 26 * 100).astype(str) + '%'

                        attendances.to_csv(
                            "static/reports/all_students_attendances.csv", index=False)
                        return send_from_directory(directory="static/reports/",
                                                   filename="all_students_attendances.csv", as_attachment=True)
                return render_template('admin_home.html', parameters=parameters, all_students=all_students)

    # User is not loggedin redirect to login page
    return redirect(url_for('login'))


# http://localhost:5000/pythinlogin/profile - this will be the profile page, only accessible for loggedin users
@app.route('/profile', methods=['GET', 'POST'])
def profile():
    # Check if user is loggedin
    if 'loggedin' in session and "id" in session and "username" in session:

        # We need all the account info for the user so we can display it on the profile page
        dbCursor.execute('SELECT * FROM users WHERE user_id = %s', (session['id'],))
        account = dbCursor.fetchone()

        # Show the profile page with account info
        if account:
            parameters = {'name': session['name'],
                          'img_path': 'pictures/' + ''.join(str(ord(c)) for c in session["username"]) + ".jpg"}
            if request.method == 'GET':
                return render_template('profile.html', account=account, parameters=parameters)
            elif request.method == 'POST':
                image = request.files['file']
                file_name = ''.join(str(ord(c)) for c in session["username"])
                im = Image.open(image)
                im = im.convert("RGB")
                im.save("static/pictures/" + file_name + ".jpg")
                return render_template('profile.html', account=account, parameters=parameters)
    # User is not loggedin redirect to login page
    return redirect(url_for('login'))


@app.route("/view", methods=['GET', 'POST'])
def view():
    if 'loggedin' in session and "username" in session and 'id' in session:
        # user_id_search will come from home page.
        parameters = {'name': session['name'], 'month': request.args.get("month", type=str),
                      'user_id_search': request.args.get("user_id_search", default="", type=str),
                      'year': datetime.now().date().year, 'date': request.args.get("date", default="", type=str),
                      'check': request.args.get("check", type=eval), 'progress': 0.0,
                      'from_date': request.args.get("from_date", default="", type=str),
                      'to_date': request.args.get("to_date", default="", type=str),
                      'student_name': request.args.get("student_name", default="", type=str),
                      'img_path': 'pictures/' + ''.join(str(ord(c)) for c in session["username"]) + ".jpg"}
        all_days, parameters = set_parameters(parameters)
        dbCursor.execute('SELECT * FROM users WHERE user_id = %s', (session['id'],))
        user = dbCursor.fetchone()
        if user:
            if user['type'] == 0:
                dbCursor.execute('SELECT * FROM attendances WHERE user_id = %s and monthname(date)= %s',
                                 (session['id'], parameters['month']))
                record = dbCursor.fetchall()
                if record:
                    for item in record:
                        if str(item['date']) in all_days['date']:
                            parameters['progress'] = parameters['progress'] + 1
                            all_days['presence'][all_days['date'].index(str(item['date']))] = 'P'
                parameters['progress'] = round(parameters['progress'] / 26 * 100, 2)
                return render_template('view.html', parameters=parameters, all_days=all_days)

            elif user['type'] == 1:
                result = {}
                if parameters['user_id_search']:
                    if parameters['date'] and type(parameters['check']) == bool:
                        if parameters['check'] == True:
                            dbCursor.execute('INSERT INTO attendances VALUES(%s, %s)',
                                             (parameters['user_id_search'], parameters['date']))
                            db_con.commit()
                        elif parameters['check'] == False:
                            dbCursor.execute('DELETE FROM attendances WHERE user_id = %s and date = %s',
                                             (parameters['user_id_search'], parameters['date']))
                            db_con.commit()

                    elif parameters['from_date'] and parameters['to_date'] and parameters['student_name']:
                        dbCursor.execute("SELECT * FROM attendances WHERE user_id = %s and date BETWEEN %s AND %s",
                                         (parameters['user_id_search'], parameters['from_date'], parameters['to_date']))
                        attendances = dbCursor.fetchall()
                        if attendances:
                            attendance_report = single_student_attendance_report(attendances, parameters)
                            pd.DataFrame(attendance_report).to_csv(
                                "static/reports/" + parameters['student_name'] + ".csv", index=False)

                        return send_from_directory(directory="static/reports/",
                                                   filename=parameters['student_name'] + ".csv", as_attachment=True)

                    dbCursor.execute("SELECT * FROM users where user_id = %s and type = %s",
                                     (parameters['user_id_search'], 0))
                    result['student'] = dbCursor.fetchone()
                    dbCursor.execute('SELECT * FROM attendances WHERE user_id = %s and monthname(date)= %s',
                                     (parameters['user_id_search'], parameters['month']))
                    result['attendance'] = dbCursor.fetchall()
                    if result['student']:
                        if result['attendance']:
                            for item in result['attendance']:
                                if str(item['date']) in all_days['date']:
                                    parameters['progress'] = parameters['progress'] + 1.0
                                    all_days['presence'][all_days['date'].index(str(item['date']))] = 'P'
                            parameters['progress'] = round(parameters['progress'] / 26 * 100, 2)
                        return render_template('admin_view.html', parameters=parameters, all_days=all_days,
                                               result=result)
                return render_template('error.html')

    return redirect(url_for('login'))


@app.route("/leave")
def leave():
    parameters = {'name': session['name'], 'msg': '', 'attendance': 0,
                  'month': request.args.get("month", default=datetime.now().date().strftime('%B'), type=str),
                  'img_path': 'pictures/' + ''.join(str(ord(c)) for c in session["username"]) + ".jpg"}

    if parameters['month'] in ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]:
        print("")

    return render_template('leave_admin.html', parameters=parameters)


@app.route("/error")
def error():
    return render_template('error.html')


if __name__ == '__main__':
    app.run(FLASK_DEBUG=True)
