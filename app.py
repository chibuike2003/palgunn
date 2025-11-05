import os
import re
from datetime import datetime

from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate # Import Migrate
from sqlalchemy.exc import IntegrityError
import json # For handling JSON data
import pytz
from datetime import datetime
from flask_login import LoginManager, login_required, current_user, UserMixin, login_user, logout_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from flask_uploads import UploadSet, configure_uploads, DOCUMENTS, IMAGES, ALL
from werkzeug.datastructures import FileStorage
import smtplib
from email.message import EmailMessage
from PIL import Image
# import pytesseract # Uncomment if you have pytesseract installed and configured
# import PyPDF2 # Uncomment if you have PyPDF2 installed
# import docx # Uncomment if you have python-docx installed

# Initialize the Flask application
app = Flask(__name__)

# --- Configuration ---
app.config['SECRET_KEY'] = 'fdtygt5e5re4ere43rt435erdrs34e56fdrde3w22121234567ytgytuih8uijhu87y6fvb' # A strong, unique secret key
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///pal.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False # Recommended to disable
app.config['UPLOAD_FOLDER'] = os.path.join(os.getcwd(), 'static', 'uploads') # Absolute path for file uploads

# Configure Flask-Uploads
app.config['UPLOADED_PROJECTS_DEST'] = os.path.join(app.root_path, 'static', 'project_uploads') # Separate folder for project files
app.config['UPLOADED_PROJECTS_ALLOW'] = DOCUMENTS + IMAGES + ('zip',) # Add 'zip' to allowed extensions
projects_uploads = UploadSet('projects', ALL) # Use ALL or specify accepted types explicitly
configure_uploads(app, projects_uploads)

# Ensure the upload directory exists
os.makedirs(app.config['UPLOADED_PROJECTS_DEST'], exist_ok=True)
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True) # Ensure this also exists for other uploads

# Initialize extensions
db = SQLAlchemy(app)
migrate = Migrate(app, db) # Initialize Flask-Migrate

# --- CONSOLIDATED FLASK-LOGIN SETUP ---
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'lecturer_login' # Default login view if @login_required is used

# User loader for Flask-Login
@login_manager.user_loader
def load_user(user_id):
    """
    Given a user ID, return the user object.
    This function is used by Flask-Login to reload the user from the session.
    It attempts to find the user in both Lecturer and User tables.
    """
    # Try to load as a Lecturer first
    # This prioritizes Lecturer if an ID exists in both tables.
    lecturer = Lecturer.query.get(int(user_id))
    if lecturer:
        return lecturer

    # If not a Lecturer, try to load as a general User
    # IMPORTANT: The User model MUST also inherit UserMixin for this to work correctly.
    user = User.query.get(int(user_id))
    if user:
        return user

    # If the user_id does not correspond to any known user type, return None
    return None



class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    fullname = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    regno = db.Column(db.String(100), unique=True, nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    profile_picture_url = db.Column(db.String(200), nullable=True, default='default.jpg')
    password = db.Column(db.String(200), nullable=False)
    public_key = db.Column(db.Text, nullable=True)

    # Define relationships for messages (assuming Message and ProjectIdea models exist)
    sent_messages = db.relationship('Message', foreign_keys='Message.sender_id', back_populates='sender', lazy=True)
    received_messages = db.relationship('Message', foreign_keys='Message.recipient_id', back_populates='recipient', lazy=True)
    project_ideas = db.relationship('ProjectIdea', backref='author', lazy=True) 

    def __repr__(self):
        return f"User('{self.fullname}', '{self.email}')"

    # Required for Flask-Login
    def is_authenticated(self):
        return True

    def is_active(self):
        return True

    def is_anonymous(self):
        return False

    def get_id(self):
        return str(self.id)
# Your ElectoralCandidate class would then be defined as discussed in the previous response,
# linking to the User model correctly.
class ElectoralCandidate(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    position = db.Column(db.String(50), nullable=False)
    profile_pic = db.Column(db.String(200), nullable=False)  # path to image
    # You might consider storing the profile_pic on the User model
    # and referencing it if the candidate's pic is the same as their user pic.

    # 1. Add a Foreign Key to link to the User model
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, unique=True)
    # Use unique=True if a User can only be a candidate once.

    # 2. Remove redundant fields: fullname and regno
    # These details should be pulled from the associated User object.
    # fullname = db.Column(db.String(100), nullable=False) # REMOVE THIS
    # regno = db.Column(db.String(20), unique=True, nullable=False) # REMOVE THIS

    # The 'user' attribute on ElectoralCandidate is implicitly created by the backref
    # 'user' on the db.relationship in the User model.
    # Alternatively, you could explicitly define it here if you prefer:
    # user = db.relationship('User', backref='electoral_candidate_profile')


    def __repr__(self):
        # Now, you can safely access self.user.fullname if the relationship is loaded
        # Add a check in case 'user' isn't loaded (e.g., during creation before commit)
        user_fullname = self.user.fullname if self.user else 'N/A'
        return f"ElectoralCandidate('{user_fullname}', '{self.position}')"




class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    recipient_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    encrypted_content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    # Define relationships here using back_populates
    # 'sender' on Message will link back to 'sent_messages' on User
    sender = db.relationship('User', foreign_keys=[sender_id], back_populates='sent_messages', lazy=True)
    # 'recipient' on Message will link back to 'received_messages' on User
    recipient = db.relationship('User', foreign_keys=[recipient_id], back_populates='received_messages', lazy=True)

    def __repr__(self):
        return f"<Message {self.id}>"




class Help(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    issue_type = db.Column(db.String(50), nullable=False)
    other_issue = db.Column(db.String(255), nullable=True)
    description = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref='help_reports')


class Contact(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), nullable=False) # Changed from fullname to username for consistency if you use username
    email = db.Column(db.String(150), nullable=False)
    subject = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    date_sent = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"Contact('{self.username}', '{self.email}', '{self.subject}')"





class PrivateChat(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    recipient_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    # Store the encrypted message as TEXT. It includes the ciphertext and nonce.
    encrypted_content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f'<PrivateChat from {self.sender_id} to {self.recipient_id} at {self.timestamp}>'


# New Rating Model
class Rating(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    rating = db.Column(db.Integer, nullable=False) # Store the star rating (1-5)
    comment = db.Column(db.Text, nullable=True) # User's comment
    timestamp = db.Column(db.DateTime, default=db.func.current_timestamp()) # When the rating was submitted

    # Define relationship to User
    user = db.relationship('User', backref='ratings')

    def __repr__(self):
        return f"Rating(User_ID: {self.user_id}, Rating: {self.rating}, Time: {self.timestamp})"


class ProjectIdea(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    innovations = db.Column(db.Text, nullable=True)
    file_paths = db.Column(db.Text, nullable=True) # Store comma-separated file paths
    contact_email = db.Column(db.String(100), nullable=False)
    submission_date = db.Column(db.DateTime, nullable=False, default=db.func.current_timestamp())
    visibility = db.Column(db.String(10), nullable=False, default='public') # 'public' or 'private'

    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True) # Assume nullable for now

    def __repr__(self):
        return f"ProjectIdea('{self.title}', '{self.submission_date}')"




# New UserBlog model for blog posts
class UserBlog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    date_posted = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    media_path = db.Column(db.String(200), nullable=True) # Path to uploaded media
    media_type = db.Column(db.String(10), nullable=True) # 'image' or 'video'

    # Foreign key to link blog post to a user
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    def __repr__(self):
        return f"UserBlog('{self.title}', '{self.date_posted}', '{self.user_id}')"

# 



class Vote(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    position = db.Column(db.String(100), nullable=False)
    candidate_id = db.Column(db.Integer, nullable=True)  # can be null for 'NO' votes
    decision = db.Column(db.String(10))  # 'yes', 'no' or 'selected'

    user = db.relationship('User', backref='votes')

class Admin(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    fullname = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    def __repr__(self):
        return f"Admin('{self.username}', '{self.email}')"


# Your existing Course and StudentResult models go here
class Course(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    course_code = db.Column(db.String(20), unique=True, nullable=False)
    course_title = db.Column(db.String(255), nullable=False)
    session_written = db.Column(db.String(50), nullable=False) # This is the missing column
    year = db.Column(db.String(50), nullable=False)
    semester = db.Column(db.String(50), nullable=False)

    results = db.relationship('StudentResult', backref='course', lazy=True, cascade="all, delete-orphan")

    def __repr__(self):
        return f"Course('{self.course_code}', '{self.course_title}')"

class StudentResult(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=False)
    student_name = db.Column(db.String(255), nullable=False)
    reg_number = db.Column(db.String(50), nullable=False)
    ca_score = db.Column(db.Integer, nullable=False)
    exam_score = db.Column(db.Integer, nullable=False)
    total_score = db.Column(db.Integer, nullable=False)
    grade = db.Column(db.String(5), nullable=False)

    __table_args__ = (db.UniqueConstraint('course_id', 'reg_number', name='_course_reg_number_uc'),)

    def __repr__(self):
        return f"StudentResult(RegNo: {self.reg_number}, Course: {self.course.course_code if self.course else 'N/A'}, Total: {self.total_score}, Grade: {self.grade})"

def calculate_grade(total_score):
    if total_score >= 70:
        return 'A'
    elif total_score >= 60:
        return 'B'
    elif total_score >= 50:
        return 'C'
    elif total_score >= 45:
        return 'D'
    elif total_score >= 40:
        return 'E'
    else:
        return 'F'

def parse_bulk_input(input_string):
    return [item.strip() for item in re.split(r'[\n,]+', input_string) if item.strip()]



# The model you provided
class ResultPublicationSchedule(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=False)
    session_written = db.Column(db.String(50), nullable=False)
    publish_start = db.Column(db.DateTime, nullable=False)
    publish_end = db.Column(db.DateTime, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    admin_id = db.Column(db.Integer, db.ForeignKey('admin.id'), nullable=True)

    course = db.relationship('Course', backref='scheduled_publications')
    admin = db.relationship('Admin', backref='scheduled_publications')

    def __repr__(self):
        return f"ResultPublicationSchedule(Course: {self.course.course_code if self.course else 'N/A'}, Session: {self.session_written}, Start: {self.publish_start}, End: {self.publish_end})"

class AdminAddDues(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    fullname = db.Column(db.String(100), nullable=False)
    regno = db.Column(db.String(100), nullable=False)
    admin_id = db.Column(db.Integer, db.ForeignKey('admin.id'), nullable=False)
    sessions_paid = db.Column(db.String(255), nullable=False)
    date_filled = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, nullable=False)

class FriendRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    receiver_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    status = db.Column(db.String(20), default='pending')  # <--- ADD THIS LINE
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    receiver_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    sender = db.relationship('User', foreign_keys=[sender_id], backref='sent_requests')
    receiver = db.relationship('User', foreign_keys=[receiver_id], backref='received_requests')

class Friendship(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user1_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    user2_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
class Community(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)  # Change 'community_name' to 'name'
    description = db.Column(db.Text, nullable=False)
    profile_picture = db.Column(db.String(150), nullable=False)
    admin_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    admin = db.relationship('User', backref='communities')




class Lecturer(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    department = db.Column(db.String(100), nullable=False)
    staff_id = db.Column(db.String(50), unique=True, nullable=False)
    phone_number = db.Column(db.String(20))
    profile_picture = db.Column(db.String(200))
    state_of_origin = db.Column(db.String(50))
    lga = db.Column(db.String(50))
    home_address = db.Column(db.Text)

    def __repr__(self):
        return f'<Lecturer {self.full_name} ({self.staff_id})>'

    # --- Flask-Login required properties/methods ---
    @property
    def is_authenticated(self):
        return True

    @property
    def is_active(self): # <--- THIS IS THE ONE FLASK-LOGIN IS LOOKING FOR
        return True

    @property
    def is_anonymous(self):
        return False

    def get_id(self):
        return str(self.id)



# If you don't have this, consider adding it for better tag management
class Tag(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)

    def __repr__(self):
        return f"Tag('{self.name}')"
class AdminActivityLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('admin.id'), nullable=False)
    action = db.Column(db.String(255), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    admin = db.relationship('Admin', backref='activities', lazy=True)

@app.route('/get_user_profile/<int:user_id>') # Or @users_bp.route(...)
def get_user_profile(user_id):
    user = User.query.get(user_id)
    if user:
        user_data = {
            'fullname': user.fullname,
            'email': user.email,
            'regno': user.regno,
            'phone': user.phone,
            'profile_picture_url': url_for('static', filename=user.profile_picture_url)
        }
        return jsonify(user_data)
    else:
        return jsonify({'error': 'User not found'}), 404

@login_manager.user_loader
def load_user(user_id):
    user = User.query.get(int(user_id))
    print(f"load_user called for user_id: {user_id}, returning: {user}")
    return user
# -----------------
#home
@app.route('/', methods=['GET', 'POST'])
def index():
        return render_template('index.html',)

@app.route('/helpcontact')
def helpcontact():
    if 'user_id' not in session:
        flash('Please log in first.', 'danger')
        return redirect(url_for('login'))
    # You might want to add authentication/session checks here too,
    # depending on whether this page should be publicly accessible or not.
    # For now, it's public.
    return render_template('helpcontact.html')


# -------------------------------------------------------------------
# 2. Signup Route
# -------------------------------------------------------------------
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        fullname = request.form['signupName']
        email = request.form['signupEmail']
        regno = request.form['regno']
        phone = request.form['phone']
        password = request.form['signupPassword']
        confirm = request.form['confirmpassword']

        if password != confirm:
            flash('Passwords do not match.', 'danger')
            return redirect(url_for('signup'))

        # Initialize variable to prevent UnboundLocalError on database failure
        existing_user = None 
        
        # Check for existing email or reg number
        try:
            existing_user = User.query.filter((User.email == email) | (User.regno == regno)).first()
        except Exception as e:
            # This is where the error jumps if the 'user' table is missing!
            print(f"Database Error during signup query: {e}")
            flash('A server error occurred during registration. Please try again.', 'danger')
            return redirect(url_for('signup'))
            
        if existing_user:
            flash('Email or Registration Number already exists, please log in', 'danger')
            return redirect(url_for('login'))

        # Create new user
        hashed_password = generate_password_hash(password)
        new_user = User(fullname=fullname, email=email, regno=regno, phone=phone, password=hashed_password)
        
        # Save new user to database
        try:
            db.session.add(new_user)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            print(f"Database Error during user save: {e}")
            flash('Failed to create account due to a database error.', 'danger')
            return redirect(url_for('signup'))

        # Send Welcome Email (commented out)
        # send_welcome_email(email, fullname)

        flash('Account created successfully! Please log in.', 'success')
        return redirect(url_for('login'))

    # Placeholder for a missing template if not using render_template
    # return "Signup Form Here" 
    return render_template('signup.html')


# -------------------------------------------------------------------
# 3. Login Route
# -------------------------------------------------------------------
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['loginEmail']
        password = request.form['loginPassword']
        
        # Initialize user to None to prevent UnboundLocalError on database failure
        user = None 
        
        try:
            # Query the database for the user
            user = User.query.filter_by(email=email).first()
        except Exception as e:
            # This is where the error jumps if the 'user' table is missing!
            print(f"Database Error during login query: {e}") 
            flash('A database error occurred during login. Please try again.', 'danger')
            return redirect(url_for('login'))

        # Check if user exists and password is correct
        if user and check_password_hash(user.password, password):
            session['user_id'] = user.id
            flash('Login successful!', 'success')
            # Assuming 'dashboard' route exists
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid credentials.', 'danger')
            return redirect(url_for('login'))

    # Placeholder for a missing template if not using render_template
    # return "Login Form Here"
    return render_template('login.html')
# -----------------
# Welcome Email Function
# -----------------
# def send_welcome_email(to_email, fullname):
#     msg = EmailMessage()
#     msg['Subject'] = 'Welcome to Department Of Public Administration, University Of Nigeria, Nsukka Platform!'
#     msg['From'] = 'yourgmail@gmail.com'
#     msg['To'] = to_email
#     msg.set_content(f"Dear {fullname},\n\nWelcome! Your account has been created successfully.\n\nThank you!")

#     # Replace with your actual Gmail credentials
#     gmail_user = 'yourgmail@gmail.com'
#     gmail_password = 'your_app_password'  # App Password if 2FA is enabled

#     try:
#         with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
#             smtp.login(gmail_user, gmail_password)
#             smtp.send_message(msg)
#     except Exception as e:
#         print("Email failed:", e)

@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully.', 'info')
    return redirect(url_for('login'))

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        flash('Please log in first.', 'danger')
        return redirect(url_for('login'))
    flash('Welcome To Your Dashboard.', 'success')
    user = User.query.get(session['user_id'])


    return render_template('dashboard.html', user=user)

@app.route('/settings')
def settings():
    if 'user_id' not in session:
        flash('Please log in to access settings.', 'danger')
        return redirect(url_for('login'))
    
    user = User.query.get(session['user_id'])
    return render_template('settings.html', user=user)

@app.route('/friendrequest', methods=['GET', 'POST'])
def friendrequest():
    if 'user_id' not in session:
        flash('Please log in to access settings.', 'danger')
        return redirect(url_for('login'))

    user = User.query.get(session['user_id'])

    if request.method == 'POST':
        action = request.form.get('action')
        receiver_id = request.form.get('receiver_id')

        if action == 'send':
            # Check if request already exists
            try:
                existing_request = FriendRequest.query.filter_by(sender_id=user.id, receiver_id=receiver_id).first()
            except Exception as e:
                        print(e)
            if not existing_request:
                new_request = FriendRequest(sender_id=user.id, receiver_id=receiver_id, status='pending')
                db.session.add(new_request)
                db.session.commit()
                flash('Friend request sent successfully!', 'success')
        elif action == 'cancel':
            try:
                existing_request = FriendRequest.query.filter_by(sender_id=user.id, receiver_id=receiver_id).first()
            except Exception as e:
                        print(e)
            if existing_request:
                db.session.delete(existing_request)
                db.session.commit()
                flash('Friend request canceled.', 'info')

        return redirect(url_for('friendrequest'))

    # Get all users except current user
    all_users = User.query.filter(User.id != user.id).all()

    # IDs of users I already sent friend request to (pending)
    sent_requests = FriendRequest.query.filter_by(sender_id=user.id, status='pending').all()
    sent_request_ids = [req.receiver_id for req in sent_requests]

    # IDs of users I am already friends with (both accepted)
    my_friends = Friendship.query.filter(
        (Friendship.user1_id == user.id) | (Friendship.user2_id == user.id)
    ).all()
    friends_ids = []
    for f in my_friends:
        if f.user1_id == user.id:
            friends_ids.append(f.user2_id)
        else:
            friends_ids.append(f.user1_id)

    return render_template('friendrequest.html', 
                           user=user, 
                           all_users=all_users, 
                           sent_request_ids=sent_request_ids, 
                           friends_ids=friends_ids)

@app.route('/community', methods=['GET', 'POST'])

@app.route('/view_friends')
def view_friends():
    user_id = session.get('user_id')
    
    # Fetch accepted friends for the user
    friendships = Friendship.query.filter(
        (Friendship.user1_id == user_id) | (Friendship.user2_id == user_id)
    ).all()
    
    friends = []
    for friendship in friendships:
        if friendship.user1_id == user_id:
            friend = User.query.get(friendship.user2_id)
        else:
            friend = User.query.get(friendship.user1_id)
        if friend:
            friends.append(friend)
    communities = Community.query.all()

    return render_template('view_friends.html', friends=friends,communitties=communities)

# Allowed file extensions
ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png'}

# Function to check allowed file extensions
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# @app.route('/create_community', methods=['GET', 'POST'])
# def create_community():
#     if request.method == 'POST':
#         community_name = request.form['community_name']
#         description = request.form['description']
#         profile_picture = request.files['profile_picture']  # this is a FileStorage object

#         if profile_picture:
#             filename = secure_filename(profile_picture.filename)
#             filepath = os.path.join('static/uploads', filename)  # choose your upload folder
#             profile_picture.save(filepath)  # save the file

#             # Now save only the filename (or filepath) to the database
#             new_community = Community(
#                 name=community_name,
#                 description=description,
#                 profile_picture=filename,  # or 'filepath' if you want full path
#                 admin_id=session['user_id'],
#                 created_at=datetime.now()
#             )
#             db.session.add(new_community)
#             db.session.commit()

#             flash('Community created successfully!', 'success')
#             return redirect(url_for('community_page'))

#     return render_template('createcommunity.html')

# @app.route('/community.html')
# def community_page():
#     communities = Community.query.all()
#     return render_template('communities.html', communities=communities)


@app.route('/report-issue', methods=['GET', 'POST'])
def report_issue():
    if 'user_id' not in session:
        flash('Please log in to access chat.', 'danger')
        return redirect(url_for('login'))

    if request.method == 'POST':
        issue_type = request.form.get('issue_type')
        other_issue = request.form.get('other_issue', '').strip()
        description = request.form.get('description', '').strip()

        if not issue_type:
            flash("Please select an issue type.", "danger")
            return redirect(url_for('report_issue'))

        if not description:
            flash("Please describe the issue.", "danger")
            return redirect(url_for('report_issue'))

        if issue_type == 'other' and not other_issue:
            flash("Please specify your issue in the 'Other' field.", "danger")
            return redirect(url_for('report_issue'))

        try:
            new_help = Help(
                user_id=session['user_id'],
                issue_type=issue_type,
                other_issue=other_issue if issue_type == 'other' else None,
                description=description,
                timestamp=datetime.utcnow()
            )

            db.session.add(new_help)
            db.session.commit()
            flash("Your issue has been reported successfully!", "success")
            return redirect(url_for('dashboard'))

        except Exception as e:
            db.session.rollback()
            flash(f'An error occurred while reporting your issue: {e}', 'danger')
            return redirect(url_for('report_issue'))

    # For GET request
    return render_template('help.html', user=current_user)





def log_activity(user_id, action):
    activity = UserActivity(
        user_id=user_id,
        action=action,
        ip_address=request.remote_addr,
        user_agent=request.headers.get('User-Agent')
    )
    db.session.add(activity)
    db.session.commit()



@app.route('/activity-log')
def activity_log():
    if 'user_id' not in session:
        flash('Please log in to access chat.', 'danger')
        return redirect(url_for('login'))

    # Log activity for viewing activity log
    log_activity(current_user.id, 'Viewed Activity Log')
    activities = UserActivity.query.filter_by(user_id=current_user.id).order_by(UserActivity.timestamp.desc()).all()
    return render_template('activity_log.html', activities=activities)





@app.route('/contact', methods=['GET', 'POST'])
def contact():
    if 'user_id' not in session:
        flash('Please log in to access chat.', 'danger')
        return redirect(url_for('login'))

    if request.method == 'POST':
        # ONLY retrieve form data if the request method is POST
        fullname = request.form.get('fullname')
        email = request.form.get('email')
        subject = request.form.get('subject')
        message = request.form.get('message')

        # Server-side validation
        if not fullname or not email or not subject or not message:
            flash('All fields are required!', 'danger')
            # Important: For a GET request, these variables (fullname, email, etc.) would not exist,
            # so they must be defined ONLY within the POST block.
            return redirect(url_for('contact'))

        # Basic email format validation
        if '@' not in email or '.' not in email:
            flash('Please enter a valid email address.', 'danger')
            return redirect(url_for('contact'))

        try:
            # Create a new Contact instance
            new_contact = Contact(
                username=fullname, # Use 'fullname' here as per your form field name
                email=email,
                subject=subject,
                message=message
            )
            
            db.session.add(new_contact)
            db.session.commit()
            flash('Your message has been sent successfully!', 'success')
            return redirect(url_for('contact'))
        except Exception as e:
            db.session.rollback()
            flash(f'An error occurred while sending your message: {e}', 'danger')
            return redirect(url_for('contact'))
    else: # This block handles GET requests
        # No need to get form data here, as it's not submitted yet.
        # The template will use current_user to pre-populate.
        pass
    
    return render_template('contact.html')











# @app.route('/chatwithfriends')
# def privatechat():
#     if 'user_id' not in session:
#         flash('Please log in to access chat.', 'danger')
#         return redirect(url_for('login'))

#     user = User.query.get(session['user_id'])
#     friend_id = request.args.get('friend_id')

#     if not friend_id:
#         flash('No friend selected to chat with.', 'warning')
#         return redirect(url_for('friendrequest')) # Redirect to friends list or similar

#     friend = User.query.get(friend_id)

#     if not friend:
#         flash('Friend not found.', 'danger')
#         return redirect(url_for('friendrequest')) # Redirect if friend doesn't exist

#     # Fetch existing messages for this chat (optional, but good for persistence)
#     # This example assumes a Message model with sender_id, recipient_id, encrypted_content
#     # You might need to adjust this based on your actual Message model structure
#     messages = Message.query.filter(
#         ((Message.sender_id == user.id) & (Message.recipient_id == friend.id)) |
#         ((Message.sender_id == friend.id) & (Message.recipient_id == user.id))
#     ).order_by(Message.timestamp.asc()).all()

#     # Pass all necessary data to the template
#     return render_template('chat.html',
#                            user=user,
#                            friend=friend, # Pass the entire friend object
#                            messages=messages,
#                            current_user_public_key=user.public_key, # Assuming public_key is stored in User model
#                            friend_public_key=friend.public_key) # Assuming public_key is stored in User model

# --- SocketIO Events ---

# def handle_connect():
#     user_id = session.get('user_id')
#     if user_id:
#         join_room(str(user_id))
#         print(f"User {user_id} connected via SocketIO.")
#     else:
#         print("Unauthenticated user tried to connect to SocketIO.")
#         return False

# def handle_disconnect():
#     user_id = session.get('user_id')
#     if user_id:
#         leave_room(str(user_id))
#         print(f"User {user_id} disconnected.")

# def handle_send_encrypted_message(data):
#     sender_id = session.get('user_id')
#     recipient_id = data.get('recipient_id')
#     encrypted_message = data.get('encrypted_message') # This is the object: {ciphertext, nonce}

#     if not sender_id or not recipient_id or not encrypted_message:
#         print("Invalid encrypted message data received.")
#         return

#     # **Store the encrypted message in the database**
#     # Store the encrypted_message object as a JSON string
#     new_message = PrivateChat(
#         sender_id=sender_id,
#         recipient_id=recipient_id,
#         encrypted_content=json.dumps(encrypted_message) # Convert dict to JSON string
#     )
#     db.session.add(new_message)
#     db.session.commit()
#     print(f"Stored encrypted message from {sender_id} to {recipient_id} in DB.")

#     # Relay the encrypted message to the recipient's room
#     # The server does NOT decrypt the message here.
#     emit('receive_encrypted_message', {
#         'sender_id': sender_id,
#         'encrypted_message': encrypted_message
#     }, room=str(recipient_id))
#     print(f"Relayed encrypted message from {sender_id} to {recipient_id}")

# def handle_request_public_key(data):
#     requester_id = session.get('user_id')
#     target_user_id = data.get('target_user_id')

#     if not requester_id or not target_user_id:
#         print("Invalid public key request.")
#         return

#     target_user = User.query.get(target_user_id)
#     if target_user and target_user.public_key:
#         emit('receive_public_key', {
#             'user_id': target_user_id,
#             'public_key': target_user.public_key
#         }, room=str(requester_id))
#         print(f"Sent public key of {target_user_id} to {requester_id}")
#     else:
#         print(f"Public key for user {target_user_id} not found or not generated yet.")
#         emit('public_key_not_found', {'user_id': target_user_id}, room=str(requester_id))



# @app.route('/block-user', methods=['POST'])
# def block_user():
#     user_id = request.json['userId']
#     # Code to block the user goes here
#     return jsonify({'success': True})

# @app.route('/unblock-user', methods=['POST'])
# def unblock_user():
#     user_id = request.json['userId']
#     # Code to unblock the user goes here
#     return jsonify({'success': True})


@app.route('/payments', methods=['GET', 'POST'])
def payments():
    if 'user_id' not in session:
        flash('Please log in to access settings.', 'danger')
        return redirect(url_for('login'))
    
    user = User.query.get(session['user_id'])
    return render_template('payment.html', user=user)



@app.route('/messages')
def messages():
    if 'user_id' not in session:
        flash('Please log in to view messages.', 'danger')
        return redirect(url_for('login'))

    user = User.query.get(session['user_id'])

    # Get friend requests sent to this user (pending)
    incoming_requests = FriendRequest.query.filter_by(receiver_id=user.id, status='pending').all()

    return render_template('messages.html', user=user, incoming_requests=incoming_requests)

# @app.route('/accept_friend_request/<int:request_id>', methods=['POST'])
# def accept_friend_request(request_id):
#     """Accept an incoming friend request."""
#     friend_request = FriendRequest.query.get_or_404(request_id)

#     # Use session to get the user ID instead of current_user
#     user_id = session.get('user_id')

#     if user_id and friend_request.receiver_id == user_id:
#         # Create a new friendship
#         new_friendship = Friendship(
#             user1_id=friend_request.sender_id,
#             user2_id=friend_request.receiver_id
#         )
#         db.session.add(new_friendship)

#         # Update the friend request status
#         friend_request.status = 'accepted'
#         db.session.commit()

#         flash('Friend request accepted!', 'success')
#     else:
#         flash('You cannot accept this request.', 'danger')

#     return redirect(url_for('messages'))

# @app.route('/decline_friend_request/<int:request_id>', methods=['POST'])
# def decline_friend_request(request_id):
#     """Decline an incoming friend request."""
#     friend_request = FriendRequest.query.get_or_404(request_id)

#     # Use session to get the user ID instead of current_user
#     user_id = session.get('user_id')

#     if user_id and friend_request.receiver_id == user_id:
#         # Update the friend request status to declined
#         friend_request.status = 'declined'
#         db.session.commit()

#         flash('Friend request declined.', 'info')
#     else:
#         flash('You cannot decline this request.', 'danger')

#     return redirect(url_for('messages'))





# --- Helper function for email validation ---
def is_valid_email(email):
    return re.match(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", email)


# --- Project Upload Route ---
@app.route("/upload", methods=['GET', 'POST'])
def upload_project():
    if 'user_id' not in session:
        flash('Please log in to upload a project.', 'danger')
        return redirect(url_for('login'))

    errors = {}
    form_data = {
        'projectTitle': '',
        'projectDescription': '',
        'keyInnovations': '',
        'contactEmail': '',
        'visibility': 'public'  # Default to public for initial GET request or repopulation
    }

    if request.method == 'POST':
        project_title = request.form.get('projectTitle', '').strip()
        project_description = request.form.get('projectDescription', '').strip()
        key_innovations = request.form.get('keyInnovations', '').strip()
        contact_email = request.form.get('contactEmail', '').strip()
        # --- NEW: Get visibility from form ---
        visibility = request.form.get('visibility', 'public') # Default to 'public' if not found

        # Repopulate form_data with submitted values
        form_data['projectTitle'] = project_title
        form_data['projectDescription'] = project_description
        form_data['keyInnovations'] = key_innovations
        form_data['contactEmail'] = contact_email
        form_data['visibility'] = visibility # --- NEW: Repopulate visibility ---

        # --- Validation ---
        if not project_title:
            errors['projectTitle'] = 'Project Title is required.'
        elif not (5 <= len(project_title) <= 200):
            errors['projectTitle'] = 'Project Title must be between 5 and 200 characters.'

        if not project_description:
            errors['projectDescription'] = 'Brief Description is required.'
        elif len(project_description) < 20:
            errors['projectDescription'] = 'Brief Description must be at least 20 characters.'
        elif len(project_description) > 1000:
            errors['projectDescription'] = 'Brief Description cannot exceed 1000 characters.'

        if key_innovations and len(key_innovations) > 2000:
            errors['keyInnovations'] = 'Key Innovations cannot exceed 2000 characters.'

        if not contact_email:
            errors['contactEmail'] = 'Your Contact Email is required.'
        elif not is_valid_email(contact_email): # Assuming is_valid_email is defined elsewhere
            errors['contactEmail'] = 'Invalid email format.'
        
        # --- File Upload Validation and Handling ---
        uploaded_file_paths = []
        max_file_size_bytes = 5 * 1024 * 1024 # 5 MB per file
        
        files = request.files.getlist('supportingFiles')

        # Check if any files were actually selected
        has_files_selected = any(f.filename != '' for f in files)

        if has_files_selected:
            for file_storage in files:
                if file_storage and file_storage.filename != '':
                    # Validate file type using Flask-Uploads
                    # Assuming projects_uploads and app.config["UPLOADED_PROJECTS_ALLOW"] are configured
                    if not projects_uploads.file_allowed(file_storage, file_storage.filename):
                        errors['supportingFiles'] = f'File "{file_storage.filename}" is not an allowed type. Accepted: {", ".join(app.config["UPLOADED_PROJECTS_ALLOW"])}'
                        break
                    
                    # Validate file size
                    file_storage.seek(0, os.SEEK_END)
                    file_size = file_storage.tell()
                    file_storage.seek(0)
                    
                    if file_size > max_file_size_bytes:
                        errors['supportingFiles'] = f'File "{file_storage.filename}" exceeds the {max_file_size_bytes / (1024 * 1024):.0f}MB limit.'
                        break
                    
                    # If file is valid, save it
                    try:
                        filename = projects_uploads.save(file_storage)
                        uploaded_file_paths.append(filename)
                    except Exception as e:
                        errors['supportingFiles'] = f'Could not save file "{file_storage.filename}": {e}'
                        break
        
        # If there are no errors, process the submission
        if not errors:
            # Get the current user's ID from the session
            current_user_id = session.get('user_id')
            
            new_project_idea = ProjectIdea(
                title=project_title,
                description=project_description,
                innovations=key_innovations,
                file_paths=','.join(uploaded_file_paths) if uploaded_file_paths else None,
                contact_email=contact_email,
                user_id=current_user_id,
                visibility=visibility  # --- NEW: Save visibility ---
            )
            db.session.add(new_project_idea)
            db.session.commit()
            flash('Your project idea has been submitted successfully!', 'success')
            return redirect(url_for('dashboard')) # Redirect to a confirmation page or dashboard
        else:
            flash('Please correct the errors in the form.', 'danger')

    # For GET requests or if there are errors on POST
    return render_template('upload.html', errors=errors, form_data=form_data)





# NEW ROUTE: Tag & Search Projects
@app.route('/browse_projects')
def browse_projects():
    if 'user_id' not in session:
        flash("Please log in to access the voting page.", "danger")
        return redirect(url_for('login'))

    user = User.query.get(session['user_id'])
    if not user:
        flash("User not found.", "danger")
        return redirect(url_for('login'))
    try:
        dues_record = AdminAddDues.query.filter_by(regno=user.regno).first()
    except Exception as e:
                print(e)
    if not dues_record:
        flash("You are not eligible to search any project. Please ensure your dues are cleared or contact the excos.", "warning")
        return redirect(url_for('dashboard'))

    # Initialize query with all projects
    query = ProjectIdea.query.order_by(ProjectIdea.submission_date.desc())

    search_query = request.args.get('search_query', '').strip()
    search_type = request.args.get('search_type', 'all').strip()
    selected_tag_name = request.args.get('tag', '').strip() # For tag filtering

    if search_query:
        if search_type == 'title':
            query = query.filter(ProjectIdea.title.ilike(f'%{search_query}%'))
        elif search_type == 'description':
            query = query.filter(ProjectIdea.description.ilike(f'%{search_query}%'))
        elif search_type == 'innovations':
            query = query.filter(ProjectIdea.innovations.ilike(f'%{search_query}%'))
        elif search_type == 'author':
            # This assumes 'author' (User model) has a 'fullname' or 'regno' field
            query = query.join(User).filter(
                (User.fullname.ilike(f'%{search_query}%')) |
                (User.regno.ilike(f'%{search_query}%'))
            )
        elif search_type == 'year':
            # Assuming submission_date is a DateTime object
            try:
                search_year = int(search_query)
                query = query.filter(func.strftime('%Y', ProjectIdea.submission_date) == str(search_year))
            except ValueError:
                flash('Invalid year format for search.', 'danger')
                search_query = '' # Clear invalid query
        else: # 'all' or no specific type
            query = query.filter(
                (ProjectIdea.title.ilike(f'%{search_query}%')) |
                (ProjectIdea.description.ilike(f'%{search_query}%')) |
                (ProjectIdea.innovations.ilike(f'%{search_query}%')) |
                (ProjectIdea.contact_email.ilike(f'%{search_query}%')) |
                # Add author search to 'all' if user model is joined
                (ProjectIdea.author.has(
                    (User.fullname.ilike(f'%{search_query}%')) |
                    (User.regno.ilike(f'%{search_query}%'))
                ))
            )
            # If using actual tags relationship, add tag search here for 'all'
            # query = query.filter(ProjectIdea.tags.any(Tag.name.ilike(f'%{search_query}%')))


    # Filter by specific tag if selected
    if selected_tag_name:
        # If using Tag model and relationship:
        # query = query.join(ProjectIdea.tags).filter(Tag.name == selected_tag_name)

        # If tags are comma-separated in ProjectIdea.file_paths (bad practice, but handles existing data)
        # This is a very inefficient way to search tags, reconsider your model
        # query = query.filter(ProjectIdea.file_paths.ilike(f'%{selected_tag_name}%'))
        pass # Handle tags based on your actual model setup

    project_ideas = query.all()

    # Get all unique tags for the tag cloud/filter (if you have a Tag model)
    # If using ProjectIdea.tags relationship:
    all_tags = Tag.query.order_by(Tag.name).all()
    # If not using a Tag model, you'd need to parse tags from ProjectIdea.file_paths
    # or a dedicated 'tags' column, which would be more complex and less efficient.

    return render_template(
        'search_projects.html',
        project_ideas=project_ideas,
        search_query=search_query,
        search_type=search_type,
        all_tags=all_tags,
        selected_tag_name=selected_tag_name
    )





@app.route('/view_projects')
def view_projects():
    if 'user_id' not in session:
        flash('Please log in to upload a project.', 'danger')
        return redirect(url_for('login'))

    # Fetch all project ideas from the database, ordered by submission date (newest first)
    project_ideas = ProjectIdea.query.order_by(ProjectIdea.submission_date.desc()).all()
    return render_template('view_projects.html', project_ideas=project_ideas)


# Route for displaying a single project's details
@app.route("/view_project_details/<int:project_id>")
def view_project_details(project_id):
    project = ProjectIdea.query.get_or_404(project_id)

    # If project is private and current user is not the owner, abort with 403 Forbidden
    if project.visibility == 'private' and project.user_id != session.get('user_id'):
        abort(403, description="You do not have permission to view this private project.")

    # Render a detailed project view template
    return render_template('project_details.html', project=project)

@app.route("/edit_project/<int:project_id>")
def edit_project(project_id):
    if 'user_id' not in session:
        flash('Please log in to edit projects.', 'danger')
        return redirect(url_for('login'))
    project = ProjectIdea.query.get_or_404(project_id)
    if project.user_id != session['user_id']:
        flash('You are not authorized to edit this project.', 'danger')
        return redirect(url_for('my_projects'))
    return f"<h1>Edit Project: {project.title}</h1><p>This would be the project editing form.</p>"

@app.route("/delete_project/<int:project_id>")
def delete_project(project_id):
    if 'user_id' not in session:
        flash('Please log in to delete projects.', 'danger')
        return redirect(url_for('login'))
    project = ProjectIdea.query.get_or_404(project_id)
    if project.user_id != session['user_id']:
        flash('You are not authorized to delete this project.', 'danger')
        return redirect(url_for('my_projects'))
    
    db.session.delete(project)
    db.session.commit()
    flash(f'Project "{project.title}" deleted successfully!', 'success')
    return redirect(url_for('my_projects'))

# If this page lists ALL forked/collaborated work for the user
@app.route("/fork_collaborate_page")
def fork_collaborate_page():
    if 'user_id' not in session:
        flash('Please log in to view your forked/collaborated projects.', 'danger')
        return redirect(url_for('login'))

    current_user_id = session['user_id']
    # Fetch projects where the user is the owner, and perhaps also filter for those that were forked
    # (You might need a new column in ProjectIdea, like `original_project_id` if you want to track forks specifically)
    forked_projects = ProjectIdea.query.filter_by(user_id=current_user_id).order_by(ProjectIdea.submission_date.desc()).all()
    # Or, if you want a page specifically for FORKS, you need a way to differentiate them.
    # For now, let's just assume it lists *all* projects of the user if you don't have a 'forked' flag.
    # If you have a column like 'is_forked_from_id', you'd filter by that.

    return render_template('fork.html', project_ideas=forked_projects) # Assuming fork.html iterates over project_ideas



# Route to render the rating page
@app.route('/users/rate-us')
def rating_page():
    return render_template('rating.html')

# Route to handle the rating submission
@app.route('/submit_rating', methods=['POST'])
def submit_rating():
    if request.method == 'POST':
        data = request.get_json()

        rating_value = data.get('rating')
        comment_text = data.get('comment', '').strip() # Get comment, default to empty string if not provided

        # Server-side validation
        if not rating_value:
            return jsonify({'message': 'Please select a star rating.'}), 400

        try:
            rating_value = int(rating_value)
            if not (1 <= rating_value <= 5):
                return jsonify({'message': 'Rating must be between 1 and 5.'}), 400
        except ValueError:
            return jsonify({'message': 'Invalid rating value.'}), 400

        if len(comment_text) > 500:
            return jsonify({'message': 'Comment cannot exceed 500 characters.'}), 400

        # In a real application, you would get the actual user_id from the session or authentication system
        # For demonstration purposes, let's assume a user with ID 1 exists.
        # You'd typically have a @login_required decorator here.
        user_id = 1 # Replace with actual logged-in user's ID

        # Basic check to ensure the user exists (optional, but good practice)
        user = User.query.get(user_id)
        if not user:
            return jsonify({'message': 'User not found.'}), 404

        try:
            new_rating = Rating(user_id=user_id, rating=rating_value, comment=comment_text)
            db.session.add(new_rating)
            db.session.commit()
            return jsonify({'message': 'Rating submitted successfully!'}), 200
        except Exception as e:
            db.session.rollback()
            print(f"Error submitting rating: {e}")
            return jsonify({'message': 'An error occurred while saving your rating.'}), 500



@app.route('/admin/ratings')
def admin_ratings():
    # You need to have app.secret_key set for sessions to work
    # For example, in your app setup:
    # app.config['SECRET_KEY'] = 'your_super_secret_key_here'
    # Use a strong, random key in production!

    if 'admin_id' not in session:
        flash('Please login first!', 'warning')
        return redirect(url_for('admin_login')) # Make sure 'admin_login' route exists

    # In a real application, you'd add a more robust authentication/authorization check here
    # e.g., if not current_user.is_admin: abort(403)

    ratings = Rating.query.order_by(Rating.timestamp.desc()).all()
    return render_template('admin_ratings.html', ratings=ratings)






@app.route("/blogs")
def get_all_blogs():
    # 1. Check if user is logged in
    if 'user_id' not in session:
        flash('Please log in to create a blog post.', 'danger')
        return redirect(url_for('login')) # Assuming 'login' is the route name for your login page

   
    blogs = UserBlog.query.order_by(UserBlog.date_posted.desc()).all()
    return render_template('blognews1.html', blogs=blogs)




@app.route('/create_blog_post_page')
def create_blog_post_page():
    # 1. Check if user is logged in
    if 'user_id' not in session:
        flash('Please log in to create a blog post.', 'danger')
        return redirect(url_for('login')) # Assuming 'login' is the route name for your login page

    # 2. Get user ID from session
    user_id = session['user_id']

    # 3. Fetch user details from the database
    user = User.query.get(user_id) # Use .get() for primary key lookups, it's efficient

    # 4. Handle case where user ID in session doesn't correspond to an existing user
    if not user:
        # This could happen if a user was deleted from the DB but their session persists
        flash('User not found. Please log in again.', 'danger')
        session.pop('user_id', None) # Clear invalid user_id from session
        return redirect(url_for('login'))

    # 5. Extract the full name
    fullname = user.fullname

    # 6. Render the template with the user's full name
    return render_template('blog.html', fullname=fullname)




@app.route('/create_blog_post', methods=['POST'])
def create_blog_post():
    if 'user_id' not in session:
        flash('Please log in to view your forked/collaborated projects.', 'danger')
        return redirect(url_for('login'))

   
    # --- 1. Basic Form Validation ---
    title = request.form.get('title')
    author_name = request.form.get('author_name')
    content = request.form.get('content')
    media_file = request.files.get('media_file')

    if not all([title, author_name, content]):
        # Flash messages are good for showing status to the user after a redirect
        flash('Please fill in all required fields: Title, Your Name, and Blog Content.', 'error')
        return redirect(url_for('create_blog_post_page', status='error', message='Please fill in all required fields!'))

    # --- 2. Determine User ID ---
    # IMPORTANT: In a real application, you would get the user_id from the
    # currently authenticated user's session (e.g., using Flask-Login: current_user.id).
    # For this demonstration, let's assume a user exists.
    # We will try to find a user by their full name, or create a dummy one if not found.
    try:
        user = User.query.filter_by(fullname=author_name).first()
    except Exception as e:
                print(e)
    if not user:
        # If user not found, create a dummy user for the purpose of saving the blog.
        # In a real app, users would register and log in.
        print(f"User '{author_name}' not found, creating a dummy user.")
        # Create dummy user details (you might prompt for these or have a registration flow)
        dummy_email = f"{author_name.lower().replace(' ', '_')}@example.com"
        dummy_regno = f"REG_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        dummy_phone = "000-000-0000"
        dummy_password = "hashed_password" # In a real app, this would be hashed

        user = User(fullname=author_name, email=dummy_email, regno=dummy_regno, phone=dummy_phone, password=dummy_password)
        db.session.add(user)
        db.session.commit() # Commit to get an ID for the new user
        print(f"Dummy user '{user.fullname}' created with ID: {user.id}")

    author_id = user.id # Get the ID of the found/created user

    # --- 3. Handle Media Upload ---
    media_path = None
    media_type = None

    if media_file and allowed_file(media_file.filename):
        filename = secure_filename(media_file.filename)
        unique_filename = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{filename}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
        try:
            media_file.save(filepath)
            media_path = url_for('static', filename=f'uploads/{unique_filename}')
            media_type = media_file.mimetype.split('/')[0] # 'image' or 'video'
            flash('Media uploaded successfully!', 'info')
        except Exception as e:
            print(f"Error saving file: {e}")
            flash('Error uploading media. Please try again.', 'error')
            return redirect(url_for('create_blog_post_page', status='error', message='Error uploading media!'))
    elif media_file and not allowed_file(media_file.filename):
        flash('Invalid file type for media upload.', 'error')
        return redirect(url_for('create_blog_post_page', status='error', message='Invalid media file type!'))


    # --- 4. Create New Blog Post Entry ---
    try:
        new_blog_post = UserBlog(
            title=title,
            content=content,
            media_path=media_path,
            media_type=media_type,
            user_id=author_id # Link to the user who posted it
        )
        db.session.add(new_blog_post)
        db.session.commit()
        flash('Your blog post has been successfully created!', 'success')
        return redirect(url_for('create_blog_post_page', status='success', message='Blog post created successfully!'))
    except Exception as e:
        db.session.rollback() # Rollback changes if an error occurs
        print(f"Error saving blog post to database: {e}")
        flash('An error occurred while creating your blog post. Please try again.', 'error')
        return redirect(url_for('create_blog_post_page', status='error', message='Failed to create blog post!'))


@app.route('/blog/<int:id>')
def blog_post_detail(id):
    if 'user_id' not in session:
        flash('Please log in to view blog posts.', 'danger') # Changed message to be more accurate
        return redirect(url_for('login')) # Assuming 'login' is the route name for your login page

    # --- FIX: Changed BlogPost to UserBlog to match your model definition ---
    blog = UserBlog.query.get_or_404(id) # Fetch the blog post by ID, or return 404
    # --- END FIX ---

    return render_template('blog_post_detail.html', blog=blog)



@app.route('/settings', methods=['GET'])
def updateprofile():
    # Manual session check as requested
    if 'user_id' not in session:
        flash('Please log in to view your settings.', 'danger')
        return redirect(url_for('login'))

    # Although 'user_id' is in session, current_user might still be AnonymousUserMixin
    # if load_user failed or user no longer exists.
    # It's safer to explicitly check if current_user is authenticated.
    if not current_user.is_authenticated:
        flash('Session invalid. Please log in again.', 'danger')
        return redirect(url_for('login'))

    return render_template('settings.html', user=current_user)

## Update User Profile

@app.route('/update_profile', methods=['POST'])
def update_profile():
    # Manual session check as requested
    if 'user_id' not in session:
        flash('Please log in to update your profile.', 'danger')
        return redirect(url_for('login'))

    # This is the crucial check: Ensure current_user is a real User object
    # and not AnonymousUserMixin after the session check.
    if not current_user.is_authenticated:
        flash('Your session is invalid. Please log in again to update your profile.', 'danger')
        return redirect(url_for('login'))

    user = current_user # Now 'user' is guaranteed to be a User object

    new_fullname = request.form.get('fullName')
    new_email = request.form.get('email')
    new_phone = request.form.get('phone')
    profile_picture_file = request.files.get('profilePicture')

    # 2. Server-side Validation
    if not new_fullname or not new_email or not new_phone:
        flash('All fields (Full Name, Email, Phone Number) are required.', 'danger')
        return redirect(url_for('updateprofile'))

    # Validate email format (basic check)
    if "@" not in new_email or "." not in new_email:
        flash('Invalid email format.', 'danger')
        return redirect(url_for('updateprofile'))

    # Check if email is already in use by another user (excluding the current user)
    try:
        existing_user_with_email = User.query.filter_by(email=new_email).first()
    except Exception as e:
                print(e)

    # Now, 'user' is guaranteed to be a User object from Flask-Login, so user.id will work
    if existing_user_with_email and existing_user_with_email.id != user.id:
        flash('That email address is already in use by another account.', 'danger')
        return redirect(url_for('updateprofile'))

    # --- Profile Update Logic ---
    user.fullname = new_fullname
    user.email = new_email
    user.phone = new_phone

    if profile_picture_file and profile_picture_file.filename != '':
        # Implement secure file saving
        # This is placeholder logic. In production, use werkzeug.utils.secure_filename
        # and save to a proper static directory, then store the path in the DB.
        upload_folder = os.path.join(app.root_path, 'static', 'profile_pics')
        if not os.path.exists(upload_folder):
            os.makedirs(upload_folder)
        
        # Example for saving: (Needs better filename handling for unique names)
        # from werkzeug.utils import secure_filename
        # filename = secure_filename(profile_picture_file.filename)
        # file_path = os.path.join(upload_folder, filename)
        # profile_picture_file.save(file_path)
        # user.profile_picture_url = filename # Store just the filename if static serves it
        
        flash('Profile picture upload logic needs to be fully implemented with secure filenames!', 'warning')
        # For demonstration, setting a placeholder if file was selected
        user.profile_picture_url = f'uploaded_{profile_picture_file.filename}'


    try:
        db.session.commit()
        flash('Profile updated successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'An error occurred during profile update: {e}', 'danger')

    return redirect(url_for('updateprofile'))



@app.route('/students/unnportal')
def unn_portal():
    if 'user_id' not in session:
        flash('Please log in to update your profile.', 'danger')
        return redirect(url_for('login'))

    """
    Renders the UNN Portal page from a template file.
    """
    return render_template('portal.html') # Changed to render_template



















# --- ADMIN DASHBOARD ROUTE ---
@app.route('/admin-dashboard') # Use your desired URL, e.g., '/admin-dashboard'
def admin_dashboard():
    # CUSTOM SESSION-BASED AUTHENTICATION CHECK
    if 'admin_id' not in session:
        flash('Please login first!', 'warning')
        return redirect(url_for('admin_login'))

    # Retrieve the admin user
    admin = Admin.query.get(session['admin_id'])
    if not admin:
        flash('Admin session invalid. Please login again.', 'danger')
        session.pop('admin_id', None)
        return redirect(url_for('admin_login'))

    # Fetch all publication schedules from the database
    schedules = ResultPublicationSchedule.query.all()
    
    # Pass both the admin and schedules data to the template
    return render_template('admin.html', admin=admin, schedules=schedules)



@app.route('/admin.-view-help-request')
def adminhelp():
    if 'admin_id' not in session:
        flash('Please login first!', 'warning')
        return redirect(url_for('admin_login'))
    help = Help.query.all()
    return render_template('adminhelp.html', help=help)



@app.route('/admin viewccontactrequest')
def adnincontact():
    if 'admin_id' not in session:
        flash('Please login first!', 'warning')
        return redirect(url_for('admin_login'))
    contact = Contact.query.all()
    return render_template('admincontact.html', contact=contact)




@app.route('/admin-login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        # This is the line you need to make sure is active and correct
        # It assumes you have SQLAlchemy or similar set up where Admin.query is available
        try:
            admin = Admin.query.filter_by(username=username).first()
        except Exception as e:
            print(e)

        if admin and admin.check_password(password):
            session['admin_id'] = admin.id
            flash('Logged in successfully!', 'success')
            return redirect(url_for('admin_dashboard'))
        else:
            flash('Invalid username or password!', 'danger')

    return render_template('admin_login.html')



@app.route('/admin-signup', methods=['GET', 'POST'])
def admin_signup():
    if request.method == 'POST':
        fullname = request.form['fullname']
        email = request.form['email']
        username = request.form['username']
        password = request.form['password']
        
        try:
            if Admin.query.filter_by(username=username).first():
                flash('Username already exists!', 'danger')
                return redirect(url_for('admin_signup'))
        except Exception as e:
                    print(e)
        try:
            if Admin.query.filter_by(email=email).first():
                flash('Email already registered!', 'danger')
                return redirect(url_for('admin_signup'))
        except Exception as e:
                    print(e)

        new_admin = Admin(fullname=fullname, email=email, username=username)
        new_admin.set_password(password)
        db.session.add(new_admin)
        db.session.commit()

        flash('Admin registered successfully! Please login.', 'success')
        return redirect(url_for('admin_login'))

    return render_template('admin_signup.html')


@app.route('/admin_logout')
def admin_logout():
    session.clear()
    flash('Logged out successfully.', 'info')
    return redirect(url_for('admin_login'))


# --- Helper Functions for Text Extraction ---
def extract_text_from_image(image_path):
    """Extracts text from an image using Tesseract OCR."""
    try:
        img = Image.open(image_path)
        text = pytesseract.image_to_string(img)
        return text
    except Exception as e:
        print(f"Error extracting text from image {image_path}: {e}")
        return None

def extract_text_from_document(doc_path, mimetype):
    """Extracts text from a document based on its MIME type."""
    text = None
    try:
        if mimetype == 'application/pdf':
            with open(doc_path, 'rb') as file:
                reader = PyPDF2.PdfReader(file)
                num_pages = len(reader.pages)
                extracted_pages_text = []
                for i in range(num_pages):
                    page = reader.pages[i]
                    extracted_pages_text.append(page.extract_text())
                text = "\n".join(extracted_pages_text)
        elif mimetype == 'application/msword' or mimetype == 'application/vnd.openxmlformats-officedocument.wordprocessingml.document':
            # For .doc (application/msword), you might need a library like antiword or python-docx's older version.
            # For .docx (application/vnd.openxmlformats-officedocument.wordprocessingml.document), python-docx works well.
            # This example focuses on .docx
            if mimetype == 'application/vnd.openxmlformats-officedocument.wordprocessingml.document':
                doc = docx.Document(doc_path)
                extracted_pages_text = [paragraph.text for paragraph in doc.paragraphs]
                text = "\n".join(extracted_pages_text)
            else: # .doc files are harder to parse directly in Python without external tools
                text = f"Text extraction for {mimetype} is not fully supported without external tools."
        elif mimetype == 'text/plain':
            with open(doc_path, 'r', encoding='utf-8') as file:
                text = file.read()
        else:
            text = f"Unsupported document type for extraction: {mimetype}"
    except Exception as e:
        print(f"Error extracting text from document {doc_path} ({mimetype}): {e}")
        return None
    return text

# ---
# Show Results Route
# ---
@app.route('/show-students-results')
@login_required
def show_results():
    # If you specifically want to enforce the 'admin_id' session check here,
    # despite the @login_required decorator, you can add it as follows:
    if 'admin_id' not in session:
        flash('Please login first!', 'warning')
        # You would typically redirect to a login page for admins here
        # return redirect(url_for('admin_login'))
        # For this example, we'll just return an error message
        return "Access Denied: Admin login required.", 403

    all_results = StudentResult.query.all()
    # Render the results in a dedicated HTML template
    return render_template('uploadresults.html', results=all_results)



@app.route('/add-dues', methods=['GET', 'POST'])
def add_dues():
    if 'admin_id' not in session:
        flash("You must be logged in as admin to access this page.", "warning")
        return redirect(url_for('admin_login'))

    if request.method == 'POST':
        fullname = request.form.get('fullname')
        regno = request.form.get('reg_number')
        sessions = request.form.getlist('session[]')

        if not fullname or not regno or not sessions:
            flash('All fields are required.', 'danger')
            return redirect(url_for('add_dues'))

        admin_id = session.get('admin_id')  # assuming admin is logged in
        if not admin_id:
            flash('Admin login required to submit form.', 'danger')
            return redirect(url_for('admin_login'))  # redirect to login or some safe page

        dues = AdminAddDues(
            fullname=fullname,
            regno=regno,
            admin_id=admin_id,
            user_id=admin_id,  # Make sure this matches your model if user_id is required
            sessions_paid=', '.join(sessions)
        )

        db.session.add(dues)
        db.session.commit()
        flash('Dues successfully recorded.', 'success')
        return redirect(url_for('add_dues'))

    return render_template('admin_adddues.html')

@app.route('/admin_addcandidate', methods=['GET', 'POST'])
def add_candidate():
    if 'admin_id' not in session:
        flash("You must be logged in as admin to access this page.", "warning")
        return redirect(url_for('admin_login'))

    if request.method == 'POST':
        fullname = request.form['fullname']
        regno = request.form['regno']
        position = request.form['position']
        profile_pic = request.files['profile_pic']

        # 1. Find the User associated with the registration number
        # This is the new crucial step since regno is now on the User model
        try:
            user_to_register = User.query.filter_by(regno=regno).first()
        except Exception as e:
            print(e)


        if not user_to_register:
            flash(f"User with Registration Number {regno} does not exist.", "danger")
            return redirect(url_for('add_candidate'))

        # 2. Check Dues using the user's regno (This remains the same if AdminAddDues uses regno)
        try:
            dues_paid = AdminAddDues.query.filter_by(regno=regno).first()
        except Exception as e:
                    print(e)
        if not dues_paid:
            flash("Candidate has not paid departmental dues.", "danger")
            return redirect(url_for('add_candidate'))

        # 3. Check if the User is already registered as a Candidate
        #    We now check the ElectoralCandidate table using the user's ID
        try:
            already_registered = ElectoralCandidate.query.filter_by(user_id=user_to_register.id).first() 
        except Exception as e:
                    print(e)
                
        if already_registered:
            flash("Candidate already registered for a position.", "warning")
            return redirect(url_for('add_candidate'))

        if not profile_pic:
            flash("Please upload a profile picture.", "danger")
            return redirect(url_for('add_candidate'))

        # --- File Upload Logic ---
        filename = secure_filename(profile_pic.filename)
        upload_folder = os.path.join('static', 'uploads')
        os.makedirs(upload_folder, exist_ok=True)
        profile_path = os.path.join(upload_folder, filename)
        profile_pic.save(profile_path)
        # --- End File Upload Logic ---

        # 4. Create the new candidate using user_id
        # We no longer save fullname or regno directly on ElectoralCandidate
        new_candidate = ElectoralCandidate(
            user_id=user_to_register.id, # Link the candidate profile to the User
            position=position,
            profile_pic=filename
        )
        db.session.add(new_candidate)
        db.session.commit()

        flash("Candidate added successfully.", "success")
        return redirect(url_for('add_candidate'))

    # --- GET request - fetch candidates and their vote counts ---
    try:
        all_candidates = ElectoralCandidate.query.all()
    except Exception as e:
                print(e)
    vote_counts = db.session.query(
        Vote.candidate_id,
        db.func.count(Vote.id).label('vote_count')
    ).group_by(Vote.candidate_id).all()
    
    vote_dict = {candidate_id: count for candidate_id, count in vote_counts}

    candidates_by_position = {}

    for candidate in all_candidates:
        position = candidate.position
        candidate.vote_count = vote_dict.get(candidate.id, 0)  # Add vote_count dynamically
        
        # NOTE: To use candidate.fullname and candidate.regno in the template, 
        # the User model and its relationship MUST be loaded.
        # You might need to add: candidate.fullname = candidate.user.fullname 
        # and candidate.regno = candidate.user.regno 
        # to the candidate object here if they aren't available via the template logic.

        if position not in candidates_by_position:
            candidates_by_position[position] = []
        candidates_by_position[position].append(candidate)

    return render_template('admin_addcandidates.html', candidates_by_position=candidates_by_position)


@app.route('/results')
def results():
    if 'user_id' not in session:
        flash("Please log in or sign up to view the election results.", "warning")
        return redirect(url_for('login'))

     # GET request - fetch candidates and their vote counts
    all_candidates = ElectoralCandidate.query.all()
    vote_counts = db.session.query(
        Vote.candidate_id,
        db.func.count(Vote.id).label('vote_count')
    ).group_by(Vote.candidate_id).all()
    
    vote_dict = {candidate_id: count for candidate_id, count in vote_counts}

    candidates_by_position = {}

    for candidate in all_candidates:
        position = candidate.position
        candidate.vote_count = vote_dict.get(candidate.id, 0)  # Add vote_count dynamically
        if position not in candidates_by_position:
            candidates_by_position[position] = []
        candidates_by_position[position].append(candidate)

    return render_template('results.html', candidates_by_position=candidates_by_position)

@app.route('/students-vote', methods=['GET', 'POST'])
def vote():
    if 'user_id' not in session:
        flash("Please log in to access the voting page.", "danger")
        return redirect(url_for('login'))

    user = User.query.get(session['user_id'])
    if not user:
        flash("User not found.", "danger")
        return redirect(url_for('login'))
    try:
        dues_record = AdminAddDues.query.filter_by(regno=user.regno).first()
    except Exception as e:
                print(e)
    if not dues_record:
        flash("You are not eligible to vote. Please ensure your dues are cleared.", "warning")
        return redirect(url_for('dashboard'))

    # Prevent multiple votes
    try:
        previous_votes = Vote.query.filter_by(user_id=user.id).first()
    except Exception as e:
                print(e)
    if previous_votes:
        flash("You have already voted.", "warning")
        return redirect(url_for('results'))

    candidates = ElectoralCandidate.query.all()
    candidates_by_position = {}
    for candidate in candidates:
        candidates_by_position.setdefault(candidate.position, []).append(candidate)

    if request.method == 'POST':
        for position, candidates_list in candidates_by_position.items():
            vote_value = request.form.get(position)

            if not vote_value:
                flash(f"You must vote for the position: {position}", "danger")
                return redirect(url_for('vote'))

            # Handle YES/NO votes
            if vote_value.startswith('yes-') or vote_value.startswith('no-'):
                vote_type, candidate_id = vote_value.split('-')
                decision = vote_type  # yes or no
                candidate_id = int(candidate_id)
            else:
                decision = 'selected'
                candidate_id = int(vote_value)

            # Save vote
            vote = Vote(user_id=user.id, position=position, candidate_id=candidate_id, decision=decision)
            db.session.add(vote)

        db.session.commit()
        flash("Your vote has been submitted successfully.", "success")
        return redirect(url_for('dashboard'))

    return render_template('vote_dashboard.html', candidates_by_position=candidates_by_position)

  
@app.route('/admin/project_ideas')
def admin_project_ideas():
    # TODO: Implement robust admin authentication here
    # For now, we'll just check if a user is logged in, but you should
    # have a separate check for admin roles.
    if 'admin_id' not in session:
        flash('Please log in as an administrator to view this page.', 'danger')
        return redirect(url_for('admin_login'))

    # Fetch all project ideas, ordered by submission date (newest first)
    project_ideas = ProjectIdea.query.order_by(ProjectIdea.submission_date.desc()).all()

    # You might want to fetch the user object for each project idea
    # if you want to display the submitter's name/email.
    # We'll pass the whole project_ideas list to the template,
    # and the template can access project_idea.author.fullname
    # because of the backref='author' in the User model.
    return render_template('admin_project_ideas.html', project_ideas=project_ideas)

@app.route('/admin/project_ideas/edit/<int:idea_id>', methods=['GET', 'POST'])
def admin_edit_project_idea(idea_id):
    # TODO: Implement robust admin authentication here
    if 'admin_id' not in session:
        flash('Please log in as an administrator to edit project ideas.', 'danger')
        return redirect(url_for('admin_login'))

    idea = ProjectIdea.query.get_or_404(idea_id)

    if request.method == 'POST':
        idea.title = request.form['title']
        idea.description = request.form['description']
        idea.innovations = request.form['innovations']
        idea.contact_email = request.form['contact_email']
        idea.visibility = request.form['visibility']

        # Handle file uploads if any. This is a simplified example.
        # In a real application, you'd want to handle multiple files,
        # deletion of old files, and robust file saving.
        # For now, we'll just show how you *might* handle a new file.
        if 'project_files' in request.files:
            files = request.files.getlist('project_files')
            new_file_paths = []
            for file in files:
                if file and allowed_file(file.filename): # You'd need to define allowed_file
                    filename = secure_filename(file.filename)
                    file_path = projects_uploads.save(file, folder=str(idea.id)) # Save to a subfolder per idea
                    new_file_paths.append(file_path)

            if new_file_paths:
                # Append new paths to existing ones, or overwrite if that's the desired behavior
                existing_paths = idea.file_paths.split(',') if idea.file_paths else []
                updated_paths = existing_paths + new_file_paths
                idea.file_paths = ','.join(updated_paths)


        try:
            db.session.commit()
            flash('Project idea updated successfully!', 'success')
            return redirect(url_for('admin_project_ideas'))
        except Exception as e:
            db.session.rollback()
            flash(f'An error occurred while updating the project idea: {e}', 'danger')

    return render_template('admin_edit_project_idea.html', idea=idea)

@app.route('/admin/project_ideas/delete/<int:idea_id>', methods=['POST'])
def admin_delete_project_idea(idea_id):
    # TODO: Implement robust admin authentication here
    if 'admin_id' not in session:
        flash('Please log in as an administrator to delete project ideas.', 'danger')
        return redirect(url_for('admin_login'))

    idea = ProjectIdea.query.get_or_404(idea_id)
    try:
        # Optionally, delete associated files from the file system
        if idea.file_paths:
            for file_path in idea.file_paths.split(','):
                full_path = os.path.join(app.config['UPLOADED_PROJECTS_DEST'], os.path.basename(file_path))
                if os.path.exists(full_path):
                    os.remove(full_path)
                    print(f"Deleted file: {full_path}") # For debugging

        db.session.delete(idea)
        db.session.commit()
        flash('Project idea deleted successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'An error occurred while deleting the project idea: {e}', 'danger')

    return redirect(url_for('admin_project_ideas'))


@app.route('/vote_timer')
def vote_timer():
    if 'user_id' not in session:
        flash("Please log in or sign up to view the election results.", "warning")
        return redirect(url_for('login'))

    now = datetime.now()

    if now < ELECTION_START:
        return redirect(url_for('wait_page'))
    elif ELECTION_START <= now <= ELECTION_END:
        return render_template('vote_dashboard.html')  # Your actual voting page
    else:
        return redirect(url_for('results'))

@app.route('/wait')
def wait_page():
    return render_template('wait.html')

# --- Existing /admin-dashboard_details route (as provided by you) ---
@app.route("/admin-dashboard_details")
def details():
    # Admin login check using session
    if 'admin_id' not in session: # Corrected 'not None' to 'not in session'
        flash("You must be logged in as admin to access this page.", "warning")
        return redirect(url_for('admin_login'))

    users = User.query.all()
    voters = (
        db.session.query(User)
        .join(Vote)
        .filter(Vote.candidate_id.isnot(None))
        .distinct()
        .all()
    )
    dues_payers = (
        db.session.query(User)
        .join(AdminAddDues, AdminAddDues.user_id == User.id)
        .distinct()
        .all()
    )
    candidates = ElectoralCandidate.query.all()
    lecturers = Lecturer.query.all()

    return render_template(
        "details.html",
        users=users,
        voters=voters,
        dues_payers=dues_payers,
        candidates=candidates,
        lecturers=lecturers
    )

# --- UPDATED: Edit User Route (with password change functionality) ---
@app.route('/admin/user/edit/<int:user_id>', methods=['GET', 'POST'])
def admin_edit_user(user_id):
    if 'admin_id' not in session:
        flash("You must be logged in as admin to access this page.", "warning")
        return redirect(url_for('admin_login'))

    user = User.query.get_or_404(user_id) # Fetch the user or return 404

    if request.method == 'POST':
        # Update basic user details
        # Note: Your User model has 'fullname', 'email', 'regno', 'phone'
        # It does NOT have 'username' unless you added it.
        # Ensure these match your User model's attributes.
        user.email = request.form['email']
        user.fullname = request.form['fullname']
        user.regno = request.form['regno'] # Make sure your HTML form has this input
        user.phone = request.form['phone'] # Make sure your HTML form has this input

        # Handle password change
        new_password = request.form.get('new_password') # Use .get() as it's optional
        confirm_password = request.form.get('confirm_password')

        if new_password: # If a new password was entered
            if new_password == confirm_password:
                # Hash the new password before saving
                # Assuming User model has a set_password method or you directly assign
                # user.set_password(new_password) # If you have this method in your User model
                user.password = generate_password_hash(new_password) # Direct assignment
                flash('Password changed successfully!', 'success')
            else:
                flash('New password and confirmation do not match!', 'danger')
                return render_template('admin_edit_user.html', user=user) # Re-render to show error and preserve other input
        elif new_password != "" and not confirm_password: # Check if new_password was entered but not confirmed
             flash('Please confirm the new password.', 'danger')
             return render_template('admin_edit_user.html', user=user)

        try:
            db.session.commit()
            flash('User details updated successfully!', 'success') # Changed message to be broader
            return redirect(url_for('details')) # Redirect to the details page after update
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating user: {str(e)}', 'danger')
            print(f"Error updating user: {e}") # For debugging
            return render_template('admin_edit_user.html', user=user) # Re-render on error

    return render_template('admin_edit_user.html', user=user)

# --- NEW: Delete User Route ---
@app.route("/admin/user/delete/<int:user_id>", methods=['POST']) # Use POST for deletions
def admin_delete_user(user_id):
    if 'admin_id' not in session:
        flash("You must be logged in as admin to access this page.", "warning")
        return redirect(url_for('admin_login'))

    user = User.query.get_or_404(user_id)

    try:
        db.session.delete(user)
        db.session.commit()
        # Note: Your User model does not have 'username', use 'fullname' if that's the display name
        flash(f"User '{user.fullname}' deleted successfully!", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error deleting user: {str(e)}", "danger")

    return redirect(url_for('details')) # Redirect back to the details page

# --- NEW: Edit Lecturer Route (Example for other models) ---
@app.route("/admin/lecturer/edit/<int:lecturer_id>", methods=['GET', 'POST'])
def admin_edit_lecturer(lecturer_id):
    if 'admin_id' not in session:
        flash("You must be logged in as admin to access this page.", "warning")
        return redirect(url_for('admin_login'))

    lecturer = Lecturer.query.get_or_404(lecturer_id)

    if request.method == 'POST':
        lecturer.full_name = request.form.get('full_name') # Corrected to full_name as per Lecturer model
        lecturer.email = request.form.get('email')
        lecturer.department = request.form.get('department')
        lecturer.staff_id = request.form.get('staff_id')
        lecturer.phone_number = request.form.get('phone_number')
        lecturer.state_of_origin = request.form.get('state_of_origin')
        lecturer.lga = request.form.get('lga')
        lecturer.home_address = request.form.get('home_address')

        # Handle password change for lecturer (similar to user)
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')

        if new_password:
            if new_password == confirm_password:
                lecturer.password_hash = generate_password_hash(new_password)
                flash('Lecturer password changed successfully!', 'success')
            else:
                flash('New password and confirmation do not match!', 'danger')
                return render_template("admin_edit_lecturer.html", lecturer=lecturer)
        elif new_password != "" and not confirm_password:
            flash('Please confirm the new password.', 'danger')
            return render_template('admin_edit_lecturer.html', lecturer=lecturer)


        try:
            db.session.commit()
            flash(f"Lecturer '{lecturer.full_name}' updated successfully!", "success")
            return redirect(url_for('details'))
        except Exception as e:
            db.session.rollback()
            flash(f"Error updating lecturer: {str(e)}", "danger")
            print(f"Error updating lecturer: {e}")

    return render_template("admin_edit_lecturer.html", lecturer=lecturer)

# --- NEW: Delete Lecturer Route ---
@app.route("/admin/lecturer/delete/<int:lecturer_id>", methods=['POST'])
def admin_delete_lecturer(lecturer_id):
    if 'admin_id' not in session:
        flash("You must be logged in as admin to access this page.", "warning")
        return redirect(url_for('admin_login'))

    lecturer = Lecturer.query.get_or_404(lecturer_id)

    try:
        db.session.delete(lecturer)
        db.session.commit()
        flash(f"Lecturer '{lecturer.full_name}' deleted successfully!", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error deleting lecturer: {str(e)}", "danger")

    return redirect(url_for('details'))

# --- NEW: Edit Candidate Route ---
@app.route("/admin/candidate/edit/<int:candidate_id>", methods=['GET', 'POST'])
def admin_edit_candidate(candidate_id):
    if 'admin_id' not in session:
        flash("You must be logged in as admin to access this page.", "warning")
        return redirect(url_for('admin_login'))

    candidate = ElectoralCandidate.query.get_or_404(candidate_id)

    if request.method == 'POST':
        # Assuming you want to edit position and profile_pic
        candidate.position = request.form.get('position')
        candidate.profile_pic = request.form.get('profile_pic') # If you handle file uploads, this will be more complex

        # If you linked candidate to user, you might want to edit user details via candidate.user
        # For example:
        # if candidate.user:
        #     candidate.user.fullname = request.form.get('user_fullname')
        #     candidate.user.email = request.form.get('user_email')
        #     # ... and so on for other user fields

        try:
            db.session.commit()
            flash(f"Candidate '{candidate.user.fullname if candidate.user else candidate.position}' updated successfully!", "success")
            return redirect(url_for('details'))
        except Exception as e:
            db.session.rollback()
            flash(f"Error updating candidate: {str(e)}", "danger")
            print(f"Error updating candidate: {e}")

    return render_template("admin_edit_candidate.html", candidate=candidate)

# --- NEW: Delete Candidate Route ---
@app.route("/admin/candidate/delete/<int:candidate_id>", methods=['POST'])
def admin_delete_candidate(candidate_id):
    if 'admin_id' not in session:
        flash("You must be logged in as admin to access this page.", "warning")
        return redirect(url_for('admin_login'))

    candidate = ElectoralCandidate.query.get_or_404(candidate_id)

    try:
        db.session.delete(candidate)
        db.session.commit()
        flash(f"Candidate '{candidate.user.fullname if candidate.user else candidate.position}' deleted successfully!", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error deleting candidate: {str(e)}", "danger")

    return redirect(url_for('details'))






@app.route('/upload_results', methods=['GET', 'POST'])
def upload_results():
    if 'admin_id' not in session:
        flash('Please login first!', 'warning')
        return redirect(url_for('admin_login'))

    if request.method == 'POST':
        # Course Details Validation
        course_code = request.form.get('courseCode')
        course_title = request.form.get('courseTitle')
        session_written = request.form.get('sessionWritten')
        year = request.form.get('year')
        semester = request.form.get('semester')

        if not all([course_code, course_title, session_written, year, semester]):
            flash('All course details are required.', 'error')
            return render_template('results_upload.html', form_data=request.form)

        # Bulk Student Details Validation
        student_names_raw = request.form.get('studentNamesBulk')
        reg_numbers_raw = request.form.get('regNumbersBulk')
        ca_scores_raw = request.form.get('caScoresBulk')
        exam_scores_raw = request.form.get('examScoresBulk')

        names = parse_bulk_input(student_names_raw)
        reg_numbers = parse_bulk_input(reg_numbers_raw)
        ca_scores = parse_bulk_input(ca_scores_raw)
        exam_scores = parse_bulk_input(exam_scores_raw)

        # Check if all bulk input arrays have the same length
        if not (len(names) == len(reg_numbers) == len(ca_scores) == len(exam_scores)):
            flash('All bulk student input fields must have the same number of entries.', 'error')
            return render_template('results_upload.html', form_data=request.form)

        if not names: # Check if there are any student entries at all
            flash('At least one student entry is required for bulk upload.', 'error')
            return render_template('results_upload.html', form_data=request.form)

        # Validate and process scores
        students_data = []
        has_score_error = False
        for i in range(len(names)):
            try:
                ca = float(ca_scores[i])
                exam = float(exam_scores[i])

                if not (0 <= ca <= 30):
                    flash(f'CA Score for student {names[i]} (entry {i+1}) is invalid. Must be between 0 and 30.', 'error')
                    has_score_error = True
                if not (0 <= exam <= 70):
                    flash(f'Exam Score for student {names[i]} (entry {i+1}) is invalid. Must be between 0 and 70.', 'error')
                    has_score_error = True

                total = ca + exam
                if total > 100:
                    flash(f'Total score for student {names[i]} (entry {i+1}) exceeds 100 ({total}). Capped at 100.', 'warning')
                total = min(total, 100) # Cap total at 100

                students_data.append({
                    'name': names[i],
                    'reg_number': reg_numbers[i],
                    'ca_score': int(ca),
                    'exam_score': int(exam),
                    'total_score': int(total),
                    'grade': calculate_grade(total)
                })
            except ValueError:
                flash(f'Invalid score format for an entry at position {i+1}. Scores must be numbers.', 'error')
                has_score_error = True
            except IndexError:
                flash(f'Missing score for an entry at position {i+1}. Please ensure all score fields have corresponding entries.', 'error')
                has_score_error = True

        if has_score_error:
            return render_template('results_upload.html', form_data=request.form)

        try:
            # --- DEBUGGED LOGIC START ---
            # First, try to find a course by its course_code.
            # This handles the scenario where course_code is unique in the DB.
            course = Course.query.filter_by(course_code=course_code).first()

            if course:
                # If a course with this course_code exists, update its details.
                # This prevents the UNIQUE constraint error on course_code.
                course.course_title = course_title
                course.session_written = session_written
                course.year = year
                course.semester = semester
                # No need to add to session, it's already managed by SQLAlchemy
                flash(f"Course '{course_code}' updated with new session/year/semester details.", 'info')
            else:
                # If no course with this course_code exists, create a new one.
                course = Course(
                    course_code=course_code,
                    course_title=course_title,
                    session_written=session_written,
                    year=year,
                    semester=semester
                )
                db.session.add(course)
                flash(f"New course '{course_code}' added.", 'info')

            db.session.commit() # Commit the new course or the updated course

            # --- DEBUGGED LOGIC END ---

            # Add student results
            for student_data in students_data:
                try:
                    # Check if student result for this course already exists
                    existing_result = StudentResult.query.filter_by(
                        course_id=course.id,
                        reg_number=student_data['reg_number']
                    ).first()

                    if existing_result:
                        # Update existing result
                        existing_result.student_name = student_data['name']
                        existing_result.ca_score = student_data['ca_score']
                        existing_result.exam_score = student_data['exam_score']
                        existing_result.total_score = student_data['total_score']
                        existing_result.grade = student_data['grade']
                        flash(f"Updated result for {student_data['name']} ({student_data['reg_number']}) in {course_code}.", 'info')
                    else:
                        # Add new result
                        new_result = StudentResult(
                            course_id=course.id,
                            student_name=student_data['name'],
                            reg_number=student_data['reg_number'],
                            ca_score=student_data['ca_score'],
                            exam_score=student_data['exam_score'],
                            total_score=student_data['total_score'],
                            grade=student_data['grade']
                        )
                        db.session.add(new_result)
                        flash(f"Added result for {student_data['name']} ({student_data['reg_number']}) in {course_code}.", 'info')
                    db.session.commit() # Commit each student result
                except IntegrityError:
                    db.session.rollback()
                    flash(f"Duplicate entry: Student with registration number '{student_data['reg_number']}' already has results for this course.", 'warning')
                except Exception as e:
                    db.session.rollback()
                    flash(f"An error occurred while adding result for {student_data['name']}: {str(e)}", 'error')
                    # It's better to continue processing other students if possible,
                    # or redirect to the form with an error, rather than index.html
                    return render_template('results_upload.html', form_data=request.form)

            flash('Course and student results processed successfully!', 'success')
            return redirect(url_for('upload_results')) # Redirect to clear form
        except Exception as e:
            db.session.rollback()
            flash(f'An error occurred during submission: {str(e)}', 'error')
            return render_template('results_upload.html', form_data=request.form)

    return render_template('results_upload.html', form_data={})
@app.route('/uploaded_results')
def display_uploaded_results():
    if 'admin_id' not in session:
        flash('Please login first!', 'warning')
        return redirect(url_for('admin_login'))
    """
    Renders the page to display all uploaded student results.
    Fetches all student results from the database and passes them to the template.
    """
    try:
        # Eager load the 'course' relationship and convert to serializable dictionaries
        all_results_data = StudentResult.query.options(db.joinedload(StudentResult.course)).all()
        serializable_results = []
        for res in all_results_data:
            serializable_results.append({
                'id': res.id,
                'student_name': res.student_name,
                'reg_number': res.reg_number,
                'ca_score': res.ca_score,
                'exam_score': res.exam_score,
                'total_score': res.total_score,
                'grade': res.grade,
                'course': {
                    'id': res.course.id,
                    'course_code': res.course.course_code,
                    'course_title': res.course.course_title,
                    'year': res.course.year,
                    'semester': res.course.semester,
                    'session_written': res.course.session_written
                }
            })
        
        return render_template('showresults.html', all_results=serializable_results)
    except Exception as e:
        # Log the error for debugging purposes
        print(f"Error fetching results for display_uploaded_results: {e}")
        # Render an error page with a specific message
        return render_template('error.html', message="Could not load uploaded student results due to a server error."), 500
 

@app.route('/edit_result/<int:result_id>', methods=['POST'])
def edit_result(result_id):
    """
    Handles updating an existing student result.
    Expects a JSON payload with 'ca_score' and 'exam_score'.
    """
    result_to_edit = StudentResult.query.get_or_404(result_id)
    
    try:
        data = request.json
        if not data:
            return jsonify({'success': False, 'message': 'Invalid JSON data'}), 400

        ca_score = int(data.get('ca_score'))
        exam_score = int(data.get('exam_score'))
        
        # Update the scores and recalculate derived fields
        result_to_edit.ca_score = ca_score
        result_to_edit.exam_score = exam_score
        result_to_edit.total_score = ca_score + exam_score
        result_to_edit.grade = calculate_grade(result_to_edit.total_score)
        
        db.session.commit()
        return jsonify({'success': True, 'message': 'Result updated successfully!'}), 200
        
    except (ValueError, TypeError) as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Error processing scores: {str(e)}'}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Error updating result: {str(e)}'}), 500
    
@app.route('/delete_result/<int:result_id>', methods=['POST'])
def delete_result(result_id):
    """
    Handles deleting a student result.
    Expects the result_id in the URL.
    """
    result_to_delete = StudentResult.query.get_or_404(result_id)
    try:
        db.session.delete(result_to_delete)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Result deleted successfully!'}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Error deleting result: {str(e)}'}), 500

@app.route('/get_result/<int:result_id>', methods=['GET'])
def get_result(result_id):
    """
    Fetches a single student result by ID for editing.
    """
    result = StudentResult.query.get_or_404(result_id)
    return jsonify({
        'id': result.id,
        'student_name': result.student_name,
        'reg_number': result.reg_number,
        'course_id': result.course_id,
        'ca_score': result.ca_score,
        'exam_score': result.exam_score,
        'total_score': result.total_score,
        'grade': result.grade
    })



@app.route('/search_results', methods=['GET', 'POST'])
def search_results():
    """
    Allows an admin to search for student results by registration number or course code.
    Displays a search form on GET and filtered results on POST.
    """
    if 'admin_id' not in session:
        flash('Please login first!', 'warning')
        return redirect(url_for('admin_login'))

    search_query = ""
    results = []
    
    if request.method == 'POST':
        search_query = request.form.get('search_query', '').strip()
        
        if search_query:
            # Query for results that match the student's registration number OR the course code
            results = StudentResult.query.join(Course).filter(
                (StudentResult.reg_number.ilike(f'%{search_query}%')) |
                (Course.course_code.ilike(f'%{search_query}%'))
            ).all()
            
            if not results:
                flash(f'No results found for "{search_query}".', 'info')
        else:
            flash('Please enter a search term.', 'warning')
            
    # For a GET request, or if the search was empty, we can show all results,
    # or an empty list if you prefer. Here, we default to showing all.
    if request.method == 'GET' or not search_query:
        results = StudentResult.query.all()
    
    return render_template('searchresults.html', all_results=results, search_query=search_query)
# In your app.py file




# --- New Admin Search Route ---
@app.route('/admin/searchresults', methods=['GET', 'POST'])
def admin_search_results():
    if 'admin_id' not in session:
        flash('Please login first!', 'warning')
        return redirect(url_for('admin_login'))

    """
    Renders the page for admins to search and display student results.
    Allows searching by year, semester, or the first four digits of the registration number.
    """
    all_results = []
    search_performed = False

    try:
        if request.method == 'POST':
            search_performed = True
            year = request.form.get('year')
            semester = request.form.get('semester')
            reg_prefix = request.form.get('reg_prefix')

            query = StudentResult.query

            if year:
                try:
                    query = query.filter_by(year=int(year))
                except ValueError:
                    flash('Invalid year entered. Please enter a number.', 'danger')
                    return render_template('admin_search_results.html', all_results=[], search_performed=False)
            if semester and semester != 'all':
                query = query.filter_by(semester=semester)
            if reg_prefix:
                # Filter by registration number starting with the prefix
                query = query.filter(StudentResult.reg_number.startswith(reg_prefix))

            all_results = query.all()

            if not all_results and search_performed:
                flash('No results found for your search criteria.', 'info')

        # If GET request or no specific search parameters on POST,
        # we might want to show all results initially or an empty state.
        # For this, let's just show an empty table on initial GET.
        # If you want to display all results on initial load, remove the 'if request.method == 'POST':' block
        # and set all_results = StudentResult.query.all() here.

    except Exception as e:
        print(f"Error searching results: {e}")
        flash('An error occurred while fetching results.', 'danger')
        return render_template('admin_search_results.html', all_results=[], search_performed=False)

    return render_template('admin_search_results.html', all_results=all_results, search_performed=search_performed)





# --- NEW ADMIN ROUTE: SCHEDULE RESULT PUBLICATION ---
@app.route('/admin/schedule_results', methods=['GET', 'POST'])
def admin_schedule_results():
    print(f"Session contents: {session}")
    if 'admin_id' not in session:
        print("admin_id NOT in session, redirecting to login!")
        flash('Please login first!', 'warning')
        return redirect(url_for('admin_login'))
    # ... rest of your code

    # Retrieve the admin user using the session ID
    admin_user = Admin.query.get(session['admin_id'])
    if not admin_user: # Defensive check if admin_id is somehow invalid
        flash('Admin session invalid. Please login again.', 'danger')
        session.pop('admin_id', None) # Clear invalid session
        # If using Flask-Login, also log out the user
        # from flask_login import logout_user
        # logout_user() 
        return redirect(url_for('admin_login'))

    # Query the database to get a unique list of all academic sessions
    # This replaces the hardcoded list
    academic_sessions = [session[0] for session in db.session.query(Course.session_written).distinct().all()]
    
    # Fetch all courses, which are needed for the form dropdown
    courses = Course.query.all()

    if request.method == 'POST':
        course_id = request.form.get('course_id')
        session_written = request.form.get('session_written')
        publish_start_str = request.form.get('publish_start')
        publish_end_str = request.form.get('publish_end')

        if not all([course_id, session_written, publish_start_str, publish_end_str]):
            flash('All fields are required!', 'danger')
            # Ensure redirect passes necessary data for GET request, if applicable
            return redirect(url_for('admin_schedule_results'))

        try:
            course_id = int(course_id)
            # Use a time zone-aware datetime object for Lagos time
            lagos_tz = pytz.timezone('Africa/Lagos')
            publish_start = lagos_tz.localize(datetime.strptime(publish_start_str, '%Y-%m-%dT%H:%M'))
            publish_end = lagos_tz.localize(datetime.strptime(publish_end_str, '%Y-%m-%dT%H:%M'))

            if publish_start >= publish_end:
                flash('Publication end time must be after start time.', 'danger')
                return redirect(url_for('admin_schedule_results'))

            # Check if a schedule already exists for this course and session
            existing_schedule = ResultPublicationSchedule.query.filter_by(
                course_id=course_id,
                session_written=session_written
            ).first()

            if existing_schedule:
                flash(f'A publication schedule for this course ({existing_schedule.course.course_code}) and session ({session_written}) already exists. Please edit the existing one.', 'warning')
                return redirect(url_for('admin_schedule_results'))

            new_schedule = ResultPublicationSchedule(
                course_id=course_id,
                session_written=session_written,
                publish_start=publish_start,
                publish_end=publish_end,
                admin_id=admin_user.id, # Use admin_user.id from the retrieved object
                is_active=True # Automatically active upon creation
            )
            db.session.add(new_schedule)
            db.session.commit()
            flash('Result publication schedule created successfully!', 'success')
            return redirect(url_for('admin_dashboard'))

        except ValueError:
            flash('Invalid date/time format. Please use the provided date/time picker.', 'danger')
        except IntegrityError:
            db.session.rollback()
            flash('An error occurred. A schedule might already exist for this course and session.', 'danger')
        except Exception as e:
            db.session.rollback()
            flash(f'An unexpected error occurred: {e}', 'danger')

    # For GET request, render the form with current data
    # Pass 'academic_sessions' fetched from the database
    return render_template('admin_schedule_results.html', courses=courses, academic_sessions=academic_sessions)


# --- NEW ADMIN ROUTE: EDIT PUBLICATION SCHEDULE ---
@app.route('/admin/edit_publication/<int:schedule_id>', methods=['GET', 'POST'])
def admin_edit_publication(schedule_id):
    # CUSTOM SESSION-BASED AUTHENTICATION CHECK
    if 'admin_id' not in session:
        flash('Please login first!', 'warning')
        return redirect(url_for('admin_login'))
    
    # Retrieve the admin user
    admin_user = Admin.query.get(session['admin_id'])
    if not admin_user:
        flash('Admin session invalid. Please login again.', 'danger')
        session.pop('admin_id', None)
        logout_user()
        return redirect(url_for('admin_login'))

    # Fetch the specific schedule to edit
    schedule = ResultPublicationSchedule.query.get_or_404(schedule_id)

    # Check if the current admin is allowed to edit this schedule (optional, but good practice)
    # if schedule.admin_id != admin_user.id:
    #     flash('You are not authorized to edit this schedule.', 'danger')
    #     return redirect(url_for('admin_schedule_results'))

    courses = Course.query.all()
    academic_sessions = ["2022/2023", "2023/2024", "2024/2025", "2025/2026"]
    lagos_tz = pytz.timezone('Africa/Lagos')

    if request.method == 'POST':
        # Retrieve updated data from the form
        course_id = request.form.get('course_id') # Course might be fixed or editable based on UX
        session_written = request.form.get('session_written') # Session might be fixed or editable
        publish_start_str = request.form.get('publish_start')
        publish_end_str = request.form.get('publish_end')
        is_active = request.form.get('is_active') == 'on' # Checkbox value

        if not all([course_id, session_written, publish_start_str, publish_end_str]):
            flash('All fields are required!', 'danger')
            return redirect(url_for('admin_edit_publication', schedule_id=schedule.id))

        try:
            # Update the schedule object with new values
            schedule.course_id = int(course_id)
            schedule.session_written = session_written
            schedule.publish_start = lagos_tz.localize(datetime.strptime(publish_start_str, '%Y-%m-%dT%H:%M'))
            schedule.publish_end = lagos_tz.localize(datetime.strptime(publish_end_str, '%Y-%m-%dT%H:%M'))
            schedule.is_active = is_active

            if schedule.publish_start >= schedule.publish_end:
                flash('Publication end time must be after start time.', 'danger')
                return redirect(url_for('admin_edit_publication', schedule_id=schedule.id))
            
            # Commit changes to the database
            db.session.commit()
            flash('Publication schedule updated successfully!', 'success')
            return redirect(url_for('admin_schedule_results')) # Redirect back to the list of schedules

        except ValueError:
            flash('Invalid date/time format. Please use the provided date/time picker.', 'danger')
        except IntegrityError:
            db.session.rollback()
            flash('An error occurred. A schedule for this course and session might already exist.', 'danger')
        except Exception as e:
            db.session.rollback()
            flash(f'An unexpected error occurred: {e}', 'danger')

    # For GET request, render the edit form with current schedule data
    return render_template('admin_edit_publication.html', 
                           schedule=schedule, 
                           courses=courses, 
                           academic_sessions=academic_sessions)




# --- NEW USER ROUTE: VIEW PUBLISHED RESULTS ---
@app.route('/student/view_results')
# Removed @login_required because you requested custom session check
def student_view_results():
    # CUSTOM SESSION-BASED AUTHENTICATION CHECK
    if 'user_id' not in session:
        flash('Please log in first.', 'danger')
        return redirect(url_for('login'))
    
    # Retrieve the user object using the session ID
    user = User.query.get(session['user_id'])
    if not user: # Defensive check if user_id is somehow invalid
        flash('User session invalid. Please login again.', 'danger')
        session.pop('user_id', None) # Clear invalid session
        logout_user() # Ensure Flask-Login also logs out
        return redirect(url_for('login'))

    user_reg_number = user.regno # Use the retrieved user object
    # Use a time zone-aware datetime object for the current time in Lagos
    lagos_tz = pytz.timezone('Africa/Lagos')
    current_time = datetime.now(lagos_tz)

    # Get active publication schedules
    active_schedules = ResultPublicationSchedule.query.filter(
        ResultPublicationSchedule.publish_start <= current_time,
        ResultPublicationSchedule.publish_end >= current_time,
        ResultPublicationSchedule.is_active == True
    ).all()

    published_results = []
    # Collect results for the current student that fall within active publication schedules
    for schedule in active_schedules:
        # Fetch results for the current student, for the specific course and session from the active schedule
        student_course_results = StudentResult.query.filter_by(
            reg_number=user_reg_number,
            course_id=schedule.course_id
        ).all()

        for result in student_course_results:
            # Check if the result's course's session matches the schedule's session
            if result.course and result.course.session_written == schedule.session_written:
                published_results.append({
                    'course_code': result.course.course_code,
                    'course_title': result.course.course_title,
                    'session_written': result.course.session_written, # Or schedule.session_written
                    'ca_score': result.ca_score,
                    'exam_score': result.exam_score,
                    'total_score': result.total_score,
                    'grade': result.grade,
                    'publish_start': schedule.publish_start,
                    'publish_end': schedule.publish_end
                })
    
    # Sort results for better display, e.g., by course code or session
    published_results.sort(key=lambda x: (x['session_written'], x['course_code']))

    return render_template('student_view_results.html', results=published_results, user=user) # Pass 'user'




@app.route('/admin/all-admins')
def all_admins():
    if 'admin_id' not in session:
        flash('Please login first!', 'warning')
        return redirect(url_for('admin_login'))
    
    """
    Route to display a list of all administrators.
    """
    # Fetch all admins from the database
    admins = Admin.query.all()
    return render_template('all_admins.html', admins=admins)

@app.route('/admin/delete-admin/<int:admin_id>', methods=['POST'])
def delete_admin(admin_id):
    """
    Route to delete an administrator account.
    This route should be a POST request for security.
    """
    # Prevent an admin from deleting their own account
    if session.get('admin_id') == admin_id:
        flash("You cannot delete your own account!", 'danger')
        return redirect(url_for('all_admins'))

    admin_to_delete = Admin.query.get_or_404(admin_id)

    try:
        # Delete related activity logs first (optional, but good practice)
        AdminActivityLog.query.filter_by(admin_id=admin_id).delete()
        db.session.delete(admin_to_delete)
        db.session.commit()
        flash(f"Administrator '{admin_to_delete.username}' and their activities have been deleted.", 'success')
    except Exception as e:
        db.session.rollback()
        flash(f"An error occurred while deleting the administrator: {str(e)}", 'danger')

    return redirect(url_for('all_admins'))

@app.route('/admin/admin-activities')
def admin_activities():
    if 'admin_id' not in session:
        flash('Please login first!', 'warning')
        return redirect(url_for('admin_login'))
    
    """
    Route to display the activity logs of all administrators.
    """
    # Fetch all activity logs, ordered from newest to oldest
    activities = AdminActivityLog.query.order_by(AdminActivityLog.timestamp.desc()).all()
    return render_template('admin_activities.html', activities=activities)


def log_admin_activity(admin_id, action):
    if 'admin_id' not in session:
        flash('Please login first!', 'warning')
        return redirect(url_for('admin_login'))
    
    """
    Helper function to log an admin's action.
    """
    log_entry = AdminActivityLog(admin_id=admin_id, action=action)
    db.session.add(log_entry)
    db.session.commit()


@app.route('/view_dues')
def view_dues():
    if 'admin_id' not in session:
        flash('Please login first!', 'warning')
        return redirect(url_for('admin_login'))
    
    """
    Renders a page displaying all students who have paid their departmental dues.
    The page fetches all records from the AdminAddDues model and passes them
    to the HTML template.
    """
    # Query all dues records from the database
    # Assuming AdminAddDues is the correct model for this data
    dues_paid = AdminAddDues.query.all()
    
    # Render the HTML template and pass the fetched data
    return render_template('view_dues.html', dues=dues_paid)



@app.route('/voted_students')
def voted_students():
    if 'admin_id' not in session:
        flash('Please login first!', 'warning')
        return redirect(url_for('admin_login'))
    
    """
    Renders a page displaying all users who have already voted.
    It fetches all vote records and their associated user details.
    """
    # Eagerly load the 'user' relationship to avoid N+1 query problem
    # This fetches all votes and their related user objects in one query
    voted_records = Vote.query.options(db.joinedload(Vote.user)).all()

    # The voted_records will contain Vote objects, each with a 'user' attribute
    return render_template('voted_students.html', votes=voted_records)



















# --- NEW LECTURER ROUTES ---

@app.route('/lecturer/signup', methods=['GET', 'POST'])
def lecturer_signup():
    if request.method == 'POST':
        data = request.get_json()
        full_name = data.get('full_name').strip()
        email = data.get('email').strip()
        password = data.get('password')
        confirm_password = data.get('confirm_password')
        department = data.get('department').strip()
        staff_id = data.get('staff_id').strip()
        phone_number = data.get('phone_number', '').strip()
        state_of_origin = data.get('state_of_origin', '').strip()
        lga = data.get('lga', '').strip()
        home_address = data.get('home_address', '').strip()

        # Server-side validation
        if not all([full_name, email, password, confirm_password, department, staff_id]):
            return jsonify({'message': 'Please fill in all required fields.'}), 400

        if password != confirm_password:
            return jsonify({'message': 'Passwords do not match.'}), 400

        if len(password) < 6: # Basic password length check
            return jsonify({'message': 'Password must be at least 6 characters long.'}), 400

        if '@' not in email or '.' not in email: # Basic email format check
            return jsonify({'message': 'Invalid email format.'}), 400

        # Check if email or staff_id already exists
        try:
            if Lecturer.query.filter_by(email=email).first():
                return jsonify({'message': 'Email already registered.'}), 400
        except Exception as e:
                    print(e)
        try:
            if Lecturer.query.filter_by(staff_id=staff_id).first():
                return jsonify({'message': 'Staff ID already registered.'}), 400
        except Exception as e:
                    print(e)

        # Hash the password
        hashed_password = generate_password_hash(password)

        try:
            new_lecturer = Lecturer(
                full_name=full_name,
                email=email,
                password_hash=hashed_password,
                department=department,
                staff_id=staff_id,
                phone_number=phone_number,
                state_of_origin=state_of_origin,
                lga=lga,
                home_address=home_address
            )
            db.session.add(new_lecturer)
            db.session.commit()
            return jsonify({'message': 'Lecturer registered successfully! You can now log in.'}), 201
        except Exception as e:
            db.session.rollback()
            print(f"Error during lecturer signup: {e}")
            return jsonify({'message': 'An error occurred during registration.'}), 500

    return render_template('lecturer_signup.html')

@app.route('/lecturer/login', methods=['GET', 'POST'])
def lecturer_login():
    if current_user.is_authenticated:
        flash('You are already logged in!', 'info')
        return redirect(url_for('lecturer_dashboard')) # Redirect if already logged in

    if request.method == 'POST':
        data = request.get_json()
        email_or_staff_id = data.get('email_or_staff_id').strip()
        password = data.get('password')

        if not email_or_staff_id or not password:
            return jsonify({'message': 'Please enter your email/staff ID and password.'}), 400

        # Try to find lecturer by email or staff_id
        lecturer = Lecturer.query.filter(
            (Lecturer.email == email_or_staff_id) | (Lecturer.staff_id == email_or_staff_id)
        ).first()

        if lecturer and check_password_hash(lecturer.password_hash, password):
            login_user(lecturer) # Log the lecturer in using Flask-Login
            flash('Logged in successfully!', 'success')
            return jsonify({'message': 'Login successful!', 'redirect_url': url_for('lecturer_dashboard')}), 200
        else:
            return jsonify({'message': 'Invalid email/staff ID or password.'}), 401

    return render_template('lecturer_login.html')

@app.route('/lecturer/logout')
@login_required # Only logged-in lecturers can log out
def lecturer_logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('lecturer_login'))




@app.route('/admin-dashboard')
def lecturer_dashboard():
    if 'lecturer_id' not in session:
        flash('Please login first!', 'warning')
        return redirect(url_for('admin_login'))
    lecturer = Lecturer.query.get(session['lecturer_login'])
    flash('Admin registered successfully!.', 'success')
    lecturer = lecturer.query.get(session['lecturer_id'])

    return render_template('admin.html',lecturer=lecturer)

















with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(debug=True)