import os
import secrets
from functools import wraps
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_socketio import SocketIO, emit, join_room, leave_room
from werkzeug.security import generate_password_hash, check_password_hash

from database import db

# Initialize Flask App
app = Flask(__name__)
app.config['SECRET_KEY'] = 'chatsphere_secure_secret_key_2026_x99'

# Initialize Flask-SocketIO
socketio = SocketIO(app, cors_allowed_origins="*")

# Initialize Database Schema & Migrations on Startup
db.init_db()


# Login Required Decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            flash('Please log in to access ChatSphere.', 'info')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


def is_room_unlocked(room):
    """Check if a room is unlocked for the current user session."""
    if not room or not room.get('password_hash'):
        return True
    if room.get('created_by') == session.get('username'):
        return True
    unlocked_rooms = session.get('unlocked_rooms', [])
    return room.get('id') in unlocked_rooms


# ==============================================================================
# HTTP Routes & Authentication
# ==============================================================================

@app.route('/')
def index():
    """Root route redirecting to rooms if authenticated, else login."""
    if 'username' in session:
        return redirect(url_for('rooms_list'))
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    """User authentication login route."""
    if 'username' in session:
        return redirect(url_for('rooms_list'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        if not username or not password:
            flash('Please provide both username and password.', 'error')
            return render_template('login.html')

        user = db.get_user_by_username(username)
        if user and check_password_hash(user['password_hash'], password):
            session.clear()
            session['username'] = user['username']
            session['user_id'] = user['id']
            session['unlocked_rooms'] = []
            flash(f'Welcome back, {user["username"]}!', 'success')
            return redirect(url_for('rooms_list'))
        else:
            flash('Invalid username or password. Please try again.', 'error')

    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    """New user registration route."""
    if 'username' in session:
        return redirect(url_for('rooms_list'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')

        if not username or len(username) < 3 or len(username) > 20:
            flash('Username must be between 3 and 20 characters.', 'error')
            return render_template('register.html')

        if not password or len(password) < 4:
            flash('Password must be at least 4 characters long.', 'error')
            return render_template('register.html')

        if password != confirm_password:
            flash('Passwords do not match. Please re-enter.', 'error')
            return render_template('register.html')

        existing_user = db.get_user_by_username(username)
        if existing_user:
            flash(f'Username "{username}" is already taken.', 'error')
            return render_template('register.html')

        password_hash = generate_password_hash(password)
        user_id = db.create_user(username, password_hash)

        if user_id:
            session.clear()
            session['username'] = username
            session['user_id'] = user_id
            session['unlocked_rooms'] = []
            flash('Account created successfully! Welcome to ChatSphere.', 'success')
            return redirect(url_for('rooms_list'))
        else:
            flash('Failed to create account. Username already exists.', 'error')

    return render_template('register.html')


@app.route('/logout')
def logout():
    """Clear session and log out user."""
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))


# Uploads configuration for profile pictures
UPLOAD_FOLDER = os.path.join(app.static_folder, 'uploads', 'profile_pics')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route('/api/check-username')
@login_required
def api_check_username():
    """API endpoint for live username availability checking in edit mode."""
    username = request.args.get('username', '').strip()
    current_user_id = session.get('user_id')

    if not username or len(username) < 3 or len(username) > 20:
        return jsonify({'available': False, 'reason': 'Username must be 3-20 characters long.'})

    exists = db.check_username_exists(username, exclude_user_id=current_user_id)
    if exists:
        return jsonify({'available': False, 'reason': 'Username is already taken.'})

    return jsonify({'available': True, 'reason': 'Username is available.'})


@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    """User profile viewing and editing route."""
    user = db.get_user_by_username(session.get('username'))
    if not user:
        flash('User profile not found.', 'error')
        return redirect(url_for('login'))

    user_dict = dict(user)

    if request.method == 'POST':
        action = request.form.get('action')

        # Handle Account Password Change
        if action == 'change_password':
            new_password = request.form.get('new_password', '').strip()
            confirm_password = request.form.get('confirm_password', '').strip()
            if new_password:
                if len(new_password) < 4:
                    flash('New password must be at least 4 characters long.', 'error')
                elif new_password != confirm_password:
                    flash('Passwords do not match.', 'error')
                else:
                    new_hash = generate_password_hash(new_password)
                    conn = db.get_db_connection()
                    cursor = conn.cursor()
                    cursor.execute('UPDATE users SET password_hash = ? WHERE id = ?', (new_hash, user_dict['id']))
                    conn.commit()
                    conn.close()
                    flash('Password updated successfully!', 'success')
            return redirect(url_for('profile'))

        # Handle Full Profile Edit (Username, Mobile, DOB, Avatar Picture)
        new_username = request.form.get('username', '').strip()
        mobile = request.form.get('mobile', '').strip()
        dob = request.form.get('dob', '').strip()

        # 1. Validate Username
        if not new_username or len(new_username) < 3 or len(new_username) > 20:
            flash('Username must be between 3 and 20 characters long.', 'error')
            return redirect(url_for('profile'))

        if db.check_username_exists(new_username, exclude_user_id=user_dict['id']):
            flash('Username is already taken. Please choose another.', 'error')
            return redirect(url_for('profile'))

        # 2. Validate & Normalize Mobile Number
        if mobile:
            clean_mobile = mobile.replace(' ', '').replace('-', '')
            if db.check_mobile_exists(clean_mobile, exclude_user_id=user_dict['id']):
                flash('Mobile number is already registered to another account.', 'error')
                return redirect(url_for('profile'))
            mobile = clean_mobile

        # 3. Validate Date of Birth
        if dob:
            try:
                dob_date = datetime.strptime(dob, '%Y-%m-%d').date()
                if dob_date > datetime.now().date():
                    flash('Date of birth cannot be in the future.', 'error')
                    return redirect(url_for('profile'))
            except ValueError:
                flash('Invalid date of birth format.', 'error')
                return redirect(url_for('profile'))

        # 4. Handle Profile Picture Upload
        profile_pic_url = user_dict.get('profile_pic')
        if 'profile_pic_file' in request.files:
            file = request.files['profile_pic_file']
            if file and file.filename != '':
                if not allowed_file(file.filename):
                    flash('Invalid image format. Allowed formats: JPG, JPEG, PNG, WEBP.', 'error')
                    return redirect(url_for('profile'))

                file.seek(0, os.SEEK_END)
                size = file.tell()
                file.seek(0)
                if size > MAX_FILE_SIZE:
                    flash('Image file size exceeds 5MB limit.', 'error')
                    return redirect(url_for('profile'))

                ext = file.filename.rsplit('.', 1)[1].lower()
                secure_name = f"user_{user_dict['id']}_{secrets.token_hex(8)}.{ext}"
                file_path = os.path.join(UPLOAD_FOLDER, secure_name)
                file.save(file_path)
                profile_pic_url = f"/static/uploads/profile_pics/{secure_name}"

        db.update_user_profile(
            user_id=user_dict['id'],
            username=new_username,
            mobile=mobile,
            dob=dob,
            profile_pic=profile_pic_url
        )

        session['username'] = new_username
        flash('✓ Profile updated successfully.', 'success')
        return redirect(url_for('profile'))

    raw_mobile = user_dict.get('mobile') or ''
    masked_mobile = 'Private'
    if raw_mobile:
        if len(raw_mobile) >= 10:
            masked_mobile = f"{raw_mobile[:3]} ********{raw_mobile[-4:]}"
        else:
            masked_mobile = raw_mobile

    calculated_age = db.calculate_age(user_dict.get('dob'))

    return render_template(
        'profile.html',
        user=user_dict,
        username=session.get('username'),
        masked_mobile=masked_mobile,
        calculated_age=calculated_age
    )


@app.route('/rooms')
@login_required
def rooms_list():
    """Display available chat rooms."""
    rooms = db.get_all_rooms()
    unlocked_rooms = session.get('unlocked_rooms', [])
    current_user = db.get_user_by_username(session.get('username'))
    user_profile_pic = current_user['profile_pic'] if current_user else None

    return render_template(
        'rooms.html',
        username=session.get('username'),
        user_profile_picture=user_profile_pic,
        rooms=rooms,
        unlocked_rooms=unlocked_rooms
    )


@app.route('/rooms/create', methods=['POST'])
@login_required
def create_room_route():
    """Create a new password-protected chat room."""
    room_name = request.form.get('room_name', '').strip()
    room_password = request.form.get('room_password', '')
    confirm_password = request.form.get('confirm_password', '')

    if not room_name:
        flash('Room name cannot be empty.', 'error')
        return redirect(url_for('rooms_list'))

    if not room_password or len(room_password) < 4:
        flash('Room password must be at least 4 characters long.', 'error')
        return redirect(url_for('rooms_list'))

    if room_password != confirm_password:
        flash('Room passwords do not match.', 'error')
        return redirect(url_for('rooms_list'))

    existing = db.get_room_by_name(room_name)
    if existing:
        flash(f'Room "{room_name}" already exists.', 'error')
        return redirect(url_for('rooms_list'))

    password_hash = generate_password_hash(room_password)
    room_id = db.create_room(room_name, created_by=session.get('username'), password_hash=password_hash)

    if room_id:
        unlocked = session.get('unlocked_rooms', [])
        if room_id not in unlocked:
            unlocked.append(room_id)
            session['unlocked_rooms'] = unlocked

        flash(f'Room "#{room_name}" created successfully with password protection!', 'success')
        return redirect(url_for('chat_room', room_id=room_id))
    else:
        flash('Failed to create room.', 'error')
        return redirect(url_for('rooms_list'))


@app.route('/rooms/<int:room_id>/verify-password', methods=['POST'])
@login_required
def verify_room_password_route(room_id):
    """Server-side verification of room password."""
    room = db.get_room_by_id(room_id)
    if not room:
        return jsonify({'success': False, 'message': 'Room not found.'}), 404

    password = request.form.get('password', '') or (request.json.get('password') if request.is_json else '')
    if not password:
        return jsonify({'success': False, 'message': 'Password is required.'}), 400

    if db.verify_room_password(room_id, password):
        unlocked = session.get('unlocked_rooms', [])
        if room_id not in unlocked:
            unlocked.append(room_id)
            session['unlocked_rooms'] = unlocked
        return jsonify({'success': True, 'redirect_url': url_for('chat_room', room_id=room_id)})
    else:
        return jsonify({'success': False, 'message': 'Incorrect room password.'}), 401


@app.route('/join/invite/<token>')
@login_required
def join_invite_route(token):
    """Resolve QR/URL invite token to room."""
    room = db.get_room_by_invite_token(token)
    if not room:
        flash('This room invitation is no longer valid or expired.', 'error')
        return redirect(url_for('rooms_list'))

    if is_room_unlocked(room):
        return redirect(url_for('chat_room', room_id=room['id']))

    return redirect(url_for('rooms_list', join_token=token))


@app.route('/api/invite/<token>')
@login_required
def api_invite_info(token):
    """API endpoint to get room metadata from invite token for QR scanner preview."""
    room = db.get_room_by_invite_token(token)
    if not room:
        return jsonify({'success': False, 'message': 'Invalid or expired QR code invitation.'}), 404

    return jsonify({
        'success': True,
        'room': {
            'id': room['id'],
            'name': room['name'],
            'created_by': room['created_by'],
            'has_password': bool(room['password_hash'])
        }
    })


@app.route('/rooms/<int:room_id>/regenerate-invite', methods=['POST'])
@login_required
def regenerate_invite_route(room_id):
    """Regenerate room cryptographic invite token (room owner only)."""
    room = db.get_room_by_id(room_id)
    if not room:
        return jsonify({'success': False, 'message': 'Room not found.'}), 404

    if room['created_by'] != session.get('username'):
        return jsonify({'success': False, 'message': 'Only the room creator can regenerate invitations.'}), 403

    new_token = db.regenerate_room_invite(room_id)
    invite_url = request.host_url.rstrip('/') + url_for('join_invite_route', token=new_token)
    return jsonify({
        'success': True,
        'new_token': new_token,
        'invite_url': invite_url,
        'message': 'Invitation regenerated. Previous QR codes are now invalid.'
    })


@app.route('/rooms/<int:room_id>/change-password', methods=['POST'])
@login_required
def change_room_password_route(room_id):
    """Change room password (room owner only)."""
    room = db.get_room_by_id(room_id)
    if not room:
        return jsonify({'success': False, 'message': 'Room not found.'}), 404

    if room['created_by'] != session.get('username'):
        return jsonify({'success': False, 'message': 'Only the room creator can change the room password.'}), 403

    data = request.form if request.form else (request.json if request.is_json else {})
    new_password = data.get('new_password', '')
    confirm_password = data.get('confirm_password', '')

    if not new_password or len(new_password) < 4:
        return jsonify({'success': False, 'message': 'Password must be at least 4 characters long.'}), 400

    if new_password != confirm_password:
        return jsonify({'success': False, 'message': 'Passwords do not match.'}), 400

    new_hash = generate_password_hash(new_password)
    db.update_room_password(room_id, new_hash)

    if data.get('regenerate_invite') == 'true' or data.get('regenerate_invite') is True:
        db.regenerate_room_invite(room_id)

    return jsonify({'success': True, 'message': 'Room password updated successfully!'})


@app.route('/chat/<int:room_id>')
@login_required
def chat_room(room_id):
    """Protected chat page for a specific room."""
    room = db.get_room_by_id(room_id)
    if not room:
        flash('Chat room not found.', 'error')
        return redirect(url_for('rooms_list'))

    if not is_room_unlocked(room):
        flash('Password verification required to enter this private room.', 'error')
        return redirect(url_for('rooms_list', room_id=room_id))

    all_rooms = db.get_all_rooms()
    invite_url = request.host_url.rstrip('/') + url_for('join_invite_route', token=room['invite_token'])
    current_user = db.get_user_by_username(session.get('username'))
    user_profile_pic = current_user['profile_pic'] if current_user else None

    return render_template(
        'chat.html',
        username=session.get('username'),
        user_profile_picture=user_profile_pic,
        room=room,
        rooms=all_rooms,
        invite_url=invite_url
    )


# ==============================================================================
# Socket.IO Event Handlers & Presence
# ==============================================================================

room_active_users = {}
sid_to_user = {}


def get_room_members(room_id):
    """Get list of unique usernames currently active in a room."""
    if room_id not in room_active_users:
        return []
    return sorted(list(set(room_active_users[room_id].values())))


def broadcast_room_members(room_id):
    """Broadcast the current list of online members to the room."""
    members = get_room_members(room_id)
    emit('room_members', {'members': members, 'count': len(members)}, to=room_id)


@socketio.on('connect')
def handle_connect():
    """Handle Socket.IO connection event."""
    username = session.get('username')
    if not username:
        return False  # Reject unauthenticated socket connection
    print(f"[Socket.IO] Client connected: {username} ({request.sid})")


@socketio.on('join')
def handle_join(data):
    """Handle user joining a specific chat room."""
    username = session.get('username', data.get('username', 'Anonymous'))
    room_id = int(data.get('room_id'))

    room = db.get_room_by_id(room_id)
    if not room:
        return

    if not is_room_unlocked(room):
        emit('error', {'message': 'Unauthorized. Password required.'}, to=request.sid)
        return

    join_room(room_id)

    if room_id not in room_active_users:
        room_active_users[room_id] = {}
    room_active_users[room_id][request.sid] = username
    sid_to_user[request.sid] = (room_id, username)

    print(f"[Socket.IO] User '{username}' joined room #{room['name']} (ID: {room_id})")

    system_msg = db.save_message(room_id, 'System', f"{username} joined the room")
    emit('new_message', system_msg, to=room_id)

    broadcast_room_members(room_id)

    history = db.get_room_messages(room_id, limit=100)
    emit('history', history, to=request.sid)


@socketio.on('send_message')
def handle_send_message(data):
    """Handle real-time message exchange."""
    username = session.get('username', data.get('username', 'Anonymous'))
    room_id = int(data.get('room_id'))
    message_text = data.get('message', '').strip()

    if not message_text:
        return

    msg_obj = db.save_message(room_id, username, message_text)

    emit('new_message', msg_obj, to=room_id)


@socketio.on('leave')
def handle_leave(data):
    """Handle user explicitly leaving a chat room."""
    username = session.get('username', data.get('username', 'Anonymous'))
    room_id = int(data.get('room_id'))

    leave_room(room_id)

    if room_id in room_active_users and request.sid in room_active_users[room_id]:
        del room_active_users[room_id][request.sid]
    if request.sid in sid_to_user:
        del sid_to_user[request.sid]

    print(f"[Socket.IO] User '{username}' left room ID: {room_id}")

    system_msg = db.save_message(room_id, 'System', f"{username} left the room")
    emit('new_message', system_msg, to=room_id)

    broadcast_room_members(room_id)


@socketio.on('disconnect')
def handle_disconnect():
    """Handle socket disconnection gracefully."""
    if request.sid in sid_to_user:
        room_id, username = sid_to_user.pop(request.sid)
        if room_id in room_active_users and request.sid in room_active_users[room_id]:
            del room_active_users[room_id][request.sid]
            broadcast_room_members(room_id)
        print(f"[Socket.IO] Client disconnected: {username} ({request.sid})")
    else:
        print(f"[Socket.IO] Unregistered socket disconnected: {request.sid}")


import os
import secrets
from functools import wraps
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_socketio import SocketIO, emit, join_room, leave_room
from werkzeug.security import generate_password_hash, check_password_hash

from database import db

# Initialize Flask App
app = Flask(__name__)
app.config['SECRET_KEY'] = 'chatsphere_secure_secret_key_2026_x99'

# Initialize Flask-SocketIO
socketio = SocketIO(app, cors_allowed_origins="*")

# Initialize Database Schema & Migrations on Startup
db.init_db()


# Login Required Decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            flash('Please log in to access ChatSphere.', 'info')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


def is_room_unlocked(room):
    """Check if a room is unlocked for the current user session."""
    if not room or not room.get('password_hash'):
        return True
    if room.get('created_by') == session.get('username'):
        return True
    unlocked_rooms = session.get('unlocked_rooms', [])
    return room.get('id') in unlocked_rooms


# ==============================================================================
# HTTP Routes & Authentication
# ==============================================================================

@app.route('/')
def index():
    """Root route redirecting to rooms if authenticated, else login."""
    if 'username' in session:
        return redirect(url_for('rooms_list'))
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    """User authentication login route."""
    if 'username' in session:
        return redirect(url_for('rooms_list'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        if not username or not password:
            flash('Please provide both username and password.', 'error')
            return render_template('login.html')

        user = db.get_user_by_username(username)
        if user and check_password_hash(user['password_hash'], password):
            session.clear()
            session['username'] = user['username']
            session['user_id'] = user['id']
            session['unlocked_rooms'] = []
            flash(f'Welcome back, {user["username"]}!', 'success')
            return redirect(url_for('rooms_list'))
        else:
            flash('Invalid username or password. Please try again.', 'error')

    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    """New user registration route."""
    if 'username' in session:
        return redirect(url_for('rooms_list'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')

        if not username or len(username) < 3 or len(username) > 20:
            flash('Username must be between 3 and 20 characters.', 'error')
            return render_template('register.html')

        if not password or len(password) < 4:
            flash('Password must be at least 4 characters long.', 'error')
            return render_template('register.html')

        if password != confirm_password:
            flash('Passwords do not match. Please re-enter.', 'error')
            return render_template('register.html')

        existing_user = db.get_user_by_username(username)
        if existing_user:
            flash(f'Username "{username}" is already taken.', 'error')
            return render_template('register.html')

        password_hash = generate_password_hash(password)
        user_id = db.create_user(username, password_hash)

        if user_id:
            session.clear()
            session['username'] = username
            session['user_id'] = user_id
            session['unlocked_rooms'] = []
            flash('Account created successfully! Welcome to ChatSphere.', 'success')
            return redirect(url_for('rooms_list'))
        else:
            flash('Failed to create account. Username already exists.', 'error')

    return render_template('register.html')


@app.route('/logout')
def logout():
    """Clear session and log out user."""
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))


# Uploads configuration for profile pictures
UPLOAD_FOLDER = os.path.join(app.static_folder, 'uploads', 'profile_pics')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route('/api/check-username')
@login_required
def api_check_username():
    """API endpoint for live username availability checking in edit mode."""
    username = request.args.get('username', '').strip()
    current_user_id = session.get('user_id')

    if not username or len(username) < 3 or len(username) > 20:
        return jsonify({'available': False, 'reason': 'Username must be 3-20 characters long.'})

    exists = db.check_username_exists(username, exclude_user_id=current_user_id)
    if exists:
        return jsonify({'available': False, 'reason': 'Username is already taken.'})

    return jsonify({'available': True, 'reason': 'Username is available.'})


@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    """User profile viewing and editing route."""
    user = db.get_user_by_username(session.get('username'))
    if not user:
        flash('User profile not found.', 'error')
        return redirect(url_for('login'))

    user_dict = dict(user)

    if request.method == 'POST':
        action = request.form.get('action')

        # Handle Account Password Change
        if action == 'change_password':
            new_password = request.form.get('new_password', '').strip()
            confirm_password = request.form.get('confirm_password', '').strip()
            if new_password:
                if len(new_password) < 4:
                    flash('New password must be at least 4 characters long.', 'error')
                elif new_password != confirm_password:
                    flash('Passwords do not match.', 'error')
                else:
                    new_hash = generate_password_hash(new_password)
                    conn = db.get_db_connection()
                    cursor = conn.cursor()
                    cursor.execute('UPDATE users SET password_hash = ? WHERE id = ?', (new_hash, user_dict['id']))
                    conn.commit()
                    conn.close()
                    flash('Password updated successfully!', 'success')
            return redirect(url_for('profile'))

        # Handle Full Profile Edit (Username, Mobile, DOB, Avatar Picture)
        new_username = request.form.get('username', '').strip()
        mobile = request.form.get('mobile', '').strip()
        dob = request.form.get('dob', '').strip()

        # 1. Validate Username
        if not new_username or len(new_username) < 3 or len(new_username) > 20:
            flash('Username must be between 3 and 20 characters long.', 'error')
            return redirect(url_for('profile'))

        if db.check_username_exists(new_username, exclude_user_id=user_dict['id']):
            flash('Username is already taken. Please choose another.', 'error')
            return redirect(url_for('profile'))

        # 2. Validate & Normalize Mobile Number
        if mobile:
            clean_mobile = mobile.replace(' ', '').replace('-', '')
            if db.check_mobile_exists(clean_mobile, exclude_user_id=user_dict['id']):
                flash('Mobile number is already registered to another account.', 'error')
                return redirect(url_for('profile'))
            mobile = clean_mobile

        # 3. Validate Date of Birth
        if dob:
            try:
                dob_date = datetime.strptime(dob, '%Y-%m-%d').date()
                if dob_date > datetime.now().date():
                    flash('Date of birth cannot be in the future.', 'error')
                    return redirect(url_for('profile'))
            except ValueError:
                flash('Invalid date of birth format.', 'error')
                return redirect(url_for('profile'))

        # 4. Handle Profile Picture Upload
        profile_pic_url = user_dict.get('profile_pic')
        if 'profile_pic_file' in request.files:
            file = request.files['profile_pic_file']
            if file and file.filename != '':
                if not allowed_file(file.filename):
                    flash('Invalid image format. Allowed formats: JPG, JPEG, PNG, WEBP.', 'error')
                    return redirect(url_for('profile'))

                file.seek(0, os.SEEK_END)
                size = file.tell()
                file.seek(0)
                if size > MAX_FILE_SIZE:
                    flash('Image file size exceeds 5MB limit.', 'error')
                    return redirect(url_for('profile'))

                ext = file.filename.rsplit('.', 1)[1].lower()
                secure_name = f"user_{user_dict['id']}_{secrets.token_hex(8)}.{ext}"
                file_path = os.path.join(UPLOAD_FOLDER, secure_name)
                file.save(file_path)
                profile_pic_url = f"/static/uploads/profile_pics/{secure_name}"

        db.update_user_profile(
            user_id=user_dict['id'],
            username=new_username,
            mobile=mobile,
            dob=dob,
            profile_pic=profile_pic_url
        )

        session['username'] = new_username
        flash('✓ Profile updated successfully.', 'success')
        return redirect(url_for('profile'))

    raw_mobile = user_dict.get('mobile') or ''
    masked_mobile = 'Private'
    if raw_mobile:
        if len(raw_mobile) >= 10:
            masked_mobile = f"{raw_mobile[:3]} ********{raw_mobile[-4:]}"
        else:
            masked_mobile = raw_mobile

    calculated_age = db.calculate_age(user_dict.get('dob'))

    return render_template(
        'profile.html',
        user=user_dict,
        username=session.get('username'),
        masked_mobile=masked_mobile,
        calculated_age=calculated_age
    )


@app.route('/rooms')
@login_required
def rooms_list():
    """Display available chat rooms."""
    rooms = db.get_all_rooms()
    unlocked_rooms = session.get('unlocked_rooms', [])
    current_user = db.get_user_by_username(session.get('username'))
    user_profile_pic = current_user['profile_pic'] if current_user else None

    return render_template(
        'rooms.html',
        username=session.get('username'),
        user_profile_picture=user_profile_pic,
        rooms=rooms,
        unlocked_rooms=unlocked_rooms
    )


@app.route('/rooms/create', methods=['POST'])
@login_required
def create_room_route():
    """Create a new password-protected chat room."""
    room_name = request.form.get('room_name', '').strip()
    room_password = request.form.get('room_password', '')
    confirm_password = request.form.get('confirm_password', '')

    if not room_name:
        flash('Room name cannot be empty.', 'error')
        return redirect(url_for('rooms_list'))

    if not room_password or len(room_password) < 4:
        flash('Room password must be at least 4 characters long.', 'error')
        return redirect(url_for('rooms_list'))

    if room_password != confirm_password:
        flash('Room passwords do not match.', 'error')
        return redirect(url_for('rooms_list'))

    existing = db.get_room_by_name(room_name)
    if existing:
        flash(f'Room "{room_name}" already exists.', 'error')
        return redirect(url_for('rooms_list'))

    password_hash = generate_password_hash(room_password)
    room_id = db.create_room(room_name, created_by=session.get('username'), password_hash=password_hash)

    if room_id:
        unlocked = session.get('unlocked_rooms', [])
        if room_id not in unlocked:
            unlocked.append(room_id)
            session['unlocked_rooms'] = unlocked

        flash(f'Room "#{room_name}" created successfully with password protection!', 'success')
        return redirect(url_for('chat_room', room_id=room_id))
    else:
        flash('Failed to create room.', 'error')
        return redirect(url_for('rooms_list'))


@app.route('/rooms/<int:room_id>/verify-password', methods=['POST'])
@login_required
def verify_room_password_route(room_id):
    """Server-side verification of room password."""
    room = db.get_room_by_id(room_id)
    if not room:
        return jsonify({'success': False, 'message': 'Room not found.'}), 404

    password = request.form.get('password', '') or (request.json.get('password') if request.is_json else '')
    if not password:
        return jsonify({'success': False, 'message': 'Password is required.'}), 400

    if db.verify_room_password(room_id, password):
        unlocked = session.get('unlocked_rooms', [])
        if room_id not in unlocked:
            unlocked.append(room_id)
            session['unlocked_rooms'] = unlocked
        return jsonify({'success': True, 'redirect_url': url_for('chat_room', room_id=room_id)})
    else:
        return jsonify({'success': False, 'message': 'Incorrect room password.'}), 401


@app.route('/join/invite/<token>')
@login_required
def join_invite_route(token):
    """Resolve QR/URL invite token to room."""
    room = db.get_room_by_invite_token(token)
    if not room:
        flash('This room invitation is no longer valid or expired.', 'error')
        return redirect(url_for('rooms_list'))

    if is_room_unlocked(room):
        return redirect(url_for('chat_room', room_id=room['id']))

    return redirect(url_for('rooms_list', join_token=token))


@app.route('/api/invite/<token>')
@login_required
def api_invite_info(token):
    """API endpoint to get room metadata from invite token for QR scanner preview."""
    room = db.get_room_by_invite_token(token)
    if not room:
        return jsonify({'success': False, 'message': 'Invalid or expired QR code invitation.'}), 404

    return jsonify({
        'success': True,
        'room': {
            'id': room['id'],
            'name': room['name'],
            'created_by': room['created_by'],
            'has_password': bool(room['password_hash'])
        }
    })


@app.route('/rooms/<int:room_id>/regenerate-invite', methods=['POST'])
@login_required
def regenerate_invite_route(room_id):
    """Regenerate room cryptographic invite token (room owner only)."""
    room = db.get_room_by_id(room_id)
    if not room:
        return jsonify({'success': False, 'message': 'Room not found.'}), 404

    if room['created_by'] != session.get('username'):
        return jsonify({'success': False, 'message': 'Only the room creator can regenerate invitations.'}), 403

    new_token = db.regenerate_room_invite(room_id)
    invite_url = request.host_url.rstrip('/') + url_for('join_invite_route', token=new_token)
    return jsonify({
        'success': True,
        'new_token': new_token,
        'invite_url': invite_url,
        'message': 'Invitation regenerated. Previous QR codes are now invalid.'
    })


@app.route('/rooms/<int:room_id>/change-password', methods=['POST'])
@login_required
def change_room_password_route(room_id):
    """Change room password (room owner only)."""
    room = db.get_room_by_id(room_id)
    if not room:
        return jsonify({'success': False, 'message': 'Room not found.'}), 404

    if room['created_by'] != session.get('username'):
        return jsonify({'success': False, 'message': 'Only the room creator can change the room password.'}), 403

    data = request.form if request.form else (request.json if request.is_json else {})
    new_password = data.get('new_password', '')
    confirm_password = data.get('confirm_password', '')

    if not new_password or len(new_password) < 4:
        return jsonify({'success': False, 'message': 'Password must be at least 4 characters long.'}), 400

    if new_password != confirm_password:
        return jsonify({'success': False, 'message': 'Passwords do not match.'}), 400

    new_hash = generate_password_hash(new_password)
    db.update_room_password(room_id, new_hash)

    if data.get('regenerate_invite') == 'true' or data.get('regenerate_invite') is True:
        db.regenerate_room_invite(room_id)

    return jsonify({'success': True, 'message': 'Room password updated successfully!'})


@app.route('/chat/<int:room_id>')
@login_required
def chat_room(room_id):
    """Protected chat page for a specific room."""
    room = db.get_room_by_id(room_id)
    if not room:
        flash('Chat room not found.', 'error')
        return redirect(url_for('rooms_list'))

    if not is_room_unlocked(room):
        flash('Password verification required to enter this private room.', 'error')
        return redirect(url_for('rooms_list', room_id=room_id))

    all_rooms = db.get_all_rooms()
    invite_url = request.host_url.rstrip('/') + url_for('join_invite_route', token=room['invite_token'])
    current_user = db.get_user_by_username(session.get('username'))
    user_profile_pic = current_user['profile_pic'] if current_user else None

    return render_template(
        'chat.html',
        username=session.get('username'),
        user_profile_picture=user_profile_pic,
        room=room,
        rooms=all_rooms,
        invite_url=invite_url
    )


# ==============================================================================
# Socket.IO Event Handlers & Presence
# ==============================================================================

room_active_users = {}
sid_to_user = {}


def get_room_members(room_id):
    """Get list of unique usernames currently active in a room."""
    if room_id not in room_active_users:
        return []
    return sorted(list(set(room_active_users[room_id].values())))


def broadcast_room_members(room_id):
    """Broadcast the current list of online members to the room."""
    members = get_room_members(room_id)
    emit('room_members', {'members': members, 'count': len(members)}, to=room_id)


@socketio.on('connect')
def handle_connect():
    """Handle Socket.IO connection event."""
    username = session.get('username')
    if not username:
        return False  # Reject unauthenticated socket connection
    print(f"[Socket.IO] Client connected: {username} ({request.sid})")


@socketio.on('join')
def handle_join(data):
    """Handle user joining a specific chat room."""
    username = session.get('username', data.get('username', 'Anonymous'))
    room_id = int(data.get('room_id'))

    room = db.get_room_by_id(room_id)
    if not room:
        return

    if not is_room_unlocked(room):
        emit('error', {'message': 'Unauthorized. Password required.'}, to=request.sid)
        return

    join_room(room_id)

    if room_id not in room_active_users:
        room_active_users[room_id] = {}
    room_active_users[room_id][request.sid] = username
    sid_to_user[request.sid] = (room_id, username)

    print(f"[Socket.IO] User '{username}' joined room #{room['name']} (ID: {room_id})")

    system_msg = db.save_message(room_id, 'System', f"{username} joined the room")
    emit('new_message', system_msg, to=room_id)

    broadcast_room_members(room_id)

    history = db.get_room_messages(room_id, limit=100)
    emit('history', history, to=request.sid)


@socketio.on('send_message')
def handle_send_message(data):
    """Handle real-time message exchange."""
    username = session.get('username', data.get('username', 'Anonymous'))
    room_id = int(data.get('room_id'))
    message_text = data.get('message', '').strip()

    if not message_text:
        return

    msg_obj = db.save_message(room_id, username, message_text)

    emit('new_message', msg_obj, to=room_id)


@socketio.on('leave')
def handle_leave(data):
    """Handle user explicitly leaving a chat room."""
    username = session.get('username', data.get('username', 'Anonymous'))
    room_id = int(data.get('room_id'))

    leave_room(room_id)

    if room_id in room_active_users and request.sid in room_active_users[room_id]:
        del room_active_users[room_id][request.sid]
    if request.sid in sid_to_user:
        del sid_to_user[request.sid]

    print(f"[Socket.IO] User '{username}' left room ID: {room_id}")

    system_msg = db.save_message(room_id, 'System', f"{username} left the room")
    emit('new_message', system_msg, to=room_id)

    broadcast_room_members(room_id)


@socketio.on('disconnect')
def handle_disconnect():
    """Handle socket disconnection gracefully."""
    if request.sid in sid_to_user:
        room_id, username = sid_to_user.pop(request.sid)
        if room_id in room_active_users and request.sid in room_active_users[room_id]:
            del room_active_users[room_id][request.sid]
            broadcast_room_members(room_id)
        print(f"[Socket.IO] Client disconnected: {username} ({request.sid})")
    else:
        print(f"[Socket.IO] Unregistered socket disconnected: {request.sid}")


if __name__ == '__main__':
    print("Starting ChatSphere Application on http://127.0.0.1:5000 ...")
    socketio.run(app, host='127.0.0.1', port=5000, debug=True)