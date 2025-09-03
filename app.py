from flask import Flask, render_template, request, jsonify, session, send_file, make_response
import csv
from io import StringIO, BytesIO
from datetime import datetime
import uuid
import os
import json

# Try to import weasyprint, but don't fail if it's not available
try:
    import weasyprint
    WEASYPRINT_AVAILABLE = True
    print("WeasyPrint available - PDF export enabled")
except ImportError as e:
    WEASYPRINT_AVAILABLE = False
    print(f"WeasyPrint not available - PDF export disabled: {e}")

app = Flask(__name__)
app.secret_key = 'class_scheduler_secret_key'

# Add CORS headers to all responses
@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    return response

# Global variables for session-based storage
classes_data = []
selected_classes = []
current_schedule = None
manual_room_assignments = {}  # Track manual room assignments (legacy)
manual_period_assignments = {}  # Track manual period assignments (legacy)
manual_session_assignments = {}  # Track individual session assignments (day, period, room per session)
class_colors = {}  # Track color assignments for each class

# Room definitions
ROOMS = {
    'computer_lab': 'Computer Lab',
    'chapel': 'Chapel',
    'classroom_2': 'Classroom 2',
    'classroom_4': 'Classroom 4', 
    'classroom_5': 'Classroom 5',
    'classroom_6': 'Classroom 6'
}

# Time periods
PERIODS = {
    1: 'Period 1',
    2: 'Period 2', 
    3: 'Period 3 (Chapel)',
    4: 'Period 4',
    5: 'Period 5',
    6: 'Period 6',
    7: 'Period 7',
    8: 'Period 8',
    9: 'Period 9',
    10: 'Period 10'
}

DAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']

# Schedule data storage
SCHEDULE_DATA_FILE = 'last_schedule.json'

def save_schedule_data():
    """Save current form data (selected classes and their assignments) to JSON file"""
    global selected_classes, manual_session_assignments
    
    schedule_data = {
        'selected_classes': selected_classes,
        'session_assignments': manual_session_assignments,
        'timestamp': datetime.now().isoformat(),
        'version': '1.0'
    }
    
    try:
        print(f"DEBUG: About to save session assignments for {len(manual_session_assignments)} classes")
        for class_name, sessions in manual_session_assignments.items():
            print(f"DEBUG: {class_name} has {len(sessions)} sessions: {sessions}")
        
        with open(SCHEDULE_DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(schedule_data, f, indent=2, ensure_ascii=False)
        print(f"Schedule data saved to {SCHEDULE_DATA_FILE}")
    except Exception as e:
        print(f"Error saving schedule data: {e}")

def load_schedule_data():
    """Load saved form data from JSON file"""
    try:
        if not os.path.exists(SCHEDULE_DATA_FILE):
            return None
            
        with open(SCHEDULE_DATA_FILE, 'r', encoding='utf-8') as f:
            schedule_data = json.load(f)
            
        print(f"Schedule data loaded from {SCHEDULE_DATA_FILE}")
        return schedule_data
    except Exception as e:
        print(f"Error loading schedule data: {e}")
        return None

def convert_schedule_to_sessions(schedule, selected_classes):
    """Convert current_schedule format to session_assignments format"""
    session_assignments = {}
    
    # Initialize empty session assignments for all selected classes
    for class_name in selected_classes:
        session_assignments[class_name] = []
    
    # Process the schedule to extract sessions
    for day in schedule:
        for period_str in schedule[day]:
            for class_session in schedule[day][period_str]:
                class_name = class_session['Class']
                room = class_session.get('room', 'Open')
                period = int(period_str) if str(period_str).isdigit() else period_str
                
                # Add this session to the class's session list
                if class_name in session_assignments:
                    session_assignments[class_name].append({
                        'day': day,
                        'period': period,
                        'room': room
                    })
    
    return session_assignments

def update_current_schedule_with_move(class_name, session_index, new_day, new_period, session_assignments, current_day=None, current_period=None, preserved_room=None):
    """Update the current_schedule global variable with a moved session.
    Targets the exact session (by previous day/period and sessionIndex if available),
    and preserves the room assignment unless explicitly changed.
    """
    global current_schedule
    if not current_schedule:
        return

    # Determine where to remove the session from
    session_template = None
    removed_successfully = False

    # Prefer precise removal using provided current_day/current_period
    if current_day and current_period is not None and current_day in current_schedule:
        for old_key in (current_period, str(current_period)):
            if old_key in current_schedule[current_day]:
                period_list = current_schedule[current_day][old_key]
                for i, class_session in enumerate(list(period_list)):
                    if class_session.get('Class') == class_name:
                        # If sessionIndex metadata exists, match it first
                        if class_session.get('sessionIndex') is not None:
                            if class_session['sessionIndex'] == session_index:
                                session_template = class_session.copy()
                                del current_schedule[current_day][old_key][i]
                                removed_successfully = True
                                print(f"SCHEDULE UPDATE: Precisely removed {class_name} session {session_index} from {current_day} P{old_key}")
                                break
                        else:
                            # Fallback: first matching occurrence in that slot
                            session_template = class_session.copy()
                            del current_schedule[current_day][old_key][i]
                            removed_successfully = True
                            print(f"SCHEDULE UPDATE: Removed {class_name} from {current_day} P{old_key} (no sessionIndex)")
                            break
                if removed_successfully:
                    break

    # Fallback: original Nth-occurrence scan across the schedule
    if not removed_successfully:
        sessions_removed = 0
        for day in list(current_schedule.keys()):
            if removed_successfully:
                break
            for period_str in list(current_schedule[day].keys()):
                if removed_successfully:
                    break
                for i, class_session in enumerate(list(current_schedule[day][period_str])):
                    if class_session.get('Class') == class_name:
                        if sessions_removed == session_index:
                            session_template = class_session.copy()
                            del current_schedule[day][period_str][i]
                            removed_successfully = True
                            print(f"SCHEDULE UPDATE: Fallback-removed {class_name} session {session_index} from {day} P{period_str}")
                            break
                        sessions_removed += 1

    if session_template is None:
        print(f"SCHEDULE UPDATE: Could not find session to move for {class_name} (index {session_index})")
        return

    # Prepare new location
    new_period_key = int(new_period) if isinstance(new_period, (int, float, str)) and str(new_period).isdigit() else new_period
    if new_day not in current_schedule:
        current_schedule[new_day] = {}
    if new_period_key not in current_schedule[new_day]:
        current_schedule[new_day][new_period_key] = []

    # Create new session with preserved room info
    new_session = session_template.copy()
    desired_room = preserved_room
    if desired_room is None and class_name in session_assignments and session_index < len(session_assignments[class_name]):
        desired_room = session_assignments[class_name][session_index].get('room')
    if desired_room:
        new_session['room'] = desired_room

    current_schedule[new_day][new_period_key].append(new_session)
    print(f"SCHEDULE UPDATE: Added {class_name} session {session_index} to {new_day} P{new_period} (room preserved: {new_session.get('room')})")

def clean_text_data(text):
    """Clean text data by removing leading/trailing spaces, double spaces, and normalizing"""
    if not text:
        return text
    
    # Convert to string if not already
    text = str(text)
    
    # Remove leading and trailing whitespace
    text = text.strip()
    
    # Convert multiple spaces to single space
    import re
    text = re.sub(r'\s+', ' ', text)
    
    # Remove extra commas and periods at the end
    text = text.rstrip('.,')
    
    # Clean up common spacing issues around commas
    text = re.sub(r'\s*,\s*', ', ', text)
    
    return text

def clean_student_list(student_string):
    """Clean and normalize student names in semicolon-separated list"""
    if not student_string:
        return ""
    
    # Split by semicolon and clean each name
    students = []
    for student in str(student_string).split(';'):
        cleaned_student = clean_text_data(student)
        if cleaned_student:  # Only add non-empty names
            students.append(cleaned_student)
    
    return '; '.join(students)

def generate_class_colors(class_names):
    """Generate two-tone colors for each class - header and body colors for enhanced distinction"""
    import colorsys
    colors = {}
    
    if not class_names:
        return colors
    
    num_classes = len(class_names)
    
    # Sort class names for consistent color assignment
    sorted_classes = sorted(class_names)
    
    # Use golden ratio for better color distribution (avoids clustering)
    golden_ratio = 0.618033988749
    
    for i, class_name in enumerate(sorted_classes):
        # Use golden ratio to distribute hues more evenly across spectrum
        # This prevents similar colors from clustering together
        hue = (i * golden_ratio * 360.0) % 360
        
        # Add cyclic variations based on position to ensure diversity
        cycle_variation = (i % 7) * 8  # 0, 8, 16, 24, 32, 40, 48 degree shifts
        hue = (hue + cycle_variation) % 360
        
        # Convert hue to 0-1 range for colorsys
        h = hue / 360.0
        
        # Generate TWO related colors for two-tone effect
        
        # Header color (darker, more saturated for class name)
        header_saturation = 0.75 + (i % 5) * 0.04  # 0.75-0.91 range
        header_lightness = 0.25 + (i % 6) * 0.02   # 0.25-0.35 range (darker)
        
        # Body color (lighter but still dark enough for white text)
        body_saturation = 0.65 + (i % 5) * 0.04    # 0.65-0.81 range (less saturated)
        body_lightness = 0.35 + (i % 6) * 0.02     # 0.35-0.45 range (lighter than header)
        
        # Convert header color
        r1, g1, b1 = colorsys.hls_to_rgb(h, header_lightness, header_saturation)
        header_color = '#{:02x}{:02x}{:02x}'.format(
            int(r1 * 255), int(g1 * 255), int(b1 * 255)
        )
        
        # Convert body color
        r2, g2, b2 = colorsys.hls_to_rgb(h, body_lightness, body_saturation)
        body_color = '#{:02x}{:02x}{:02x}'.format(
            int(r2 * 255), int(g2 * 255), int(b2 * 255)
        )
        
        # Store both colors
        colors[class_name] = {
            'header': header_color,
            'body': body_color,
            'primary': header_color  # For backward compatibility
        }
    
    return colors

def get_class_color(class_name, color_type='primary'):
    """Get the assigned color for a specific class"""
    global class_colors
    class_color_data = class_colors.get(class_name, {
        'header': '#667eea',
        'body': '#8a9bf2', 
        'primary': '#667eea'
    })
    return class_color_data.get(color_type, '#667eea')

def abbreviate_teacher_name(full_name):
    """Abbreviate teacher first name (e.g., 'Melson, Pat' -> 'Melson, P.')"""
    if not full_name or ',' not in full_name:
        return full_name
    
    try:
        # Split by comma and clean up spaces
        parts = [part.strip() for part in full_name.split(',')]
        if len(parts) >= 2:
            last_name = parts[0]
            first_name = parts[1]
            
            # Take first letter of first name and add period
            if first_name:
                abbreviated = f"{last_name}, {first_name[0]}."
                return abbreviated
    except:
        # If anything goes wrong, return original name
        pass
    
    return full_name

def abbreviate_room_name(room_name):
    """Abbreviate room names (e.g., 'Classroom 2' -> 'Room 2')"""
    if not room_name:
        return room_name
    
    # Replace "Classroom" with "Room" and capitalize "class" to "Class"
    abbreviated = room_name.replace('Classroom', 'Room')
    abbreviated = abbreviated.replace('classroom', 'Room')  # Handle lowercase
    abbreviated = abbreviated.replace('class', 'Class')     # Capitalize "class"
    
    return abbreviated

def clean_csv_data(class_info):
    """Clean all relevant fields in a class record"""
    cleaned = {}
    
    # Clean each field that contains text
    for key, value in class_info.items():
        if key == 'Students':
            # Special handling for student list
            cleaned[key] = clean_student_list(value)
        elif key in ['Class', 'Course Name', 'Teacher']:
            # Clean text fields
            cleaned[key] = clean_text_data(value)
        elif key == 'Units':
            # Clean units field but preserve numeric value
            cleaned[key] = clean_text_data(value)
        else:
            # Keep other fields as-is but still clean them
            cleaned[key] = clean_text_data(value) if value else value
    
    return cleaned

class ClassScheduler:
    def __init__(self, classes, manual_rooms=None, manual_periods=None, manual_sessions=None):
        self.classes = classes
        self.schedule = {}
        self.conflicts = []
        self.room_assignments = {}
        self.manual_room_assignments = manual_rooms or {}
        self.manual_period_assignments = manual_periods or {}
        self.manual_session_assignments = manual_sessions or {}
        
    def parse_students(self, student_string):
        """Parse semicolon-separated student list with data cleaning"""
        if not student_string or student_string == '':
            return []
        
        # Clean the student list and split by semicolon
        cleaned_list = clean_student_list(student_string)
        return [s.strip() for s in cleaned_list.split(';') if s.strip()]
    
    def get_class_frequency(self, units):
        """Determine how many times per week a class meets based on units"""
        try:
            units = int(float(units))
            if units == 4:
                return 1
            elif units == 8:
                return 2
            elif units == 12:
                return 3
            else:
                return 1  # Default
        except:
            return 1
    
    def get_preferred_days(self, frequency):
        """Get preferred and alternative days based on frequency"""
        if frequency == 1:
            return [['Monday'], ['Tuesday'], ['Wednesday'], ['Thursday'], ['Friday']]
        elif frequency == 2:
            # Priority order: preferred first, then alternatives
            return [
                ['Tuesday', 'Thursday'],      # Preferred
                ['Monday', 'Wednesday'],      # Alternative 1
                ['Monday', 'Friday'],         # Alternative 2  
                ['Wednesday', 'Friday'],      # Alternative 3
                ['Monday', 'Tuesday'],        # Alternative 4
                ['Tuesday', 'Wednesday'],     # Alternative 5
                ['Wednesday', 'Thursday'],    # Alternative 6
                ['Thursday', 'Friday']        # Alternative 7
            ]
        elif frequency == 3:
            # Priority order: preferred first, then alternatives
            return [
                ['Monday', 'Wednesday', 'Friday'],  # Preferred
                ['Monday', 'Tuesday', 'Thursday'],  # Alternative 1
                ['Tuesday', 'Wednesday', 'Friday'], # Alternative 2
                ['Monday', 'Tuesday', 'Wednesday'], # Alternative 3
                ['Tuesday', 'Wednesday', 'Thursday'], # Alternative 4
                ['Wednesday', 'Thursday', 'Friday']   # Alternative 5
            ]
        return [['Monday']]
    
    def get_period_priority_order(self):
        """Get periods in priority order: core periods first, then others"""
        return [
            [2, 4, 5, 6],  # Core periods (highest priority)
            [1],           # Period 1 (second priority) 
            [7],           # Period 7 (lunch time)
            [11],          # Period 7b (afternoon option)
            [8]            # Period 8 (special teachers only)
        ]
    
    def evaluate_solution_quality(self, schedule):
        """Evaluate the quality of a scheduling solution"""
        score = 0
        period_usage = {p: 0 for p in range(1, 12)}  # Updated to include Period 7b
        
        # Count period usage
        for day in schedule:
            for period in schedule[day]:
                if schedule[day][period]:  # If period has classes
                    period_usage[period] += len(schedule[day][period])
        
        # Scoring: Prefer core periods, penalize Period 1 and 7
        score += period_usage[2] * 10  # Core periods get high scores
        score += period_usage[4] * 10
        score += period_usage[5] * 10
        score += period_usage[6] * 10
        score -= period_usage[1] * 5   # Penalize Period 1 usage
        score -= period_usage[7] * 20  # Heavy penalty for Period 7
        score -= period_usage[11] * 10 # Moderate penalty for Period 7b (afternoon)
        score += period_usage[8] * 8   # Period 8 is okay for special teachers
        score += period_usage[9] * 8   # Period 9 is okay for special teachers  
        score += period_usage[10] * 8  # Period 10 is okay for special teachers
        
        return score, period_usage
    
    def analyze_manual_session_pattern(self, class_name, total_frequency):
        """Analyze manual session assignments to infer patterns for remaining sessions"""
        pattern = {
            'manual_days': [],
            'manual_periods': [],
            'manual_rooms': [],
            'inferred_days': None,
            'preferred_period': None,
            'preferred_room': None,
            'preferred_day': None
        }
        
        if class_name not in self.manual_session_assignments:
            return pattern
            
        # Extract manual assignments
        sessions = self.manual_session_assignments[class_name]
        for session_index, session in enumerate(sessions):
            if session_index in self.manually_scheduled_sessions.get(class_name, set()):
                # This session was manually scheduled (day and period specified)
                pattern['manual_days'].append(session.get('day'))
                pattern['manual_periods'].append(session.get('period'))
                pattern['manual_rooms'].append(session.get('room'))
        
        # Also check room preferences for auto-scheduled sessions
        if hasattr(self, 'manual_room_preferences') and class_name in self.manual_room_preferences:
            for session_index, room in self.manual_room_preferences[class_name].items():
                if session_index >= len(pattern['manual_rooms']):
                    # Extend list if needed
                    while len(pattern['manual_rooms']) <= session_index:
                        pattern['manual_rooms'].append(None)
                pattern['manual_rooms'][session_index] = room
        
        # Also check period preferences for auto-scheduled sessions
        if hasattr(self, 'manual_period_preferences') and class_name in self.manual_period_preferences:
            for session_index, period in self.manual_period_preferences[class_name].items():
                if session_index >= len(pattern['manual_periods']):
                    # Extend list if needed
                    while len(pattern['manual_periods']) <= session_index:
                        pattern['manual_periods'].append(None)
                pattern['manual_periods'][session_index] = period
        
        # Also check day preferences for auto-scheduled sessions
        if hasattr(self, 'manual_day_preferences') and class_name in self.manual_day_preferences:
            for session_index, day in self.manual_day_preferences[class_name].items():
                if session_index >= len(pattern['manual_days']):
                    # Extend list if needed
                    while len(pattern['manual_days']) <= session_index:
                        pattern['manual_days'].append(None)
                pattern['manual_days'][session_index] = day
        
        # Infer preferred period (use most common manual period)
        manual_periods = [p for p in pattern['manual_periods'] if p != 'Open' and p is not None]
        if manual_periods:
            pattern['preferred_period'] = manual_periods[0]  # Use first manual period
        
        # Infer preferred room (use most common manual room)
        manual_rooms = [r for r in pattern['manual_rooms'] if r and r != 'Open']
        if manual_rooms:
            pattern['preferred_room'] = manual_rooms[0]  # Use first manual room
        
        # Infer preferred day (use first manual day)
        manual_days = [d for d in pattern['manual_days'] if d != 'Open' and d is not None]
        if manual_days:
            pattern['preferred_day'] = manual_days[0]  # Use first manual day
        
        # Infer day pattern based on frequency and manual days
        manual_days = [d for d in pattern['manual_days'] if d != 'Open' and d is not None]
        if manual_days and total_frequency > len(manual_days):
            if total_frequency == 2:
                # 8-credit class - infer the REMAINING day needed, not the full pattern
                if 'Monday' in manual_days:
                    pattern['inferred_days'] = ['Wednesday']  # Only the remaining day needed
                elif 'Tuesday' in manual_days:
                    pattern['inferred_days'] = ['Thursday']   # Only the remaining day needed
                elif 'Wednesday' in manual_days:
                    pattern['inferred_days'] = ['Monday']     # Only the remaining day needed
                elif 'Thursday' in manual_days:
                    pattern['inferred_days'] = ['Tuesday']    # Only the remaining day needed
                elif 'Friday' in manual_days:
                    pattern['inferred_days'] = ['Monday']     # Only the remaining day needed
            elif total_frequency == 3:
                # 12-credit class - infer the REMAINING days needed, not the full pattern
                used_days = set(manual_days)
                if len(used_days) == 1:
                    # One day used, need two more
                    if 'Monday' in used_days:
                        pattern['inferred_days'] = ['Wednesday', 'Friday']  # Complete M/W/F
                    elif 'Wednesday' in used_days:
                        pattern['inferred_days'] = ['Monday', 'Friday']     # Complete M/W/F
                    elif 'Friday' in used_days:
                        pattern['inferred_days'] = ['Monday', 'Wednesday']  # Complete M/W/F
                    elif 'Tuesday' in used_days:
                        pattern['inferred_days'] = ['Wednesday', 'Thursday'] # Complete T/W/Th
                    elif 'Thursday' in used_days:
                        pattern['inferred_days'] = ['Tuesday', 'Wednesday']  # Complete T/W/Th
                elif len(used_days) == 2:
                    # Two days used, need one more
                    mwf_days = {'Monday', 'Wednesday', 'Friday'}
                    twth_days = {'Tuesday', 'Wednesday', 'Thursday'}
                    if used_days.issubset(mwf_days):
                        pattern['inferred_days'] = list(mwf_days - used_days)     # Complete M/W/F
                    elif used_days.issubset(twth_days):
                        pattern['inferred_days'] = list(twth_days - used_days)    # Complete T/W/Th
                    else:
                        # Mixed pattern - just pick any remaining day
                        all_days = {'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday'}
                        pattern['inferred_days'] = list(all_days - used_days)[:1]  # Just one more day
        
        return pattern
    
    def assign_room(self, class_info):
        """Assign appropriate room based on class requirements and manual overrides"""
        class_name = class_info['Class']
        
        # Check for manual room assignment first
        if class_name in self.manual_room_assignments:
            manual_room = self.manual_room_assignments[class_name]
            if manual_room == 'Computer Lab':
                return 'computer_lab'
            elif manual_room == 'Chapel':
                return 'chapel'
            elif manual_room in ['Classroom 2', 'Classroom 4', 'Classroom 5', 'Classroom 6']:
                return manual_room.lower().replace(' ', '_')
        
        # Default automatic assignment logic
        course_name = class_info['Course Name'].upper()
        student_count = len(self.parse_students(class_info['Students']))
        
        # Computer classes and ESL classes -> Computer Lab
        if 'GECO' in course_name or 'GELA' in course_name:
            return 'computer_lab'
        
        # Classes over 40 students -> Chapel
        if student_count > 40:
            return 'chapel'
        
        # Regular classrooms for others - will be optimized during scheduling
        return 'regular_classroom'
    
    def get_available_regular_classroom(self, day, period, assigned_rooms):
        """Find an available regular classroom for the given day/period"""
        regular_classrooms = ['classroom_2', 'classroom_4', 'classroom_5', 'classroom_6']
        
        for room in regular_classrooms:
            room_key = f"{day}_{period}_{room}"
            if room_key not in assigned_rooms:
                return room
        
        return None  # No regular classroom available
    
    def check_conflicts(self, class1, class2):
        """Check if two classes have conflicts"""
        conflicts = []
        
        # Teacher conflict
        if class1['Teacher'] == class2['Teacher']:
            conflicts.append({
                'type': 'teacher',
                'teacher': class1['Teacher']
            })
        
        # Student conflicts
        students1 = set(self.parse_students(class1['Students']))
        students2 = set(self.parse_students(class2['Students']))
        shared_students = students1.intersection(students2)
        
        if shared_students:
            conflicts.append({
                'type': 'student',
                'shared_students': list(shared_students)
            })
        
        return conflicts
    
    def can_schedule_class(self, class_info, day_option, period, assigned_rooms, preferred_room=None):
        """Check if a class can be scheduled at the given day/period with optional room preference"""
        if preferred_room and preferred_room != 'Open':
            # Check availability of preferred room
            if preferred_room == 'Computer Lab':
                assigned_room_type = 'computer_lab'
            elif preferred_room == 'Chapel':
                assigned_room_type = 'chapel'
            elif preferred_room in ['Classroom 2', 'Classroom 4', 'Classroom 5', 'Classroom 6']:
                assigned_room_type = preferred_room.lower().replace(' ', '_')
            else:
                assigned_room_type = self.assign_room(class_info)
        else:
            assigned_room_type = self.assign_room(class_info)
        conflicts_found = []
        
        for day in day_option:
            existing_classes = self.schedule[day][period]
            
            # Check conflicts with existing classes
            for existing_class in existing_classes:
                class_conflicts = self.check_conflicts(class_info, existing_class)
                if class_conflicts:
                    for conflict in class_conflicts:
                        if conflict['type'] == 'student' and 'shared_students' in conflict:
                            student_names = ', '.join(conflict['shared_students'])
                            conflicts_found.append(f"student conflict with {existing_class['Class']} (students: {student_names})")
                        else:
                            conflicts_found.append(f"{conflict['type']} conflict with {existing_class['Class']}")
            
            # Check room availability
            if assigned_room_type == 'computer_lab':
                room_key = f"{day}_{period}_computer_lab"
                if room_key in assigned_rooms:
                    conflicts_found.append(f"Computer Lab unavailable")
            elif assigned_room_type == 'chapel':
                room_key = f"{day}_{period}_chapel"
                if room_key in assigned_rooms:
                    conflicts_found.append(f"Chapel unavailable")
            elif assigned_room_type in ['classroom_2', 'classroom_4', 'classroom_5', 'classroom_6']:
                # Specific classroom assignment
                room_key = f"{day}_{period}_{assigned_room_type}"
                if room_key in assigned_rooms:
                    conflicts_found.append(f"{assigned_room_type.replace('_', ' ').title()} unavailable")
            else:  # regular classroom (any available)
                available_room = self.get_available_regular_classroom(day, period, assigned_rooms)
                if not available_room:
                    conflicts_found.append(f"No regular classroom available")
        
        return len(conflicts_found) == 0, conflicts_found
    
    def schedule_class(self, class_info, day_option, period, assigned_rooms, preferred_room=None):
        """Schedule a class at the given day/period with optional room preference"""
        if preferred_room and preferred_room != 'Open':
            # Use preferred room if specified and available
            print(f"    Trying preferred room: {preferred_room}")
            if preferred_room == 'Computer Lab':
                assigned_room_type = 'computer_lab'
            elif preferred_room == 'Chapel':
                assigned_room_type = 'chapel'
            elif preferred_room in ['Classroom 2', 'Classroom 4', 'Classroom 5', 'Classroom 6']:
                assigned_room_type = preferred_room.lower().replace(' ', '_')
            else:
                assigned_room_type = self.assign_room(class_info)
        else:
            assigned_room_type = self.assign_room(class_info)
        
        for day in day_option:
            # Add class to schedule
            self.schedule[day][period].append(class_info)
            
            # Reserve room
            if assigned_room_type == 'computer_lab':
                room_key = f"{day}_{period}_computer_lab"
                assigned_rooms[room_key] = class_info['Class']
                self.room_assignments[f"{day}_{period}_{class_info['Class']}"] = 'Computer Lab'
            elif assigned_room_type == 'chapel':
                room_key = f"{day}_{period}_chapel"
                assigned_rooms[room_key] = class_info['Class']
                self.room_assignments[f"{day}_{period}_{class_info['Class']}"] = 'Chapel'
            elif assigned_room_type in ['classroom_2', 'classroom_4', 'classroom_5', 'classroom_6']:
                # Specific classroom assignment
                room_key = f"{day}_{period}_{assigned_room_type}"
                assigned_rooms[room_key] = class_info['Class']
                room_display = assigned_room_type.replace('_', ' ').title()
                self.room_assignments[f"{day}_{period}_{class_info['Class']}"] = room_display
            else:  # regular classroom (any available)
                available_room = self.get_available_regular_classroom(day, period, assigned_rooms)
                if available_room:
                    room_key = f"{day}_{period}_{available_room}"
                    assigned_rooms[room_key] = class_info['Class']
                    room_display = available_room.replace('_', ' ').title()
                    self.room_assignments[f"{day}_{period}_{class_info['Class']}"] = room_display
    
    def try_schedule_without_period_7(self):
        """Try to schedule all classes without using Period 7"""
        return self.generate_schedule_internal(use_period_7=False)
    
    def try_schedule_with_period_7(self):
        """Try to schedule all classes including Period 7 as last resort"""
        return self.generate_schedule_internal(use_period_7=True)
    
    def generate_schedule(self, use_period_7=False):
        """Generate class schedule with sophisticated optimization and multiple solution comparison"""
        print("Starting enhanced scheduling algorithm...")
        
        best_solution = None
        best_score = -999999
        solutions_tried = 0
        
        # Try multiple scheduling approaches and compare results
        approaches = [
            {"name": "Core periods first, no Period 7", "use_p7": False, "aggressive_core": True},
            {"name": "Standard approach, no Period 7", "use_p7": False, "aggressive_core": False},
        ]
        
        if use_period_7:
            approaches.extend([
                {"name": "Core periods first, with Period 7", "use_p7": True, "aggressive_core": True},
                {"name": "Standard approach, with Period 7", "use_p7": True, "aggressive_core": False},
            ])
        
        # Always add a fallback approach that's very flexible
        approaches.append({
            "name": "Fallback - any period allowed", "use_p7": True, "aggressive_core": False
        })
        
        for approach in approaches:
            print(f"\nTrying approach: {approach['name']}")
            
            # Reset for this attempt
            self.schedule = {}
            self.conflicts = []
            self.room_assignments = {}
            
            success, unscheduled = self.generate_schedule_internal(
                use_period_7=approach['use_p7'], 
                aggressive_core_filling=approach['aggressive_core']
            )
            
            solutions_tried += 1
            
            # Debug: Count actual scheduled classes
            actual_scheduled = sum(len(self.schedule[day][period]) 
                                 for day in self.schedule 
                                 for period in self.schedule[day] 
                                 if self.schedule[day][period])
            
            print(f"Approach result: success={success}, unscheduled={len(unscheduled)}, actually_scheduled={actual_scheduled}")
            
            if success:
                # Evaluate this solution
                score, period_usage = self.evaluate_solution_quality(self.schedule)
                print(f"Solution found! Score: {score}, Period usage: {period_usage}")
                
                if score > best_score:
                    best_score = score
                    best_solution = {
                        'schedule': dict(self.schedule),
                        'room_assignments': dict(self.room_assignments),
                        'score': score,
                        'period_usage': period_usage,
                        'approach': approach['name']
                    }
                    print(f"New best solution! Score: {score}")
            else:
                print(f"Approach failed with {len(unscheduled)} unscheduled classes")
                
                # Only treat as successful if we actually scheduled ALL classes, not just many instances
                if len(unscheduled) == 0:  # Must have zero unscheduled classes
                    print(f"WARNING: Approach reported failure but actually scheduled all {len(self.classes)} classes!")
                    # Treat this as a successful solution
                    score, period_usage = self.evaluate_solution_quality(self.schedule)
                    if score > best_score:
                        best_score = score
                        best_solution = {
                            'schedule': dict(self.schedule),
                            'room_assignments': dict(self.room_assignments),
                            'score': score,
                            'period_usage': period_usage,
                            'approach': approach['name'] + " (corrected)"
                        }
                        print(f"Using corrected solution! Score: {score}")
                else:
                    print(f"Approach truly failed: {len(unscheduled)} classes unscheduled: {[u['class']['Class'] for u in unscheduled]}")
        
        # Let the last approach (fallback) finish completely if no perfect solution found yet
        if not best_solution and len(approaches) > 0:
            print(f"\nNo perfect solution found yet. Ensuring fallback approach completes...")
            fallback_approach = approaches[-1]  # Last approach is always fallback
            
            # Reset for final attempt
            self.schedule = {}
            self.conflicts = []
            self.room_assignments = {}
            
            print(f"Running final attempt: {fallback_approach['name']}")
            success, unscheduled = self.generate_schedule_internal(
                use_period_7=fallback_approach['use_p7'], 
                aggressive_core_filling=fallback_approach['aggressive_core']
            )
            
            if success or len(unscheduled) == 0:
                score, period_usage = self.evaluate_solution_quality(self.schedule)
                best_solution = {
                    'schedule': dict(self.schedule),
                    'room_assignments': dict(self.room_assignments),
                    'score': score,
                    'period_usage': period_usage,
                    'approach': fallback_approach['name'] + " (final complete run)"
                }
                print(f"Fallback approach succeeded! Score: {score}")

        # Use the best solution found, or the best partial solution
        if best_solution:
            self.schedule = best_solution['schedule']
            self.room_assignments = best_solution['room_assignments']
            
            # Count actual scheduled classes in final solution
            final_scheduled_count = sum(len(self.schedule[day][period]) 
                                      for day in self.schedule 
                                      for period in self.schedule[day] 
                                      if self.schedule[day][period])
            
            print(f"\nUsing best solution: {best_solution['approach']}")
            print(f"Final score: {best_solution['score']}, Period usage: {best_solution['period_usage']}")
            print(f"Final solution has {final_scheduled_count} classes scheduled out of {len(self.classes)} total")
            
            # Debug: List all scheduled classes in final solution
            scheduled_classes = set()
            for day in self.schedule:
                for period in self.schedule[day]:
                    for class_info in self.schedule[day][period]:
                        scheduled_classes.add(class_info['Class'])
            
            missing_classes = set(cls['Class'] for cls in self.classes) - scheduled_classes
            if missing_classes:
                print(f"WARNING: Missing classes in final solution: {list(missing_classes)}")
            else:
                print(f"SUCCESS: All {len(self.classes)} classes are in the final solution")
            
            return True, []
        else:
            # No complete solution found, but let's try to find the best partial solution
            print(f"\nNo complete solution found after {solutions_tried} attempts")
            print("Attempting to find best partial solution...")
            
            best_partial = None
            best_partial_score = -999999
            min_unscheduled = 999999
            
            # Try all approaches again but keep partial results
            for approach in approaches:
                print(f"Evaluating partial solution for: {approach['name']}")
                
                # Reset for this attempt
                self.schedule = {}
                self.conflicts = []
                self.room_assignments = {}
                
                success, unscheduled = self.generate_schedule_internal(
                    use_period_7=approach['use_p7'], 
                    aggressive_core_filling=approach['aggressive_core']
                )
                
                # Calculate how many classes were successfully scheduled
                total_scheduled = sum(len(self.schedule[day][period]) 
                                    for day in self.schedule 
                                    for period in self.schedule[day])
                
                # Score this partial solution
                if total_scheduled > 0:
                    score, period_usage = self.evaluate_solution_quality(self.schedule)
                    # Bonus points for scheduling more classes
                    adjusted_score = score + (total_scheduled * 50) - (len(unscheduled) * 100)
                    
                    print(f"Partial solution: {total_scheduled} scheduled, {len(unscheduled)} unscheduled, score: {adjusted_score}")
                    
                    # Prefer solutions with fewer unscheduled classes, then higher scores
                    if (len(unscheduled) < min_unscheduled or 
                        (len(unscheduled) == min_unscheduled and adjusted_score > best_partial_score)):
                        
                        min_unscheduled = len(unscheduled)
                        best_partial_score = adjusted_score
                        best_partial = {
                            'schedule': dict(self.schedule),
                            'room_assignments': dict(self.room_assignments),
                            'score': adjusted_score,
                            'period_usage': period_usage,
                            'approach': approach['name'],
                            'unscheduled': unscheduled,
                            'total_scheduled': total_scheduled
                        }
            
            # Use the best partial solution
            if best_partial:
                self.schedule = best_partial['schedule']
                self.room_assignments = best_partial['room_assignments']
                print(f"\nUsing best partial solution: {best_partial['approach']}")
                print(f"Scheduled {best_partial['total_scheduled']} classes, {len(best_partial['unscheduled'])} unscheduled")
                print(f"Score: {best_partial['score']}, Period usage: {best_partial['period_usage']}")
                
                # Return success if we scheduled most classes, otherwise partial success
                if len(best_partial['unscheduled']) <= len(self.classes) * 0.1:  # 90% success rate
                    return True, []
                else:
                    return False, best_partial['unscheduled']
            else:
                print("No valid solution found at all")
                return False, unscheduled
    
    def generate_schedule_internal(self, use_period_7=False, aggressive_core_filling=True):
        """Internal method that actually generates the schedule"""
        self.schedule = {}
        self.conflicts = []
        self.room_assignments = {}
        self.manual_conflicts = []  # Track manual assignment conflicts
        assigned_rooms = {}  # Track room assignments: "day_period_room" -> class_name
        
        # Available periods (excluding period 3 for chapel)
        available_periods = [1, 2, 4, 5, 6]
        if use_period_7:
            available_periods.append(7)
            available_periods.append(11)  # Add Period 7b when Period 7 is enabled
        
        # Removed hardcoded teacher period requirements - now handled via manual dropdowns
        
        # Initialize schedule grid
        for day in DAYS:
            self.schedule[day] = {}
            for period in range(1, 12):  # Updated to include Period 7b (period 11)
                self.schedule[day][period] = []
        
        # FIRST: Handle manual session assignments (highest priority)
        # Track which sessions have been manually scheduled
        manually_scheduled_sessions = {}  # class_name -> set of scheduled session indices
        # Track manual room preferences for auto-scheduled sessions
        manual_room_preferences = {}  # class_name -> session_index -> room_name
        # Track manual period preferences for auto-scheduled sessions
        manual_period_preferences = {}  # class_name -> session_index -> period_number
        # Track manual day preferences for auto-scheduled sessions
        manual_day_preferences = {}  # class_name -> session_index -> day_name
        
        # Filter session assignments to only include selected classes
        selected_class_names = set(cls['Class'] for cls in self.classes)
        filtered_session_assignments = {
            class_name: sessions 
            for class_name, sessions in self.manual_session_assignments.items()
            if class_name in selected_class_names
        }
        
        print(f"MANUAL DEBUG: Processing {len(filtered_session_assignments)} classes with session assignments (filtered from {len(self.manual_session_assignments)} total)")
        
        try:
            for class_name, sessions in filtered_session_assignments.items():
                try:
                    # Find the class info
                    class_info = None
                    for cls in self.classes:
                        if cls['Class'] == class_name:
                            class_info = cls
                            break
                    
                    if not class_info:
                        print(f"ERROR: Class info not found for {class_name}")
                        continue
                        
                    print(f"Processing manual sessions for {class_name}: {sessions}")
                    manually_scheduled_sessions[class_name] = set()
                    
                    # Schedule each manually specified session
                    for session_index, session in enumerate(sessions):
                        try:
                            period_value = session.get('period')
                            day_value = session.get('day')
                            room_value = session.get('room', 'Open')
                            print(f"  Session {session_index}: day='{day_value}', period='{period_value}', room='{room_value}'")
                            
                            # Check if this is a fully manual assignment (day OR period specified, not both Open)
                            is_day_specified = session.get('day') not in ['Open', '', None]
                            is_period_specified = (period_value not in ['Open', '', None] and str(period_value).isdigit())
                            
                            if is_day_specified and is_period_specified:
                                # Both day and period specified - fully manual
                                pass  # Continue with fully manual logic
                            elif is_day_specified and period_value in ['Open', '', None]:
                                # Day specified but period is Open - still fully manual (day constraint)
                                pass  # Continue with fully manual logic  
                            elif is_period_specified and session.get('day') == 'Open':
                                # Period specified but day is Open - still fully manual (period constraint)
                                pass  # Continue with fully manual logic
                            else:
                                # Neither day nor period specified - skip to preferences logic
                                pass  # Will go to the else block below
                            
                            if (is_day_specified or is_period_specified):
                                
                                # Handle different types of manual assignments
                                if is_day_specified and is_period_specified:
                                    # Both specified - full manual assignment
                                    day = session['day']
                                    period = int(session['period'])
                                    room = session.get('room', 'TBD')
                                elif is_day_specified and period_value in ['Open', '', None]:
                                    # Day specified, period open - need to find available period on that day
                                    day = session['day']
                                    # Find the first available period on this day
                                    available_periods = [1, 2, 4, 5, 6, 7, 8, 9, 10, 11]  # All possible periods including Period 7b
                                    period = None
                                    for test_period in available_periods:
                                        if not self.schedule[day][test_period]:  # Empty period
                                            # Check if this class can be scheduled here
                                            can_schedule, _ = self.can_schedule_class(class_info, [day], test_period, {}, None)
                                            if can_schedule:
                                                period = test_period
                                                break
                                    
                                    if period is None:
                                        print(f"  ERROR: No available period found on {day} for {class_name}")
                                        continue
                                    
                                    room = session.get('room', 'TBD')
                                elif is_period_specified and session.get('day') == 'Open':
                                    # Period specified, day open - need to find available day for that period
                                    period = int(session['period'])
                                    # Find the first available day for this period
                                    available_days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
                                    day = None
                                    for test_day in available_days:
                                        if not self.schedule[test_day][period]:  # Empty slot
                                            # Check if this class can be scheduled here
                                            can_schedule, _ = self.can_schedule_class(class_info, [test_day], period, {}, None)
                                            if can_schedule:
                                                day = test_day
                                                break
                                    
                                    if day is None:
                                        print(f"  ERROR: No available day found for Period {period} for {class_name}")
                                        continue
                                    
                                    room = session.get('room', 'TBD')
                                else:
                                    print(f"  ERROR: Unexpected manual assignment state for {class_name}")
                                    continue
                                
                                print(f"  FULLY MANUAL: Scheduling session {session_index+1}: {day}, Period {period}, {room}")
                                
                                # Check for conflicts - BLOCK manual assignments if conflicts exist
                                try:
                                    conflicts_found = []
                                    # Check conflicts with existing classes in this time slot
                                    existing_classes = self.schedule[day][period]
                                    for existing_class in existing_classes:
                                        class_conflicts = self.check_conflicts(class_info, existing_class)
                                        if class_conflicts:
                                            for conflict in class_conflicts:
                                                if conflict['type'] == 'student' and 'shared_students' in conflict:
                                                    student_names = ', '.join(conflict['shared_students'])
                                                    conflicts_found.append(f"student conflict with {existing_class['Class']} (students: {student_names})")
                                                else:
                                                    conflicts_found.append(f"{conflict['type']} conflict with {existing_class['Class']}")
                                    
                                    if conflicts_found:
                                        print(f"  CONFLICT ERROR: Manual assignment blocked due to conflicts: {conflicts_found}")
                                        print(f"  BLOCKED: Cannot schedule {class_name} on {day} Period {period} - conflicts detected")
                                        # Add to conflicts list instead of scheduling
                                        conflict_info = {
                                            'class': class_info,
                                            'requested_slot': f"{day} Period {period}",
                                            'conflicts': conflicts_found,
                                            'type': 'manual_assignment_conflict'
                                        }
                                        if not hasattr(self, 'manual_conflicts'):
                                            self.manual_conflicts = []
                                        self.manual_conflicts.append(conflict_info)
                                        continue  # Skip to next session
                                    
                                except Exception as e:
                                    print(f"  ERROR checking conflicts for {class_name}: {e}")
                                    import traceback
                                    traceback.print_exc()
                                
                                # Only schedule if no conflicts were found
                                try:
                                    self.schedule[day][period].append(class_info)
                                    print(f"  SUCCESS: Added {class_name} to {day} Period {period}")
                                except Exception as e:
                                    print(f"  ERROR scheduling {class_name} on {day} Period {period}: {e}")
                                    import traceback
                                    traceback.print_exc()
                                    raise
                                
                                # Track room assignment properly
                                try:
                                    room_key = f"{day}_{period}_{class_info['Class']}"
                                    
                                    if room != 'Open' and room != 'TBD':
                                        # Manual room assignment specified
                                        self.room_assignments[room_key] = room
                                        print(f"  ROOM: Assigned specific room {room} to {class_name}")
                                        
                                        # Track room as occupied for this time slot using the correct key format
                                        if room == 'Computer Lab':
                                            assigned_rooms[f"{day}_{period}_computer_lab"] = class_info['Class']
                                        elif room == 'Chapel':
                                            assigned_rooms[f"{day}_{period}_chapel"] = class_info['Class']
                                        elif room == 'Classroom 2':
                                            assigned_rooms[f"{day}_{period}_classroom_2"] = class_info['Class']
                                        elif room == 'Classroom 4':
                                            assigned_rooms[f"{day}_{period}_classroom_4"] = class_info['Class']
                                        elif room == 'Classroom 5':
                                            assigned_rooms[f"{day}_{period}_classroom_5"] = class_info['Class']
                                        elif room == 'Classroom 6':
                                            assigned_rooms[f"{day}_{period}_classroom_6"] = class_info['Class']
                                        else:
                                            print(f"  WARNING: Unknown room format: {room}")
                                    else:
                                        # Room is "Open" - auto-assign using normal logic
                                        assigned_room_type = self.assign_room(class_info)
                                        
                                        if assigned_room_type == 'computer_lab':
                                            self.room_assignments[room_key] = 'Computer Lab'
                                            assigned_rooms[f"{day}_{period}_computer_lab"] = class_info['Class']
                                            print(f"  ROOM: Auto-assigned Computer Lab to {class_name}")
                                        elif assigned_room_type == 'chapel':
                                            self.room_assignments[room_key] = 'Chapel'
                                            assigned_rooms[f"{day}_{period}_chapel"] = class_info['Class']
                                            print(f"  ROOM: Auto-assigned Chapel to {class_name}")
                                        elif assigned_room_type in ['classroom_2', 'classroom_4', 'classroom_5', 'classroom_6']:
                                            # Specific classroom assignment from manual assignment
                                            room_display = assigned_room_type.replace('_', ' ').title()
                                            self.room_assignments[room_key] = room_display
                                            assigned_rooms[f"{day}_{period}_{assigned_room_type}"] = class_info['Class']
                                            print(f"  ROOM: Auto-assigned {room_display} to {class_name}")
                                        else:
                                            # Regular classroom - find first available
                                            available_room = self.get_available_regular_classroom(day, period, assigned_rooms)
                                            if available_room:
                                                room_display = available_room.replace('_', ' ').title()
                                                self.room_assignments[room_key] = room_display
                                                assigned_rooms[f"{day}_{period}_{available_room}"] = class_info['Class']
                                                print(f"  ROOM: Auto-assigned available {room_display} to {class_name}")
                                            else:
                                                # No regular classroom available
                                                self.room_assignments[room_key] = 'TBD'
                                                print(f"  ROOM: No available room for {class_name}, marked as TBD")
                                except Exception as e:
                                    print(f"  ERROR in room assignment for {class_name}: {e}")
                                    import traceback
                                    traceback.print_exc()
                                    raise
                                
                                # Track this session as manually scheduled
                                manually_scheduled_sessions[class_name].add(session_index)
                                print(f"  TRACKED: Session {session_index} marked as manually scheduled")
                                
                            else:
                                # Handle partial constraints (period-only or room-only preferences)
                                has_preferences = False
                                
                                # Check if there's a manual room preference (even if day/period are "Open")
                                if room_value != 'Open' and room_value != 'TBD':
                                    # Store room preference for auto-scheduling
                                    if class_name not in manual_room_preferences:
                                        manual_room_preferences[class_name] = {}
                                    manual_room_preferences[class_name][session_index] = room_value
                                    print(f"  ROOM PREF: Session {session_index} prefers {room_value}")
                                    has_preferences = True
                                
                                # Check if there's a manual period preference (day="Open" but specific period)
                                if (day_value == 'Open' and 
                                    period_value not in ['Open', '', None] and
                                    str(period_value).isdigit()):
                                    # Store period preference for auto-scheduling
                                    if class_name not in manual_period_preferences:
                                        manual_period_preferences[class_name] = {}
                                    manual_period_preferences[class_name][session_index] = int(period_value)
                                    print(f"  PERIOD PREF: Session {session_index} prefers Period {period_value}")
                                    has_preferences = True
                                
                                # Check if there's a manual day preference (period="Open" but specific day)
                                if (period_value in ['Open', '', None] and 
                                    day_value not in ['Open', '', None] and
                                    day_value in DAYS):
                                    # Store day preference for auto-scheduling
                                    if class_name not in manual_day_preferences:
                                        manual_day_preferences[class_name] = {}
                                    manual_day_preferences[class_name][session_index] = day_value
                                    print(f"  DAY PREF: Session {session_index} prefers {day_value}")
                                    has_preferences = True
                                
                                if not has_preferences:
                                    print(f"  AUTO: Session {session_index} will be fully auto-scheduled")
                                else:
                                    print(f"  CONSTRAINED: Session {session_index} will be auto-scheduled with preferences")
                        except Exception as e:
                            print(f"ERROR processing session {session_index} for {class_name}: {e}")
                            import traceback
                            traceback.print_exc()
                            raise
                except Exception as e:
                    print(f"ERROR processing manual sessions for class {class_name}: {e}")
                    import traceback
                    traceback.print_exc()
                    raise
        except Exception as e:
            print(f"CRITICAL ERROR in manual session processing: {e}")
            import traceback
            traceback.print_exc()
            raise
        
        # Store manually scheduled sessions info for use during auto-scheduling
        self.manually_scheduled_sessions = manually_scheduled_sessions
        self.manual_room_preferences = manual_room_preferences
        self.manual_period_preferences = manual_period_preferences
        self.manual_day_preferences = manual_day_preferences
        print(f"Manual session scheduling complete. Manual sessions: {manually_scheduled_sessions}")
        print(f"Room preferences captured: {manual_room_preferences}")
        print(f"Period preferences captured: {manual_period_preferences}")
        print(f"Day preferences captured: {manual_day_preferences}")
        
        # ALL classes remain in auto-scheduling (they may need additional sessions)
        remaining_classes = self.classes
        
        # Sort remaining classes by enhanced priority hierarchy
        def class_priority(class_info):
            priority = 0
            student_count = len(self.parse_students(class_info['Students']))
            course_name = class_info['Course Name'].upper()
            
            # 1. Manual period assignments get highest priority (most constrained)
            if class_info['Class'] in self.manual_period_assignments:
                priority += 10000
            
            # 2. Required teacher periods removed - now handled via manual period assignments
            
            # 3. Room constraints get third priority
            if 'GECO' in course_name or 'GELA' in course_name:
                priority += 2000  # Computer Lab constraint
            if student_count > 40:
                priority += 2000  # Chapel constraint
            
            # 4. Class size (largest first) - add student count directly
            priority += student_count * 10
            
            # 5. Classes with more frequency get higher priority (harder to schedule)
            frequency = self.get_class_frequency(class_info['Units'])
            priority += frequency * 100
            
            return priority
        
        sorted_classes = sorted(remaining_classes, key=class_priority, reverse=True)
        unscheduled_classes = []
        
        # Enhanced scheduling with sophisticated search and optimization
        for class_info in sorted_classes:
            class_name = class_info['Class']
            frequency = self.get_class_frequency(class_info['Units'])
            
            # Check if this class has manual sessions and calculate remaining sessions needed
            manual_sessions_count = 0
            if class_name in self.manually_scheduled_sessions:
                manual_sessions_count = len(self.manually_scheduled_sessions[class_name])
            
            remaining_sessions_needed = frequency - manual_sessions_count
            
            print(f"Auto-scheduling {class_name}: needs {frequency} total sessions, {manual_sessions_count} already manual, {remaining_sessions_needed} remaining")
            
            # Skip if all sessions are already manually scheduled
            if remaining_sessions_needed <= 0:
                print(f"  All sessions already manually scheduled, skipping")
                continue
            
            # Analyze manual session patterns for smart consistency
            manual_pattern = self.analyze_manual_session_pattern(class_name, frequency)
            print(f"  Manual pattern analysis: {manual_pattern}")
            
            # Get smart day options based on manual pattern
            if manual_pattern['inferred_days']:
                # Use inferred pattern (which excludes manually used days) as first choice
                day_options = [manual_pattern['inferred_days']]  # Use inferred pattern as first choice
                fallback_options = self.get_preferred_days(remaining_sessions_needed)
                day_options.extend([opt for opt in fallback_options if opt != manual_pattern['inferred_days']])
                print(f"  Using smart day options based on manual pattern: {day_options[:2]}...")
            else:
                day_options = self.get_preferred_days(remaining_sessions_needed)  # Use remaining sessions for day options
            
            # Exclude days that are already manually scheduled for this class
            if class_name in self.manually_scheduled_sessions:
                manually_used_days = set()
                if class_name in self.manual_session_assignments:
                    for session_index in self.manually_scheduled_sessions[class_name]:
                        if session_index < len(self.manual_session_assignments[class_name]):
                            session = self.manual_session_assignments[class_name][session_index]
                            if session.get('day') != 'Open':
                                manually_used_days.add(session['day'])
                
                print(f"  Manual days used: {manually_used_days}")
                
                # Filter out manually used days from all day options
                filtered_day_options = []
                for day_option in day_options:
                    available_days = [day for day in day_option if day not in manually_used_days]
                    if len(available_days) == remaining_sessions_needed:
                        filtered_day_options.append(available_days)
                
                if filtered_day_options:
                    day_options = filtered_day_options
                    print(f"  Filtered day options to avoid manual days: {day_options}")
                else:
                    print(f"  WARNING: No valid day combinations remain after excluding manual days")
            
            scheduled = False
            conflicts_found = []
            best_option = None
            
            # Check for manual period assignment first (legacy support)
            has_manual_period = class_name in self.manual_period_assignments
            
            # Teacher period requirements removed - now handled via manual dropdowns
            needs_period_8 = False
            needs_period_1 = False
            
            # Determine period priorities for this class
            if has_manual_period:
                period_groups = [[self.manual_period_assignments[class_name]]]
            elif manual_pattern['preferred_period']:
                # Use preferred period from manual pattern analysis
                preferred_period = manual_pattern['preferred_period']
                print(f"  Using preferred period {preferred_period} from manual pattern")
                period_groups = [
                    [preferred_period],  # Try preferred period first
                    [2, 4, 5, 6],       # Then core periods
                    [1],                # Then Period 1
                    [7] if use_period_7 else []  # Period 7 last resort
                ]
                # Remove the preferred period from other groups to avoid duplicates (but keep the first group intact)
                period_groups = [period_groups[0]] + [[p for p in group if p != preferred_period] for group in period_groups[1:]]
                period_groups = [group for group in period_groups if group]  # Remove empty groups
            else:
                # Use period priority order based on aggressiveness
                if aggressive_core_filling:
                    # Strict priority: core periods first, then others
                    period_groups = [
                        [2, 4, 5, 6],  # Core periods (try these first)
                        [1],           # Period 1 (only if core periods don't work)
                        [7] if use_period_7 else []  # Period 7 (last resort)
                    ]
                else:
                    # More flexible: allow mixing of periods
                    period_groups = [
                        [2, 4, 5, 6],  # Still prefer core periods
                        [1, 7] if use_period_7 else [1]  # But allow Period 1 and 7 together
                    ]
                period_groups = [group for group in period_groups if group]  # Remove empty groups
            
            # Try scheduling with period priority in mind
            for period_group in period_groups:
                if scheduled:
                    break
                    
                for period in period_group:
                    if scheduled:
                        break
                        
                    # Try each day combination for this period
                    for day_option in day_options:
                        if scheduled:
                            break
                            
                        can_schedule, period_conflicts = self.can_schedule_class(class_info, day_option, period, assigned_rooms, manual_pattern.get('preferred_room'))
                        
                        if can_schedule:
                            # Found a valid slot - record it
                            potential_option = {
                                'day_option': day_option,
                                'period': period,
                                'priority_score': self.get_option_priority_score(period, day_option, frequency)
                            }
                            
                            # If this is core period, manual assignment, or preferred period, schedule immediately
                            if period in [2, 4, 5, 6] or has_manual_period or manual_pattern['preferred_period'] == period:
                                self.schedule_class(class_info, day_option, period, assigned_rooms, manual_pattern.get('preferred_room'))
                                scheduled = True
                                print(f"Scheduled {class_info['Class']} on {day_option} at Period {period}")
                                break
                            else:
                                # For non-core periods, save the option but keep looking for better ones
                                if best_option is None or potential_option['priority_score'] > best_option['priority_score']:
                                    best_option = potential_option
                        else:
                            conflicts_found.extend(period_conflicts)
            
            # If not scheduled in core periods but have a fallback option, use it
            if not scheduled and best_option:
                self.schedule_class(class_info, best_option['day_option'], best_option['period'], assigned_rooms, manual_pattern.get('preferred_room'))
                scheduled = True
                print(f"Scheduled {class_info['Class']} on {best_option['day_option']} at Period {best_option['period']} (fallback)")
            
            if not scheduled:
                unscheduled_classes.append({
                    'class': class_info,
                    'conflicts': conflicts_found
                })
                print(f"Could not schedule {class_info['Class']} - conflicts: {conflicts_found[:3]}...")  # Show first 3 conflicts
        
        # Apply room preferences for auto-scheduled sessions
        self.apply_room_preferences()
        
        # Always return the current state - whether complete or partial
        total_classes = len(self.classes)
        scheduled_classes = total_classes - len(unscheduled_classes)
        print(f"Scheduling complete: {scheduled_classes}/{total_classes} classes scheduled")
        
        return len(unscheduled_classes) == 0, unscheduled_classes
    
    def apply_room_preferences(self):
        """Apply manual room preferences to auto-scheduled sessions"""
        try:
            print("Starting apply_room_preferences method")
            
            if not hasattr(self, 'manual_room_preferences'):
                print("No manual_room_preferences attribute found")
                return
                
            if not self.manual_room_preferences:
                print("No room preferences to apply")
                return
                
            print(f"Applying room preferences: {self.manual_room_preferences}")
            
            for class_name, session_prefs in self.manual_room_preferences.items():
                try:
                    print(f"Processing room preferences for {class_name}: {session_prefs}")
                    
                    # Find all scheduled instances of this class
                    scheduled_instances = []
                    print(f"  Searching schedule for {class_name}")
                    
                    for day in self.schedule:
                        for period in self.schedule[day]:
                            for class_instance in self.schedule[day][period]:
                                if class_instance['Class'] == class_name:
                                    scheduled_instances.append({
                                        'day': day,
                                        'period': period,
                                        'class_instance': class_instance
                                    })
                                    print(f"    Found instance: {day} Period {period}")
                    
                    print(f"  Found {len(scheduled_instances)} scheduled instances")
                    
                    # Apply room preferences to matching sessions
                    for session_index, preferred_room in session_prefs.items():
                        try:
                            print(f"    Processing session {session_index} preference: {preferred_room}")
                            
                            if session_index < len(scheduled_instances):
                                instance = scheduled_instances[session_index]
                                day = instance['day']
                                period = instance['period']
                                
                                # Update room assignment
                                room_key = f"{day}_{period}_{class_name}"
                                old_room = self.room_assignments.get(room_key, 'TBD')
                                self.room_assignments[room_key] = preferred_room
                                
                                print(f"      Applied: Session {session_index} ({day} Period {period}) changed from {old_room} to {preferred_room}")
                            else:
                                print(f"      WARNING: Session {session_index} preference for {preferred_room} but only {len(scheduled_instances)} instances scheduled")
                        except Exception as e:
                            print(f"    ERROR processing session {session_index}: {e}")
                            import traceback
                            traceback.print_exc()
                            
                except Exception as e:
                    print(f"ERROR processing class {class_name}: {e}")
                    import traceback
                    traceback.print_exc()
                    
            print("Completed apply_room_preferences method")
            
        except Exception as e:
            print(f"CRITICAL ERROR in apply_room_preferences: {e}")
            import traceback
            traceback.print_exc()
    
    def get_option_priority_score(self, period, day_option, frequency):
        """Score an option based on period and day preferences"""
        score = 0
        
        # Period scoring (higher = better)
        if period in [2, 4, 5, 6]:
            score += 100  # Core periods get highest score
        elif period == 1:
            score += 20   # Period 1 is acceptable
        elif period == 7:
            score += 5    # Period 7 is last resort
        elif period == 8:
            score += 80   # Period 8 is good for special teachers
        elif period == 9:
            score += 80   # Period 9 is good for special teachers
        elif period == 10:
            score += 80   # Period 10 is good for special teachers
        
        # Day combination scoring
        if frequency == 2 and day_option == ['Tuesday', 'Thursday']:
            score += 50  # Preferred days for 8-credit
        elif frequency == 3 and day_option == ['Monday', 'Wednesday', 'Friday']:
            score += 50  # Preferred days for 12-credit
        else:
            score += 10  # Alternative days
        
        return score

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/test')
def test():
    return jsonify({'status': 'Server is running!', 'timestamp': datetime.now().isoformat()})


@app.route('/upload', methods=['POST'])
def upload_csv():
    global classes_data
    
    try:
        print("Upload request received")  # Debug
        print("Files in request:", list(request.files.keys()))  # Debug
        
        if 'csv_file' not in request.files:
            print("No csv_file in request.files")  # Debug
            return jsonify({'success': False, 'error': 'No file uploaded'})
        
        file = request.files['csv_file']
        print(f"File received: {file.filename}")  # Debug
        
        if file.filename == '':
            return jsonify({'success': False, 'error': 'No file selected'})
        
        # Read CSV file
        csv_content = file.read().decode('utf-8')
        print(f"CSV content length: {len(csv_content)}")  # Debug
        
        reader = csv.DictReader(StringIO(csv_content))
        
        # Convert to list of dictionaries and clean data
        raw_classes = list(reader)
        print(f"Raw classes parsed: {len(raw_classes)}")  # Debug
        
        # Clean data and count students for each class
        classes_data = []
        for class_info in raw_classes:
            # Clean all data fields
            cleaned_class = clean_csv_data(class_info)
            
            # Count students after cleaning
            if 'Students' in cleaned_class and cleaned_class['Students']:
                student_list = [s.strip() for s in str(cleaned_class['Students']).split(';') if s.strip()]
                cleaned_class['student_count'] = len(student_list)
                print(f"Cleaned class: {cleaned_class['Class']} - Teacher: '{cleaned_class['Teacher']}' - Students: {cleaned_class['student_count']}")  # Debug
            else:
                cleaned_class['student_count'] = 0
                
            classes_data.append(cleaned_class)
        
        print(f"Classes cleaned and processed: {len(classes_data)}")  # Debug
        
        print("Upload successful")  # Debug
        return jsonify({
            'success': True,
            'classes_found': len(classes_data),
            'classes': [
                {
                    'name': cls['Class'],
                    'teacher': cls['Teacher'],
                    'student_count': cls['student_count'],
                    'units': cls['Units']
                } for cls in classes_data
            ]
        })
        
    except Exception as e:
        print(f"Upload error: {str(e)}")  # Debug
        return jsonify({'success': False, 'error': str(e)})

@app.route('/generate_schedule', methods=['POST'])
def generate_schedule():
    global current_schedule, selected_classes, manual_room_assignments, manual_period_assignments, manual_session_assignments, class_colors
    
    try:
        data = request.get_json() or {}
        use_period_7 = data.get('use_period_7', False)
        
        print(f"SCHEDULE DEBUG: Starting generate_schedule")
        print(f"SCHEDULE DEBUG: selected_classes = {selected_classes}")
        print(f"SCHEDULE DEBUG: classes_data length = {len(classes_data) if classes_data else 0}")
        
        if not selected_classes:
            print("SCHEDULE DEBUG: No classes selected")
            return jsonify({'success': False, 'error': 'No classes selected'})
        
        # Filter classes to only selected ones
        classes_to_schedule = [cls for cls in classes_data if cls['Class'] in selected_classes]
        
        print(f"SCHEDULE DEBUG: classes_to_schedule length = {len(classes_to_schedule)}")
        for i, cls in enumerate(classes_to_schedule[:3]):  # Show first 3 classes
            print(f"SCHEDULE DEBUG: Class {i+1}: {cls.get('Class', 'Unknown')} - {cls.get('student_count', 0)} students")
        
        if not classes_to_schedule:
            print("SCHEDULE DEBUG: Selected classes not found in data")
            return jsonify({'success': False, 'error': 'Selected classes not found in data'})
        
        # Generate colors for all selected classes
        class_names = [cls['Class'] for cls in classes_to_schedule]
        class_colors = generate_class_colors(class_names)
        print(f"Generated colors for {len(class_colors)} classes")
        
        print(f"Manual room assignments: {manual_room_assignments}")
        print(f"Manual period assignments: {manual_period_assignments}")
        
        # Pass manual assignments to scheduler
        scheduler = ClassScheduler(classes_to_schedule, manual_room_assignments, manual_period_assignments, manual_session_assignments)
        print(f"SCHEDULE DEBUG: Created scheduler, calling generate_schedule")
        success, unscheduled = scheduler.generate_schedule(use_period_7)
        print(f"SCHEDULE DEBUG: Schedule generation result: success={success}")
        if unscheduled:
            print(f"SCHEDULE DEBUG: Unscheduled classes: {len(unscheduled)}")
        
        # Debug the resulting schedule
        if hasattr(scheduler, 'schedule'):
            total_scheduled = 0
            for day in scheduler.schedule:
                for period in scheduler.schedule[day]:
                    total_scheduled += len(scheduler.schedule[day][period])
            print(f"SCHEDULE DEBUG: Total classes in schedule: {total_scheduled}")
        else:
            print("SCHEDULE DEBUG: No schedule attribute found on scheduler")
        
        # Always build enhanced schedule (for both complete and partial schedules)  
        enhanced_schedule = {}
        
        # Track session indices by counting occurrences of each class as we build the schedule
        class_session_counters = {}  # {class_name: current_session_index}
        
        for day in scheduler.schedule:
            enhanced_schedule[day] = {}
            for period in scheduler.schedule[day]:
                enhanced_schedule[day][period] = []
                for class_info in scheduler.schedule[day][period]:
                    # Get room assignment
                    room_key = f"{day}_{period}_{class_info['Class']}"
                    room_name = scheduler.room_assignments.get(room_key, 'TBD')
                    
                    # Track session index by counting occurrences
                    class_name = class_info['Class']
                    if class_name not in class_session_counters:
                        class_session_counters[class_name] = 0
                    session_index = class_session_counters[class_name]
                    class_session_counters[class_name] += 1
                    
                    # Add room info, colors, abbreviated names, and session index to class
                    enhanced_class = class_info.copy()
                    enhanced_class['room'] = room_name
                    enhanced_class['room_abbreviated'] = abbreviate_room_name(room_name)
                    enhanced_class['teacher_abbreviated'] = abbreviate_teacher_name(class_info.get('Teacher', ''))
                    enhanced_class['color_header'] = get_class_color(class_info['Class'], 'header')
                    enhanced_class['color_body'] = get_class_color(class_info['Class'], 'body')
                    enhanced_class['color'] = get_class_color(class_info['Class'], 'primary')  # For backward compatibility
                    enhanced_class['sessionIndex'] = session_index  # Add session index for drag and drop tracking
                    enhanced_schedule[day][period].append(enhanced_class)
        
        # Save the enhanced schedule with room assignments for PDF export
        current_schedule = enhanced_schedule
        
        # Calculate how many classes were actually scheduled
        # Count unique scheduled classes by checking what's in the actual schedule
        scheduled_class_names = set()
        for day in scheduler.schedule:
            for period in scheduler.schedule[day]:
                for class_info in scheduler.schedule[day][period]:
                    scheduled_class_names.add(class_info['Class'])
        
        scheduled_count = len(scheduled_class_names)
        unscheduled_count = len(classes_to_schedule) - scheduled_count
        
        print(f"STATS DEBUG: {len(classes_to_schedule)} total classes, {scheduled_count} scheduled classes, {unscheduled_count} unscheduled classes")
        print(f"STATS DEBUG: Scheduled classes: {sorted(scheduled_class_names)}")
        if unscheduled:
            print(f"STATS DEBUG: Unscheduled classes: {[item['class']['Class'] for item in unscheduled]}")
        
        if success or scheduled_count > 0:
            response_data = {
                'success': True,
                'schedule': enhanced_schedule,
                'class_colors': class_colors,
                'stats': {
                    'total_classes': len(classes_to_schedule),
                    'scheduled_classes': scheduled_count,
                    'unscheduled_classes': unscheduled_count
                },
                'partial_schedule': unscheduled_count > 0,  # Indicate if this is a partial schedule
                'unscheduled': unscheduled
            }
            
            # If there are unscheduled classes, add detailed error information
            # Use the accurate count instead of relying on the scheduler's unscheduled list
            if unscheduled_count > 0:
                print(f"ERROR DEBUG: Found {unscheduled_count} unscheduled classes based on count")
                response_data['scheduling_errors'] = []
                
                # Find which classes are missing by comparing input vs scheduled
                input_class_names = set(cls['Class'] for cls in classes_to_schedule)
                missing_class_names = input_class_names - scheduled_class_names
                
                print(f"ERROR DEBUG: Missing classes: {missing_class_names}")
                
                # Create error info for each missing class
                for missing_class in missing_class_names:
                    # Find the class info from the original data
                    class_info = next((cls for cls in classes_to_schedule if cls['Class'] == missing_class), None)
                    if class_info:
                        error_info = {
                            'class_name': missing_class,
                            'teacher': class_info.get('Teacher', 'Unknown'),
                            'student_count': class_info.get('student_count', 0),
                            'conflicts': {
                                'student_conflicts': 0,
                                'teacher_conflicts': 0, 
                                'room_conflicts': 0,
                                'details': ['Could not find available time slot without conflicts']
                            }
                        }
                        response_data['scheduling_errors'].append(error_info)
                        print(f"ERROR DEBUG: Added error info for {missing_class}")
            
            # Check for manual assignment conflicts and create separate error categories
            manual_conflicts = getattr(scheduler, 'manual_conflicts', [])
            if manual_conflicts:
                print(f"MANUAL CONFLICT DEBUG: Found {len(manual_conflicts)} manual assignment conflicts")
                if 'scheduling_errors' not in response_data:
                    response_data['scheduling_errors'] = []
                if 'manual_assignment_warnings' not in response_data:
                    response_data['manual_assignment_warnings'] = []
                
                # Separate manual conflicts into two categories
                for conflict in manual_conflicts:
                    class_info = conflict['class']
                    class_name = class_info['Class']
                    
                    # Check if this class was eventually scheduled through auto-scheduling
                    if class_name not in scheduled_class_names:
                        # RED INDICATOR: Class was not scheduled at all - critical error
                        error_info = {
                            'class_name': class_name,
                            'teacher': class_info.get('Teacher', 'Unknown'),
                            'student_count': class_info.get('student_count', 0),
                            'requested_slot': conflict['requested_slot'],
                            'conflict_type': 'manual_assignment_blocked',
                            'severity': 'critical',  # Red indicator
                            'conflicts': {
                                'student_conflicts': len([c for c in conflict['conflicts'] if 'student conflict' in c]),
                                'teacher_conflicts': len([c for c in conflict['conflicts'] if 'teacher conflict' in c]),
                                'room_conflicts': len([c for c in conflict['conflicts'] if 'room conflict' in c]),
                                'details': conflict['conflicts']
                            }
                        }
                        response_data['scheduling_errors'].append(error_info)
                        print(f"MANUAL CONFLICT DEBUG: Added critical manual conflict for {class_name} at {conflict['requested_slot']} (class not auto-scheduled)")
                    else:
                        # YELLOW INDICATOR: Class was auto-scheduled but not at manual settings - warning
                        warning_info = {
                            'class_name': class_name,
                            'teacher': class_info.get('Teacher', 'Unknown'),
                            'student_count': class_info.get('student_count', 0),
                            'requested_slot': conflict['requested_slot'],
                            'conflict_type': 'manual_assignment_ignored',
                            'severity': 'warning',  # Yellow indicator
                            'conflicts': {
                                'student_conflicts': len([c for c in conflict['conflicts'] if 'student conflict' in c]),
                                'teacher_conflicts': len([c for c in conflict['conflicts'] if 'teacher conflict' in c]),
                                'room_conflicts': len([c for c in conflict['conflicts'] if 'room conflict' in c]),
                                'details': conflict['conflicts']
                            }
                        }
                        response_data['manual_assignment_warnings'].append(warning_info)
                        print(f"MANUAL CONFLICT DEBUG: Added manual assignment warning for {class_name} at {conflict['requested_slot']} (class auto-scheduled elsewhere)")
                
                # Mark as partial schedule if there are critical manual conflicts or manual assignment warnings
                has_critical_conflicts = any(
                    conflict['class']['Class'] not in scheduled_class_names 
                    for conflict in manual_conflicts
                )
                has_manual_warnings = len(response_data.get('manual_assignment_warnings', [])) > 0
                
                if has_critical_conflicts or has_manual_warnings:
                    response_data['partial_schedule'] = True
                    response_data['has_manual_conflicts'] = True
            
            # CRITICAL FIX: Convert the generated schedule back to session_assignments format
            # This ensures drag/drop conflict detection uses the current schedule data
            updated_session_assignments = None
            
            # Only create new session assignments if we don't already have valid ones
            if success and not manual_session_assignments:
                updated_session_assignments = {}
                
                for class_name in selected_classes:
                    # Initialize session assignments for each selected class
                    class_info = None
                    for cls in classes_to_schedule:
                        if cls['Class'] == class_name:
                            class_info = cls
                            break
                    
                    if class_info:
                        # Calculate expected number of sessions based on units
                        units = class_info.get('Units', 0)
                        # Also check lowercase 'units' for compatibility
                        if units == 0:
                            units = class_info.get('units', 0)
                        if isinstance(units, str):
                            try:
                                units = int(float(units))  # Handle float strings like "8.0"
                            except ValueError:
                                units = 0
                        
                        # Determine number of sessions based on credit hours
                        if units == 4:
                            num_sessions = 1
                        elif units == 8:
                            num_sessions = 2  
                        elif units == 12:
                            num_sessions = 3
                        else:
                            # Stop processing and return error for invalid credit hours
                            error_msg = f"ERROR: Invalid credit hours ({units}) for class '{class_name}'. Only 4, 8, or 12 credit hours are supported."
                            print(error_msg)
                            # Don't overwrite manual_session_assignments on error
                            return jsonify({
                                'success': False,
                                'error': error_msg,
                                'schedule': None
                            })
                        
                        # Initialize with the correct number of "Open" sessions 
                        updated_session_assignments[class_name] = []
                        for i in range(num_sessions):
                            updated_session_assignments[class_name].append({
                                'day': 'Open',
                                'period': 'Open', 
                                'room': 'Open'
                            })
            
            # Now populate with actual scheduled sessions (only if we created new session assignments)
            if updated_session_assignments is not None:
                for day in enhanced_schedule:
                    for period_str in enhanced_schedule[day]:
                        period = int(period_str) if str(period_str).isdigit() else period_str
                        for class_session in enhanced_schedule[day][period_str]:
                            class_name = class_session['Class']
                            room = class_session.get('room', 'Open')
                            
                            # Find the first available session slot for this class
                            # Handle potential trailing spaces in class names
                            matching_key = None
                            for key in updated_session_assignments.keys():
                                if key.strip() == class_name.strip():
                                    matching_key = key
                                    break
                            
                            if matching_key:
                                for session_idx, session in enumerate(updated_session_assignments[matching_key]):
                                    if session['day'] == 'Open' and session['period'] == 'Open':
                                        updated_session_assignments[matching_key][session_idx] = {
                                            'day': day,
                                            'period': period,
                                            'room': room
                                        }
                                        break
            
            # Update the global session assignments and save to file only if we created new ones
            if updated_session_assignments is not None:
                manual_session_assignments = updated_session_assignments
                
                # Save updated session assignments to file
                schedule_data = load_schedule_data() or {}
                schedule_data['selected_classes'] = selected_classes
                schedule_data['session_assignments'] = updated_session_assignments
            else:
                # Save existing manual session assignments
                schedule_data = load_schedule_data() or {}
                schedule_data['selected_classes'] = selected_classes
                schedule_data['session_assignments'] = manual_session_assignments
            schedule_data['timestamp'] = datetime.now().isoformat()
            schedule_data['version'] = '1.0'
            
            with open('last_schedule.json', 'w') as f:
                json.dump(schedule_data, f, indent=2)
            
            if updated_session_assignments is not None:
                print(f"SYNC DEBUG: Updated session_assignments with {len(updated_session_assignments)} classes")
                for class_name, sessions in updated_session_assignments.items():
                    scheduled_sessions = [s for s in sessions if s['day'] != 'Open']
                    print(f"  {class_name}: {len(scheduled_sessions)} scheduled sessions out of {len(sessions)} total")
            else:
                print("SYNC DEBUG: No new session assignments created, using existing manual assignments")
            
            return jsonify(response_data)
        else:
            # Only return failure if NO classes could be scheduled
            return jsonify({
                'success': False,
                'error': 'Could not schedule any classes',
                'unscheduled': unscheduled,
                'can_try_period_7': not use_period_7
            })
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/debug/students')
def debug_students():
    """Debug endpoint to examine student enrollment data"""
    global classes_data
    
    if not classes_data:
        return jsonify({'error': 'No class data loaded'})
    
    # Find the specific classes we're debugging
    btcm_class = None
    gela_class = None
    
    for class_info in classes_data:
        if 'BTCM 101 P Christian Life' in class_info['Class']:
            btcm_class = class_info
        elif 'GELA 203 B English as a Second Language 3' in class_info['Class']:
            gela_class = class_info
    
    result = {
        'btcm_class': btcm_class,
        'gela_class': gela_class
    }
    
    if btcm_class and gela_class:
        # Parse students and check for conflicts
        scheduler = ClassScheduler()
        btcm_students = scheduler.parse_students(btcm_class['Students'])
        gela_students = scheduler.parse_students(gela_class['Students'])
        
        result['btcm_parsed_students'] = btcm_students
        result['gela_parsed_students'] = gela_students
        result['intersection'] = list(set(btcm_students).intersection(set(gela_students)))
        
        conflicts = scheduler.check_conflicts(btcm_class, gela_class)
        result['conflicts_detected'] = conflicts
    
    return jsonify(result)

@app.route('/set_selection', methods=['POST'])
def set_selection():
    global selected_classes, manual_room_assignments, manual_period_assignments, manual_session_assignments, current_schedule
    
    try:
        data = request.get_json()
        selected_classes = data.get('selected_classes', [])
        all_session_assignments = data.get('session_assignments', {})
        
        # Filter session assignments to only include selected classes
        selected_classes_set = set(selected_classes)
        manual_session_assignments = {
            class_name: sessions 
            for class_name, sessions in all_session_assignments.items()
            if class_name in selected_classes_set
        }
        
        # DEBUG: Log what's being received from frontend
        print("DEBUG SET_SELECTION: Received data from frontend:")
        for class_name, sessions in manual_session_assignments.items():
            print(f"  {class_name}: {len(sessions)} sessions - {sessions}")
        
        # Convert session assignments to the old format for backward compatibility
        # This is a fallback for classes that don't have specific session assignments
        manual_room_assignments = {}
        manual_period_assignments = {}
        
        # Clear the current schedule when selections change
        # This ensures users see a blank generate page after making changes
        current_schedule = None
        
        print(f"Selected classes: {selected_classes}")
        print(f"Manual session assignments: {manual_session_assignments}")
        print("Current schedule cleared due to selection changes")
        
        # Save schedule data to local JSON file when selection is confirmed
        save_schedule_data()
        
        return jsonify({
            'success': True,
            'selected_count': len(selected_classes)
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/get_schedule_status')
def get_schedule_status():
    """Check if there's currently a schedule available"""
    global current_schedule
    return jsonify({
        'has_schedule': current_schedule is not None
    })

@app.route('/check_saved_schedule')
def check_saved_schedule():
    """Check if there's a saved schedule file available"""
    has_saved = os.path.exists(SCHEDULE_DATA_FILE)
    return jsonify({
        'has_saved_schedule': has_saved
    })

@app.route('/load_saved_schedule', methods=['POST'])
def load_saved_schedule():
    """Load the saved schedule data and restore form state"""
    global selected_classes, manual_session_assignments
    
    try:
        schedule_data = load_schedule_data()
        if not schedule_data:
            return jsonify({
                'success': False,
                'error': 'No saved schedule found'
            })
        
        # Restore the form data
        selected_classes = schedule_data.get('selected_classes', [])
        manual_session_assignments = schedule_data.get('session_assignments', {})
        
        # DEBUG: Check if any class has incorrect session counts
        for class_name, sessions in manual_session_assignments.items():
            print(f"DEBUG LOAD: {class_name} has {len(sessions)} sessions")
        
        print(f"Restored {len(selected_classes)} selected classes")
        print(f"Restored session assignments for {len(manual_session_assignments)} classes")
        
        return jsonify({
            'success': True,
            'selected_classes': selected_classes,
            'session_assignments': manual_session_assignments,
            'timestamp': schedule_data.get('timestamp', 'Unknown')
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/test_pdf')
def test_pdf():
    """Test PDF generation with simple content"""
    try:
        html_content = "<html><body><h1>Test PDF Export</h1><p>This is a test</p></body></html>"
        pdf_buffer = BytesIO()
        weasyprint.HTML(string=html_content).write_pdf(pdf_buffer)
        pdf_buffer.seek(0)
        
        return send_file(
            pdf_buffer,
            as_attachment=True,
            download_name='test.pdf',
            mimetype='application/pdf'
        )
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/export_pdf')
def export_pdf():
    global current_schedule
    
    print("PDF export requested")  # Debug
    
    if not current_schedule:
        print("No current schedule available")  # Debug
        return jsonify({'success': False, 'error': 'No schedule to export'})
    
    try:
        print("Generating HTML for PDF...")  # Debug
        
        # Compute room conflicts for export summary
        def compute_room_conflicts(schedule):
            conflicts = []
            display_periods = [1, 2, 3, 4, 5, 6, 7, 11, 8, 9, 10]
            for day in DAYS:
                if day not in schedule:
                    continue
                for period in display_periods:
                    classes = schedule.get(day, {}).get(period, [])
                    if not classes:
                        continue
                    room_map = {}
                    for ci in classes:
                        room = ci.get('room') or 'TBD'
                        if room in ('Open', 'TBD'):
                            continue
                        room_map.setdefault(room, []).append(ci.get('Class'))
                    for room, class_list in room_map.items():
                        if len(class_list) > 1:
                            conflicts.append({
                                'day': day,
                                'period': int(period),
                                'room': room,
                                'classes': class_list
                            })
            return conflicts

        room_conflicts = compute_room_conflicts(current_schedule)
        conflict_keys = [f"{item['day']}-{item['period']}-{item['room']}" for item in room_conflicts]

        # Generate HTML for PDF
        html_content = render_template('schedule_pdf.html', 
                                     schedule=current_schedule, 
                                     periods=PERIODS, 
                                     days=DAYS,
                                     rooms=ROOMS,
                                     class_colors=class_colors,
                                     room_conflicts=room_conflicts,
                                     room_conflict_keys=conflict_keys,
                                     datetime=datetime)
        
        print(f"HTML content length: {len(html_content)}")  # Debug
        print("HTML generated successfully, creating PDF...")  # Debug
        
        # Generate PDF
        pdf_buffer = BytesIO()
        
        if WEASYPRINT_AVAILABLE:
            # Try to create WeasyPrint HTML object
            try:
                html_doc = weasyprint.HTML(string=html_content)
                print("WeasyPrint HTML object created successfully")  # Debug
                
                html_doc.write_pdf(pdf_buffer)
                print("PDF written to buffer successfully")  # Debug
                
                pdf_buffer.seek(0)
                pdf_size = len(pdf_buffer.getvalue())
                print(f"PDF generated successfully, size: {pdf_size} bytes")  # Debug
                
                return send_file(
                    pdf_buffer,
                    as_attachment=True,
                    download_name=f'class_schedule_{datetime.now().strftime("%Y%m%d_%H%M")}.pdf',
                    mimetype='application/pdf'
                )
            except Exception as pdf_error:
                print(f"PDF generation failed: {pdf_error}")  # Debug
                # Fall through to HTML export
        
        # Fallback: Export as styled HTML file
        print("Exporting as styled HTML file (PDF not available)")  # Debug
        
        # Create a complete HTML document with proper styling
        complete_html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>GBBC Class Schedule</title>
    <style>
        @page {{
            size: A4 landscape;
            margin: 1cm;
        }}
        
        /* Force color printing - preserve background colors when printing */
        * {{
            print-color-adjust: exact !important;
            -webkit-print-color-adjust: exact !important;
            color-adjust: exact !important;
        }}
        
        body {{
            font-family: Arial, sans-serif;
            font-size: 10px;
            margin: 0;
            padding: 20px;
            background-color: white;
        }}
        
        .export-note {{
            background: #d1ecf1;
            border: 1px solid #bee5eb;
            padding: 15px;
            margin-bottom: 20px;
            border-radius: 5px;
            font-size: 14px;
        }}
        
        .header {{
            text-align: center;
            margin-bottom: 20px;
            border-bottom: 2px solid #333;
            padding-bottom: 10px;
        }}
        
        .header h1 {{
            margin: 0;
            font-size: 18px;
            color: #333;
        }}
        
        .header p {{
            margin: 5px 0 0 0;
            color: #666;
            font-size: 12px;
        }}
        
        .schedule-table {{
            width: 100%;
            border-collapse: collapse;
            margin: 0;
        }}
        
        .schedule-table th {{
            background-color: #667eea;
            color: white;
            padding: 8px 4px;
            text-align: center;
            font-weight: bold;
            border: 1px solid #333;
            font-size: 11px;
        }}
        
        .schedule-table td {{
            border: 1px solid #333;
            padding: 4px;
            vertical-align: top;
            height: 80px;
            width: 16.66%;
        }}
        
        .period-label {{
            background-color: #f0f0f0;
            font-weight: bold;
            text-align: center;
            width: 80px;
            font-size: 9px;
            line-height: 1.2;
        }}
        
        .period-label small {{
            font-size: 7px;
            font-weight: normal;
            color: #666;
            display: block;
            margin-top: 2px;
        }}
        
        .class-block {{
            background-color: transparent; /* Two-tone styling handled inline */
            color: white;
            border: 1px solid rgba(255,255,255,0.4);
            border-radius: 3px;
            padding: 3px;
            margin-bottom: 2px;
            font-size: 10px; /* Increased from 8px for better readability */
            overflow: hidden;
        }}
        
        .class-block:last-child {{
            margin-bottom: 0;
        }}
        
        .class-title {{
            font-weight: bold;
            color: white;
            margin-bottom: 1px;
            line-height: 1.1;
            font-size: 11px; /* Explicit size for class titles */
        }}
        
        .period-label {{
            background-color: #f0f0f0;
            font-weight: bold;
            text-align: center;
            width: 90px;
            font-size: 10px; /* Increased for better readability */
            line-height: 1.2;
            padding: 8px 4px;
            border: 1px solid #333;
        }}
        
        .period-label small {{
            font-size: 10px; /* Increased to 10px for better readability */
            font-weight: normal;
            color: #666;
            display: block;
            margin-top: 2px;
        }}
        
        /* Compressed height for empty periods */
        .empty-period-row td {{
            height: 25px !important; /* Much smaller for empty periods */
        }}
        
        .class-teacher {{
            color: rgba(255,255,255,0.9);
            font-size: 7px;
            line-height: 1.1;
        }}
        
        .class-room {{
            color: rgba(255,255,255,0.8);
            font-size: 7px;
            font-style: italic;
        }}
        
        .class-students {{
            color: rgba(255,255,255,0.9);
            font-size: 6px;
            margin-top: 1px;
            font-weight: 500;
        }}
        
        .chapel-period {{
            background-color: #fff3cd;
        }}
        
        .footer {{
            margin-top: 15px;
            font-size: 8px;
            color: #666;
            text-align: center;
        }}
        
        @media print {{
            .export-note {{ display: none !important; }}
            body {{ padding: 0; }}
            @page {{ size: landscape; margin: 1cm; }}
        }}
    </style>
</head>
<body>
    <div class="export-note">
        <strong>📄 HTML Schedule Export</strong><br>
        PDF export is not available on this server. You can print this page to PDF using your browser:<br>
        <strong>Ctrl+P → More settings → Save as PDF → Layout: Landscape</strong>
    </div>
    
    <div class="header">
        <h1>GBBC Weekly Class Schedule</h1>
        <p>Generated on {datetime.now().strftime('%B %d, %Y at %I:%M %p')}</p>
    </div>
    
    <table class="schedule-table">
        <thead>
            <tr>
                <th>Period</th>
                <th>Monday</th>
                <th>Tuesday</th>
                <th>Wednesday</th>
                <th>Thursday</th>
                <th>Friday</th>
            </tr>
        </thead>
        <tbody>"""
        
        # Generate the table body with the schedule data
        days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
        for period_num in [1, 2, 3, 4, 5, 6, 7, 11, 8, 9, 10]:  # Period 7b moved after Period 7
            # Check if this period has any classes
            period_has_classes = False
            for day in days:
                if current_schedule.get(day) and current_schedule[day].get(period_num):
                    period_has_classes = True
                    break
            
            # Apply empty-period-row class if no classes in this period
            row_class = ' class="empty-period-row"' if not period_has_classes else ''
            period_display = 'Period 7b' if period_num == 11 else f'Period {period_num}'
            complete_html += f"""
            <tr{row_class}>
                <td class="period-label {'chapel-period' if period_num == 3 else ''}">
                    {period_display}<br>
                    <small>"""
            
            # Add period times
            if period_num == 1: complete_html += "7:00am-7:50am"
            elif period_num == 2: complete_html += "8:00am-8:50am"
            elif period_num == 3: complete_html += "9:00am-9:30am<br>(Chapel)"
            elif period_num == 4: complete_html += "9:40am-10:30am"
            elif period_num == 5: complete_html += "10:40am-11:30am"
            elif period_num == 6: complete_html += "11:40am-12:30pm"
            elif period_num == 7: complete_html += "12:40pm-1:30pm"
            elif period_num == 8: complete_html += "5:30pm-6:20pm"
            elif period_num == 9: complete_html += "6:30pm-7:20pm"
            elif period_num == 10: complete_html += "7:30pm-8:20pm"
            elif period_num == 11: complete_html += "1:00pm-3:00pm<br>(Period 7b)"
            
            complete_html += """</small>
                </td>"""
            
            # Add cells for each day
            for day in days:
                complete_html += "<td>"
                if current_schedule.get(day) and current_schedule[day].get(period_num):
                    for class_info in current_schedule[day][period_num]:
                        class_color_data = class_colors.get(class_info.get('Class', ''), {
                            'header': '#667eea', 
                            'body': '#8a9bf2'
                        })
                        teacher_name = class_info.get('teacher_abbreviated', class_info.get('Teacher', ''))
                        room_name = class_info.get('room_abbreviated', class_info.get('room', 'TBD'))
                        # Escape teacher name for safe HTML attributes
                        escaped_teacher = class_info.get('Teacher', '').replace('"', '&quot;').replace("'", '&#39;')
                        
                        # Determine if this is a single-session class for drag & drop
                        class_units = class_info.get('Units', '8')
                        frequency = get_class_frequency(class_units)
                        is_single_session = (frequency == 1)
                        
                        # Escape class name for data attributes
                        escaped_class_name = class_info.get('Class', '').replace('"', '&quot;').replace("'", '&#39;')
                        
                        # Build CSS classes and attributes
                        css_classes = "class-block clickable-class"
                        drag_attrs = ""
                        cursor_style = "cursor: pointer;"
                        
                        if is_single_session:
                            css_classes += " draggable-class"
                            drag_attrs = f'draggable="true" data-class-name="{escaped_class_name}" data-current-day="{day}" data-current-period="{period_num}"'
                            cursor_style = "cursor: grab;"
                        else:
                            css_classes += " multi-session-class"
                        # Conflict highlight inline style for this class body
                        _room = class_info.get('room') or 'TBD'
                        _key = f"{day}-{int(period_num)}-{_room}"
                        _conflict_style = "border: 2px solid #c0392b; box-shadow: 0 0 0 2px rgba(192,57,43,0.15);" if (_room not in ('Open','TBD') and _key in conflict_keys) else ""

                        complete_html += f"""
                        <div class="{css_classes}" data-teacher="{escaped_teacher}" {drag_attrs} style="{cursor_style}">
                            <div class="class-title" style="background-color: {class_color_data['header']}; padding: 2px 3px; margin: -3px -3px 0 -3px; border-radius: 3px 3px 0 0; color: white;">
                                {class_info.get('Class', '')}
                                {'<span style="float: right; font-size: 8px; opacity: 0.8;">📌</span>' if not is_single_session else ''}
                            </div>
                            <div class="class-body" style="background-color: {class_color_data['body']}; padding: 1px 3px; margin: 0 -3px -3px -3px; border-radius: 0 0 3px 3px; font-size: 10px; line-height: 1.1; color: white; {_conflict_style}">
                                <div class="class-details" style="color: white;"><strong>{teacher_name}</strong> • <span class="room-indicator">{room_name}</span> • {class_info.get('student_count', 0)} students</div>
                            </div>
                        </div>"""
                complete_html += "</td>"
            
            complete_html += "</tr>"
        
        complete_html += """
        </tbody>
    </table>
    """

        # Append room conflict summary if present
        if room_conflicts:
            items_html = ''.join([
                f"<div>• {item['day']} Period {item['period']} — <strong>{item['room']}</strong> used by {', '.join(item['classes'])}</div>"
                for item in room_conflicts
            ])
            complete_html += (
                "<div style=\"margin-top:10px;\">"
                "<div style=\"background:#fff3f3;border:1px solid #ffcccc;padding:10px;border-radius:4px;\">"
                f"<strong style=\"color:#c0392b;\">Room Conflicts: {len(room_conflicts)}</strong>"
                "</div>"
                f"<div style=\"font-size:12px;color:#333;padding:8px 0;\">{items_html}</div>"
                "</div>"
            )

        complete_html += """
    
    <!-- Teacher filter indicator -->
    <div id="teacherFilterIndicator" style="display: none; margin-top: 15px; padding: 10px; background-color: #e3f2fd; border-radius: 5px; border-left: 4px solid #2196f3;">
        <strong>🔍 Showing classes for: <span id="currentTeacher"></span></strong>
        <button onclick="clearTeacherFilter()" style="margin-left: 15px; padding: 5px 10px; background: #f44336; color: white; border: none; border-radius: 3px; cursor: pointer;">Show All Classes</button>
    </div>
    
    <div class="footer">
        <p>Class Schedule Generator - Conflict-free scheduling with room assignments</p>
    </div>

    <script>
        let currentTeacherFilter = null;
        
        // Debug function
        console.log('Teacher filtering script loaded');
        console.log('Number of clickable-class elements found:', document.querySelectorAll('.clickable-class').length);
        
        function filterByTeacher(teacherName) {
            if (currentTeacherFilter === teacherName) {
                // Already filtered by this teacher, do nothing
                return;
            }
            
            currentTeacherFilter = teacherName;
            
            // Hide all class blocks
            document.querySelectorAll('.class-block').forEach(block => {
                block.style.display = 'none';
                block.style.opacity = '0.3';
            });
            
            // Show only blocks for this teacher with highlighting
            document.querySelectorAll(`[data-teacher="${teacherName}"]`).forEach(block => {
                block.style.display = 'block';
                block.style.opacity = '1';
                block.style.transform = 'scale(1.02)';
                block.style.boxShadow = '0 2px 8px rgba(0,0,0,0.3)';
                block.style.transition = 'all 0.2s ease';
            });
            
            // Show filter indicator
            document.getElementById('teacherFilterIndicator').style.display = 'block';
            document.getElementById('currentTeacher').textContent = teacherName;
            
            console.log(`Filtered to show only classes for teacher: ${teacherName}`);
        }
        
        function clearTeacherFilter() {
            currentTeacherFilter = null;
            
            // Show all class blocks and remove highlighting
            document.querySelectorAll('.class-block').forEach(block => {
                block.style.display = 'block';
                block.style.opacity = '1';
                block.style.transform = 'none';
                block.style.boxShadow = 'none';
                block.style.transition = 'all 0.2s ease';
            });
            
            // Hide filter indicator
            document.getElementById('teacherFilterIndicator').style.display = 'none';
            
            console.log('Cleared teacher filter - showing all classes');
        }
        
        // Event delegation for class block clicks
        document.addEventListener('click', function(event) {
            console.log('Click detected on:', event.target);
            const classBlock = event.target.closest('.clickable-class');
            console.log('Closest clickable-class:', classBlock);
            
            if (classBlock) {
                // Clicked on a class block
                console.log('Clicked on class block!');
                event.stopPropagation();
                const teacherName = classBlock.getAttribute('data-teacher');
                console.log('Teacher name:', teacherName);
                if (teacherName) {
                    console.log('Calling filterByTeacher with:', teacherName);
                    filterByTeacher(teacherName);
                }
            } else if (!event.target.closest('#teacherFilterIndicator') && currentTeacherFilter !== null) {
                // Clicked outside - clear filter
                console.log('Clicked outside - clearing filter');
                clearTeacherFilter();
            }
        });
        
        // Add visual feedback for hovering using event delegation
        document.addEventListener('mouseenter', function(event) {
            if (event.target.closest('.clickable-class') && !currentTeacherFilter) {
                const block = event.target.closest('.clickable-class');
                block.style.transform = 'scale(1.05)';
                block.style.transition = 'transform 0.1s ease';
            }
        }, true);
        
        document.addEventListener('mouseleave', function(event) {
            if (event.target.closest('.clickable-class') && !currentTeacherFilter) {
                const block = event.target.closest('.clickable-class');
                block.style.transform = 'none';
            }
        }, true);
    </script>
</body>
</html>"""
        
        # Create response with styled HTML file
        response = make_response(complete_html)
        response.headers['Content-Type'] = 'text/html; charset=utf-8'
        response.headers['Content-Disposition'] = f'attachment; filename=class_schedule_{datetime.now().strftime("%Y%m%d_%H%M")}.html'
        
        return response
        
    except ImportError as e:
        print(f"WeasyPrint import error: {e}")  # Debug
        error_msg = 'PDF generation library not available. Please install WeasyPrint.'
        return jsonify({'success': False, 'error': error_msg})
    except Exception as e:
        print(f"PDF export error: {str(e)}")  # Debug
        import traceback
        traceback.print_exc()
        
        # Return a JSON error response instead of trying HTML fallback
        error_msg = f'PDF generation failed: {str(e)}'
        print(f"Returning error: {error_msg}")  # Debug
        return jsonify({'success': False, 'error': error_msg})

# Drag and Drop API Endpoints
@app.route('/api/get_valid_slots', methods=['POST'])
def get_valid_slots():
    """Get valid time slots for dragging an individual class session"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No data provided'})
        
        class_name = data.get('class_name')
        session_index = data.get('session_index', 0)  # New parameter for session index
        current_day = data.get('current_day')
        current_period = data.get('current_period')
        
        print(f"DEBUG GET_VALID_SLOTS: Checking valid slots for {class_name} session {session_index}")
        print(f"DEBUG GET_VALID_SLOTS: Current position: {current_day} P{current_period}")
        
        if not class_name:
            return jsonify({'success': False, 'error': 'Class name required'})
        
        # Use current generated schedule instead of saved session assignments
        global classes_data, current_schedule, selected_classes
        if not current_schedule:
            return jsonify({'success': False, 'error': 'No generated schedule found. Please generate a schedule first.'})
        
        if not classes_data:
            return jsonify({'success': False, 'error': 'No classes data available'})
        
        # Find the specific class
        class_info = None
        for cls in classes_data:
            if clean_text_data(cls['Class']) == class_name:
                class_info = cls
                break
        
        if not class_info:
            return jsonify({'success': False, 'error': f'Class {class_name} not found'})
        
        # Get current session assignments from the generated schedule
        filtered_session_assignments = convert_schedule_to_sessions(current_schedule, selected_classes)
        print(f"DEBUG INITIAL SESSION ASSIGNMENTS: {filtered_session_assignments}")
        print(f"DEBUG CURRENT_SCHEDULE STRUCTURE: {json.dumps(current_schedule, indent=2)}")
        
        # Filter classes_data to only include currently selected classes
        selected_classes_set = set(selected_classes)
        filtered_classes_data = [
            cls for cls in classes_data 
            if clean_text_data(cls['Class']) in selected_classes_set
        ]
        
        # Resolve the actual session index by matching current position
        resolved_index = session_index
        if class_name in filtered_session_assignments:
            for idx, sess in enumerate(filtered_session_assignments[class_name]):
                if sess.get('day') == current_day and sess.get('period') == current_period:
                    resolved_index = idx
                    break

        # Find valid slots
        valid_slots = []
        for day in DAYS:
            for period in range(1, 12):  # Include all periods including Period 7b (11)
                # Skip the current slot
                if day == current_day and period == current_period:
                    continue
                
                # Test if this session can be placed here
                # Use filtered_session_assignments as the base, not scheduler.manual_session_assignments
                temp_assignments = {}
                for cls, sessions in filtered_session_assignments.items():
                    temp_assignments[cls] = [dict(session) for session in sessions]  # Deep copy
                
                if class_name in temp_assignments and len(temp_assignments[class_name]) > resolved_index:
                    # Update only the specific session being dragged
                    temp_assignments[class_name][resolved_index] = {'day': day, 'period': period, 'room': 'Open'}
                else:
                    # Class not in schedule yet, create new session
                    temp_assignments[class_name] = [{'day': day, 'period': period, 'room': 'Open'}]
                
                # Create temporary scheduler with new assignment to test conflicts
                temp_scheduler = ClassScheduler(classes_data)
                temp_scheduler.manual_session_assignments = temp_assignments
                
                # Check for conflicts at this slot using direct session assignment checking
                # Pass the temp_assignments which includes the proposed move to properly detect conflicts
                print(f"DEBUG TEMP_ASSIGNMENTS for {day} P{period}: Testing drop of {class_name} session {session_index}")
                if class_name in temp_assignments:
                    print(f"DEBUG TEMP_ASSIGNMENTS: {class_name} sessions: {temp_assignments[class_name]}")
                conflicts = check_slot_conflicts_directly(
                    filtered_classes_data,
                    temp_assignments,
                    day,
                    period,
                    class_name,
                    resolved_index,
                    current_day,
                    current_period
                )
                
                slot_info = {
                    'day': day,
                    'period': period,
                    'slot_id': f"{day}-{period}",
                    'valid': len(conflicts) == 0,
                    'conflicts': conflicts
                }
                valid_slots.append(slot_info)
        
        return jsonify({'success': True, 'valid_slots': valid_slots})
        
    except Exception as e:
        print(f"Error in get_valid_slots: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/move_class', methods=['POST'])  
def move_class():
    """Move an individual class session to a new time slot"""
    # Access global variables
    global classes_data, manual_session_assignments
    
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No data provided'})
        
        class_name = data.get('class_name')
        session_index = data.get('session_index', 0)  # New parameter for session index
        new_day = data.get('new_day')
        new_period = data.get('new_period')
        current_day = data.get('current_day')
        current_period = data.get('current_period')
        print(f"MOVE_CLASS DEBUG: Moving {class_name} session {session_index}")
        print(f"MOVE_CLASS DEBUG: FROM {current_day} P{current_period} TO {new_day} P{new_period}", flush=True)
        
        if not all([class_name, new_day, new_period is not None]):
            return jsonify({'success': False, 'error': 'Missing required parameters'})
        
        # Use the current generated schedule data instead of saved session assignments
        global current_schedule
        if not current_schedule:
            return jsonify({'success': False, 'error': 'No generated schedule found. Please generate a schedule first.'})
        
        # Convert current_schedule to session assignments format for manipulation
        session_assignments = convert_schedule_to_sessions(current_schedule, selected_classes)
        if class_name not in session_assignments:
            session_assignments[class_name] = []

        # Resolve the actual index of the dragged session by matching its current position
        resolved_index = session_index
        if current_day and current_period is not None:
            for idx, sess in enumerate(session_assignments[class_name]):
                if sess.get('day') == current_day and sess.get('period') == int(current_period):
                    resolved_index = idx
                    break

        # Ensure we have enough sessions for the resolved_index
        while len(session_assignments[class_name]) <= resolved_index:
            session_assignments[class_name].append({'day': 'Open', 'period': 'Open', 'room': 'Open'})

        # Store original session assignment for potential rollback and to preserve room
        original_session = dict(session_assignments[class_name][resolved_index])
        print(f"MOVE_CLASS DEBUG: Original session: {original_session}")
        
        # Update only the specific session being moved (preserve room)
        preserved_room = original_session.get('room', 'Open')
        session_assignments[class_name][resolved_index] = {'day': new_day, 'period': int(new_period), 'room': preserved_room}
        print(f"MOVE_CLASS DEBUG: Updated session assignments")
        
        # Check for duplicate classes in the same slot (post-drop validation)
        print(f"MOVE_CLASS DEBUG: Starting post-drop validation for {class_name} session {session_index} to {new_day} P{new_period}")
        print(f"MOVE_CLASS DEBUG: Updated session_assignments: {session_assignments}")
        duplicate_detected = False
        sessions_in_target_slot = []
        
        for cls_name, sessions in session_assignments.items():
            for session_idx, session in enumerate(sessions):
                session_day = session.get('day')
                session_period = session.get('period')
                
                if session_day == new_day and session_period == int(new_period):
                    sessions_in_target_slot.append({
                        'class_name': cls_name,
                        'session_index': session_idx,
                        'session': session
                    })
                    print(f"MOVE_CLASS DEBUG: Found session in target slot: {cls_name} session {session_idx} at {session_day} P{session_period}")
        
        print(f"POST-DROP VALIDATION: Found {len(sessions_in_target_slot)} sessions in {new_day} P{new_period}", flush=True)
        for session_info in sessions_in_target_slot:
            print(f"  - {session_info['class_name']} session {session_info['session_index']}", flush=True)
        
        # Check for duplicate classes (multiple sessions of same class in same slot)
        class_names_in_slot = [s['class_name'] for s in sessions_in_target_slot]
        unique_classes = set(class_names_in_slot)
        
        if len(class_names_in_slot) > len(unique_classes):
            # Found duplicates - revert the move
            print(f"POST-DROP VALIDATION: DUPLICATE DETECTED! Multiple sessions of same class in {new_day} P{new_period}", flush=True)
            session_assignments[class_name][session_index] = original_session
            duplicate_detected = True
        
        # Also check for teacher conflicts (same teacher in same slot)
        if not duplicate_detected:
            # Use uploaded classes data
            current_classes_data = classes_data
            if not current_classes_data:
                print("POST-DROP VALIDATION: No classes data available - please upload a CSV file first", flush=True)
                return jsonify({
                    'success': False, 
                    'error': 'No classes data available. Please upload a CSV file first.'
                })
            
            # Get teacher info for each class in the slot
            teachers_in_slot = []
            print(f"POST-DROP VALIDATION: current_classes_data length: {len(current_classes_data)}", flush=True)
            print(f"POST-DROP VALIDATION: Looking up teachers for {len(sessions_in_target_slot)} sessions", flush=True)
            for session_info in sessions_in_target_slot:
                class_name_to_find = session_info['class_name']
                print(f"POST-DROP VALIDATION: Looking for teacher of '{class_name_to_find}'", flush=True)
                teacher_found = False
                for cls in current_classes_data:
                    if clean_text_data(cls['Class']) == class_name_to_find:
                        teacher = cls.get('Teacher', '')
                        teachers_in_slot.append(teacher)
                        print(f"POST-DROP VALIDATION: Found teacher '{teacher}' for '{class_name_to_find}'", flush=True)
                        teacher_found = True
                        break
                if not teacher_found:
                    print(f"POST-DROP VALIDATION: No teacher found for '{class_name_to_find}'", flush=True)
                    print(f"POST-DROP VALIDATION: Available class names: {[clean_text_data(cls['Class']) for cls in current_classes_data[:5]]}", flush=True)
            
            unique_teachers = set(teachers_in_slot)
            print(f"POST-DROP VALIDATION: Teachers in slot: {teachers_in_slot}, unique: {list(unique_teachers)}", flush=True)
            if len(teachers_in_slot) > len(unique_teachers):
                print(f"POST-DROP VALIDATION: TEACHER CONFLICT DETECTED! Same teacher has multiple classes in {new_day} P{new_period}", flush=True)
                session_assignments[class_name][session_index] = original_session
                duplicate_detected = True
        
        # Also check for student conflicts (same student in same slot)
        if not duplicate_detected:
            # Get all students for each class in the slot
            all_students_in_slot = []
            print(f"POST-DROP VALIDATION: Checking for student conflicts among {len(sessions_in_target_slot)} sessions", flush=True)
            for session_info in sessions_in_target_slot:
                class_name_to_find = session_info['class_name']
                for cls in current_classes_data:
                    if clean_text_data(cls['Class']) == class_name_to_find:
                        students_str = cls.get('Students', '')
                        if students_str:
                            # Split student list and clean each student name
                            students = [s.strip() for s in str(students_str).split(';') if s.strip()]
                            all_students_in_slot.extend(students)
                            print(f"POST-DROP VALIDATION: Found {len(students)} students for '{class_name_to_find}': {students[:3]}{'...' if len(students) > 3 else ''}", flush=True)
                        break
            
            # Check for duplicate students
            unique_students = set(all_students_in_slot)
            print(f"POST-DROP VALIDATION: Total students in slot: {len(all_students_in_slot)}, unique: {len(unique_students)}", flush=True)
            if len(all_students_in_slot) > len(unique_students):
                print(f"POST-DROP VALIDATION: STUDENT CONFLICT DETECTED! Same student has multiple classes in {new_day} P{new_period}", flush=True)
                session_assignments[class_name][session_index] = original_session
                duplicate_detected = True
        
        if duplicate_detected:
            # Save the reverted schedule
            schedule_data = load_schedule_data() or {}
            schedule_data['selected_classes'] = selected_classes
            schedule_data['session_assignments'] = session_assignments
            schedule_data['timestamp'] = datetime.now().isoformat()
            schedule_data['version'] = '1.0'
            
            with open('last_schedule.json', 'w') as f:
                json.dump(schedule_data, f, indent=2)
            
            return jsonify({
                'success': False, 
                'error': 'Cannot place multiple sessions with the same teacher or student in the same time slot. Move reverted.'
            })
        
        # Update the current_schedule with the new session position
        update_current_schedule_with_move(
            class_name,
            resolved_index,
            new_day,
            new_period,
            session_assignments,
            current_day=current_day,
            current_period=current_period,
            preserved_room=preserved_room
        )
        
        # Update the global manual session assignments 
        global manual_session_assignments
        manual_session_assignments = session_assignments
        
        # Save the successful move to JSON file (use central saver)
        save_schedule_data()
        
        print(f"MOVE_CLASS DEBUG: Successfully moved {class_name} session {session_index} to {new_day} P{new_period}")
        print(f"MOVE_CLASS DEBUG: Saved updated session assignments to JSON file")
        
        # Build response using preserved room; room conflicts will be handled on next generate
        room_assignment = preserved_room
        room_conflict = False

        return jsonify({
            'success': True,
            'new_assignment': {
                'day': new_day,
                'period': new_period,
                'room': room_assignment,
                'room_conflict': room_conflict
            }
        })
        
    except Exception as e:
        print(f"Error in move_class: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)})

def check_slot_conflicts(scheduler, class_info, day, period):
    """Check for conflicts when placing a class in a specific slot"""
    conflicts = []
    
    if day in scheduler.schedule and period in scheduler.schedule[day]:
        existing_classes = scheduler.schedule[day][period]
        
        for existing_class in existing_classes:
            class_conflicts = scheduler.check_conflicts(class_info, existing_class)
            if class_conflicts:
                for conflict in class_conflicts:
                    if conflict['type'] == 'teacher':
                        conflicts.append(f"Teacher conflict with {existing_class['Class']}")
                    elif conflict['type'] == 'student':
                        student_names = ', '.join(conflict.get('shared_students', [])[:3])  # Show first 3
                        conflicts.append(f"Student conflict with {existing_class['Class']} ({student_names})")
    
    return conflicts

def check_slot_conflicts_directly(classes_data, session_assignments, target_day, target_period, dragged_class_name, dragged_session_index, current_day=None, current_period=None):
    """Check for conflicts by directly examining session assignments rather than scheduler state"""
    print(f"DEBUG DIRECT CONFLICT: Checking {target_day} P{target_period} for {dragged_class_name}")
    print(f"DEBUG DIRECT CONFLICT: Dragged from {current_day} P{current_period}")
    conflicts = []
    
    # Get the class info for the dragged class
    dragged_class_info = None
    for cls in classes_data:
        if clean_text_data(cls['Class']) == dragged_class_name:
            dragged_class_info = cls
            break
    
    if not dragged_class_info:
        print(f"DEBUG DIRECT CONFLICT: Could not find class info for {dragged_class_name}")
        return conflicts
    
    print(f"DEBUG DIRECT CONFLICT: Found dragged class: {dragged_class_info['Teacher']}")
    
    # Check all sessions in the target slot - but exclude the one being moved
    sessions_found_in_slot = 0
    for class_name, sessions in session_assignments.items():
        for session_idx, session in enumerate(sessions):
            session_day = session.get('day')
            session_period = session.get('period')
            
            # Skip if this is not in the target slot
            if session_day != target_day or session_period != target_period:
                continue
                
            # Skip the session that was just moved TO this slot (the one we're testing)
            # When we create temp_assignments, we move the session from old position to new position
            # So in the target slot, we should find the dragged class session, but we shouldn't count it as a conflict with itself
            if class_name == dragged_class_name and session_idx == dragged_session_index:
                print(f"DEBUG DIRECT CONFLICT: Skipping the dragged session itself in the target slot")
                continue
            
            # CRITICAL FIX: Prevent dropping any session of the same class onto any other session of the same class
            # This ensures consistent behavior regardless of which session index is being dragged
            if class_name == dragged_class_name:
                print(f"DEBUG SAME CLASS FIX: TRIGGERED - dragged={dragged_class_name} session {dragged_session_index} trying to drop on slot with {class_name} session {session_idx}")
                print(f"DEBUG SAME CLASS FIX: Target slot: {target_day} P{target_period}, contains: {class_name} session {session_idx}")
                conflicts.append(f"Same class conflict: Cannot drop {dragged_class_name} session {dragged_session_index} onto slot with session {session_idx}")
                continue
            
            sessions_found_in_slot += 1
            print(f"DEBUG DIRECT CONFLICT: Found session in target slot: {class_name} at {session_day} P{session_period}")
                
            # Find the class info for this conflicting class
            conflicting_class_info = None
            for cls in classes_data:
                if clean_text_data(cls['Class']) == class_name:
                    conflicting_class_info = cls
                    break
            
            if conflicting_class_info:
                print(f"DEBUG DIRECT CONFLICT: Comparing teachers: {dragged_class_info['Teacher']} vs {conflicting_class_info['Teacher']}")
                
                # Check for teacher conflicts
                if dragged_class_info['Teacher'] == conflicting_class_info['Teacher']:
                    conflicts.append(f"Teacher conflict with {class_name}")
                    print(f"DEBUG DIRECT CONFLICT: TEACHER CONFLICT DETECTED - {dragged_class_info['Teacher']}")
                
                # Check for student conflicts
                dragged_students = set([s.strip() for s in dragged_class_info['Students'].split(';') if s.strip()])
                conflicting_students = set([s.strip() for s in conflicting_class_info['Students'].split(';') if s.strip()])
                shared_students = dragged_students.intersection(conflicting_students)
                
                if shared_students:
                    student_names = ', '.join(list(shared_students)[:6])
                    conflicts.append(f"Student conflict with {class_name} ({student_names})")
                    print(f"DEBUG DIRECT CONFLICT: STUDENT CONFLICT DETECTED - {len(shared_students)} shared students")
    
    print(f"DEBUG DIRECT CONFLICT: Found {sessions_found_in_slot} sessions in slot, {len(conflicts)} conflicts detected")
    return conflicts

def get_class_frequency(units):
    """Helper function to determine class frequency"""
    try:
        units = int(float(units))
        if units == 4:
            return 1
        elif units == 8:
            return 2
        elif units == 12:
            return 3
        else:
            return 1
    except:
        return 1

if __name__ == '__main__':
    # Get port from environment (Render sets this)
    port = int(os.environ.get('PORT', 5000))
    
    # Always bind to 0.0.0.0 for Render, but check if we're in production
    if 'RENDER' in os.environ or os.environ.get('PORT'):
        # Production deployment (Render)
        print(f"Starting production server on 0.0.0.0:{port}")
        app.run(debug=False, host='0.0.0.0', port=port)
    else:
        # Local development
        print(f"Starting development server on 127.0.0.1:{port}")
        app.run(debug=True, host='127.0.0.1', port=port)
