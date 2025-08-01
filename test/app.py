import os
import json
import logging
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from werkzeug.middleware.proxy_fix import ProxyFix

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

@app.route('/')
def index():
    """Main page showing room availability"""
    rooms = load_rooms()
    
    # Add current status to each room
    for room in rooms:
        room['current_status'] = get_room_status(room['id'])
    
    today = datetime.now().strftime('%Y-%m-%d')
    return render_template('index.html', rooms=rooms, today=today)

@app.route('/book/<int:room_id>')
def book_room(room_id):
    """Room booking page"""
    rooms = load_rooms()
    room = next((r for r in rooms if r['id'] == room_id), None)
    
    if not room:
        flash('Room not found', 'error')
        return redirect(url_for('index'))
    
    today = datetime.now().strftime('%Y-%m-%d')
    return render_template('book_room.html', room=room, today=today)

@app.route('/book/<int:room_id>', methods=['POST'])
def process_booking(room_id):
    """Process room booking form submission"""
    rooms = load_rooms()
    room = next((r for r in rooms if r['id'] == room_id), None)
    
    if not room:
        flash('Room not found', 'error')
        return redirect(url_for('index'))
    
    # Get form data
    date = request.form.get('date')
    start_time = request.form.get('start_time')
    end_time = request.form.get('end_time')
    user_name = request.form.get('user_name')
    purpose = request.form.get('purpose', '')
    
    # Validate form data
    if not all([date, start_time, end_time, user_name]):
        flash('Please fill in all required fields', 'error')
        return render_template('book_room.html', room=room, today=datetime.now().strftime('%Y-%m-%d'))
    
    # Validate date is not in the past
    booking_date = datetime.strptime(date, '%Y-%m-%d').date()
    if booking_date < datetime.now().date():
        flash('Cannot book rooms for past dates', 'error')
        return render_template('book_room.html', room=room, today=datetime.now().strftime('%Y-%m-%d'))
    
    # Validate time range
    start_dt = datetime.strptime(start_time, '%H:%M').time()
    end_dt = datetime.strptime(end_time, '%H:%M').time()
    
    if start_dt >= end_dt:
        flash('End time must be after start time', 'error')
        return render_template('book_room.html', room=room, today=datetime.now().strftime('%Y-%m-%d'))
    
    # Check availability
    if not is_room_available(room_id, date, start_time, end_time):
        flash('Room is not available for the selected time slot', 'error')
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
        'purpose': purpose,
        'status': 'confirmed',
        'created_at': datetime.now().isoformat()
    }
    
    bookings.append(new_booking)
    
    if save_bookings(bookings):
        flash(f'Room {room["name"]} booked successfully for {date} from {start_time} to {end_time}', 'success')
        return redirect(url_for('index'))
    else:
        flash('Error saving booking. Please try again.', 'error')
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

@app.route('/my-bookings')
def my_bookings():
    """Show user's bookings (simplified - shows all bookings for demo)"""
    bookings = load_bookings()
    # Sort by date and start time
    bookings.sort(key=lambda x: (x['date'], x['start_time']))
    
    return render_template('my_bookings.html', bookings=bookings)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
