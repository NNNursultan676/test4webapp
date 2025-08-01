import os
import json
import logging
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from werkzeug.middleware.proxy_fix import ProxyFix
from translations import get_translation, get_companies, TRANSLATIONS

# Configure logging
logging.basicConfig(level=logging.DEBUG)

# Create the app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "dev-secret-key-change-in-production")
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

def load_rooms():
    """Load rooms data from JSON file"""
    try:
        with open('data/rooms.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        logging.error("Rooms data file not found")
        return []

def load_bookings():
    """Load bookings data from JSON file"""
    try:
        with open('data/bookings.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        logging.debug("Bookings file not found, creating empty bookings")
        return []

def save_bookings(bookings):
    """Save bookings data to JSON file"""
    try:
        with open('data/bookings.json', 'w') as f:
            json.dump(bookings, f, indent=2)
        return True
    except Exception as e:
        logging.error(f"Error saving bookings: {e}")
        return False

def load_users():
    """Load users data from JSON file"""
    try:
        with open('data/users.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        logging.debug("Users file not found, creating empty users")
        return {}

def save_users(users):
    """Save users data to JSON file"""
    try:
        with open('data/users.json', 'w') as f:
            json.dump(users, f, indent=2)
        return True
    except Exception as e:
        logging.error(f"Error saving users: {e}")
        return False

def get_user_lang():
    """Get user's preferred language"""
    return session.get('lang', 'ru')

def is_user_registered():
    """Check if current user is registered"""
    return 'user_name' in session and 'user_company' in session

def is_room_available(room_id, date, start_time, end_time):
    """Check if a room is available for the given time slot"""
    bookings = load_bookings()
    
    for booking in bookings:
        if (booking['room_id'] == room_id and 
            booking['date'] == date and
            booking['status'] == 'confirmed'):
            
            # Check for time overlap
            booking_start = datetime.strptime(booking['start_time'], '%H:%M').time()
            booking_end = datetime.strptime(booking['end_time'], '%H:%M').time()
            slot_start = datetime.strptime(start_time, '%H:%M').time()
            slot_end = datetime.strptime(end_time, '%H:%M').time()
            
            # Check if there's any overlap
            if not (slot_end <= booking_start or slot_start >= booking_end):
                return False
    
    return True

def get_room_status(room_id):
    """Get current status of a room (available/occupied)"""
    now = datetime.now()
    current_date = now.strftime('%Y-%m-%d')
    current_time = now.strftime('%H:%M')
    
    bookings = load_bookings()
    
    for booking in bookings:
        if (booking['room_id'] == room_id and 
            booking['date'] == current_date and
            booking['status'] == 'confirmed'):
            
            if booking['start_time'] <= current_time <= booking['end_time']:
                return 'occupied'
    
    return 'available'

@app.context_processor
def inject_globals():
    """Inject global template variables"""
    lang = get_user_lang()
    return {
        'get_translation': lambda key, default=None: get_translation(lang, key, default),
        'lang': lang,
        'companies': get_companies(),
        'user_name': session.get('user_name'),
        'user_company': session.get('user_company'),
        'is_registered': is_user_registered()
    }

@app.route('/set_language/<lang>')
def set_language(lang):
    """Set user's preferred language"""
    if lang in TRANSLATIONS:
        session['lang'] = lang
    return redirect(request.referrer or url_for('index'))

@app.route('/')
def index():
    """Main page showing room availability"""
    # Check if user is registered, if not redirect to registration
    if not is_user_registered():
        return redirect(url_for('register'))
    
    rooms = load_rooms()
    
    # Add current status to each room
    for room in rooms:
        room['current_status'] = get_room_status(room['id'])
    
    today = datetime.now().strftime('%Y-%m-%d')
    return render_template('index.html', rooms=rooms, today=today)

@app.route('/register', methods=['GET', 'POST'])
def register():
    """User registration page"""
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        company = request.form.get('company', '').strip()
        lang = request.form.get('lang', 'en')
        
        if not name:
            flash(get_translation(lang, 'name_required'), 'error')
            return render_template('register.html')
        
        if not company:
            flash(get_translation(lang, 'company_required'), 'error')
            return render_template('register.html')
        
        # Save user info to session
        session['user_name'] = name
        session['user_company'] = company
        session['lang'] = lang
        
        # Save to users database (optional for persistence)
        users = load_users()
        user_id = f"{name}_{company}_{datetime.now().timestamp()}"
        users[user_id] = {
            'name': name,
            'company': company,
            'registered_at': datetime.now().isoformat()
        }
        save_users(users)
        
        return redirect(url_for('index'))
    
    return render_template('register.html')

@app.route('/profile', methods=['GET', 'POST'])
def profile():
    """User profile page"""
    if not is_user_registered():
        return redirect(url_for('register'))
    
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        company = request.form.get('company', '').strip()
        
        if name and company:
            session['user_name'] = name
            session['user_company'] = company
            flash(get_translation(get_user_lang(), 'profile_updated', 'Profile updated successfully'), 'success')
    
    return render_template('profile.html')

@app.route('/book/<int:room_id>')
def book_room(room_id):
    """Room booking page"""
    if not is_user_registered():
        return redirect(url_for('register'))
    
    rooms = load_rooms()
    room = next((r for r in rooms if r['id'] == room_id), None)
    
    if not room:
        flash(get_translation(get_user_lang(), 'room_not_found', 'Room not found'), 'error')
        return redirect(url_for('index'))
    
    today = datetime.now().strftime('%Y-%m-%d')
    return render_template('book_room.html', room=room, today=today)

@app.route('/book/<int:room_id>', methods=['POST'])
def process_booking(room_id):
    """Process room booking form submission"""
    if not is_user_registered():
        return redirect(url_for('register'))
    
    rooms = load_rooms()
    room = next((r for r in rooms if r['id'] == room_id), None)
    lang = get_user_lang()
    
    if not room:
        flash(get_translation(lang, 'room_not_found', 'Room not found'), 'error')
        return redirect(url_for('index'))
    
    # Get form data
    date = request.form.get('date')
    start_time = request.form.get('start_time')
    end_time = request.form.get('end_time')
    purpose = request.form.get('purpose', '')
    
    # Use session data for user info
    user_name = session.get('user_name')
    user_company = session.get('user_company')
    
    # Validate form data
    if not all([date, start_time, end_time]):
        flash(get_translation(lang, 'fill_required_fields', 'Please fill in all required fields'), 'error')
        return render_template('book_room.html', room=room, today=datetime.now().strftime('%Y-%m-%d'))
    
    # Validate date is not in the past
    if date:
        booking_date = datetime.strptime(date, '%Y-%m-%d').date()
        if booking_date < datetime.now().date():
            flash(get_translation(lang, 'no_past_dates', 'Cannot book rooms for past dates'), 'error')
            return render_template('book_room.html', room=room, today=datetime.now().strftime('%Y-%m-%d'))
    
    # Validate time range
    if start_time and end_time:
        start_dt = datetime.strptime(start_time, '%H:%M').time()
        end_dt = datetime.strptime(end_time, '%H:%M').time()
    
        if start_dt >= end_dt:
            flash(get_translation(lang, 'invalid_time'), 'error')
            return render_template('book_room.html', room=room, today=datetime.now().strftime('%Y-%m-%d'))
    
    # Check availability
    if not is_room_available(room_id, date, start_time, end_time):
        flash(get_translation(lang, 'room_unavailable'), 'error')
        return render_template('book_room.html', room=room, today=datetime.now().strftime('%Y-%m-%d'))
    
    # Create booking
    bookings = load_bookings()
    new_booking = {
        'id': len(bookings) + 1,
        'room_id': room_id,
        'room_name': room['name'],
        'date': date,
        'start_time': start_time,
        'end_time': end_time,
        'user_name': user_name,
        'user_company': user_company,
        'purpose': purpose,
        'status': 'confirmed',
        'created_at': datetime.now().isoformat()
    }
    
    bookings.append(new_booking)
    
    if save_bookings(bookings):
        flash(get_translation(lang, 'booking_successful'), 'success')
        return redirect(url_for('index'))
    else:
        flash(get_translation(lang, 'booking_error'), 'error')
        return render_template('book_room.html', room=room, today=datetime.now().strftime('%Y-%m-%d'))

@app.route('/api/room-availability/<int:room_id>')
def room_availability_api(room_id):
    """API endpoint for checking room availability"""
    date = request.args.get('date')
    if not date:
        return jsonify({'error': 'Date parameter required'}), 400
    
    bookings = load_bookings()
    room_bookings = [b for b in bookings if b['room_id'] == room_id and b['date'] == date and b['status'] == 'confirmed']
    
    occupied_slots = []
    for booking in room_bookings:
        occupied_slots.append({
            'start': booking['start_time'],
            'end': booking['end_time'],
            'user': booking['user_name'],
            'purpose': booking.get('purpose', '')
        })
    
    return jsonify({'occupied_slots': occupied_slots})

@app.route('/schedule/<int:room_id>')
def room_schedule(room_id):
    """Show room schedule for a specific date"""
    if not is_user_registered():
        return redirect(url_for('register'))
    
    date = request.args.get('date', datetime.now().strftime('%Y-%m-%d'))
    rooms = load_rooms()
    room = next((r for r in rooms if r['id'] == room_id), None)
    
    if not room:
        flash(get_translation(get_user_lang(), 'room_not_found', 'Room not found'), 'error')
        return redirect(url_for('index'))
    
    bookings = load_bookings()
    room_bookings = [b for b in bookings if b['room_id'] == room_id and b['date'] == date and b['status'] == 'confirmed']
    room_bookings.sort(key=lambda x: x['start_time'])
    
    return render_template('schedule.html', room=room, bookings=room_bookings, selected_date=date)

@app.route('/api/schedule/<int:room_id>')
def api_room_schedule(room_id):
    """API endpoint for room schedule"""
    date = request.args.get('date', datetime.now().strftime('%Y-%m-%d'))
    bookings = load_bookings()
    room_bookings = [b for b in bookings if b['room_id'] == room_id and b['date'] == date and b['status'] == 'confirmed']
    room_bookings.sort(key=lambda x: x['start_time'])
    
    return jsonify({'bookings': room_bookings})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
