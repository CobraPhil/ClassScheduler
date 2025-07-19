from flask import Flask, render_template, request, jsonify, session, send_file
import csv
from io import StringIO, BytesIO
import weasyprint
from datetime import datetime
import uuid
import os

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
manual_room_assignments = {}  # Track manual room assignments

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
    8: 'Period 8'
}

DAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']

class ClassScheduler:
    def __init__(self, classes, manual_rooms=None):
        self.classes = classes
        self.schedule = {}
        self.conflicts = []
        self.room_assignments = {}
        self.manual_room_assignments = manual_rooms or {}
        
    def parse_students(self, student_string):
        """Parse semicolon-separated student list"""
        if not student_string or student_string == '':
            return []
        return [s.strip() for s in str(student_string).split(';') if s.strip()]
    
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
    
    def can_schedule_class(self, class_info, day_option, period, assigned_rooms):
        """Check if a class can be scheduled at the given day/period"""
        assigned_room_type = self.assign_room(class_info)
        conflicts_found = []
        
        for day in day_option:
            existing_classes = self.schedule[day][period]
            
            # Check conflicts with existing classes
            for existing_class in existing_classes:
                class_conflicts = self.check_conflicts(class_info, existing_class)
                if class_conflicts:
                    for conflict in class_conflicts:
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
    
    def schedule_class(self, class_info, day_option, period, assigned_rooms):
        """Schedule a class at the given day/period"""
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
        """Generate class schedule with multi-pass conflict resolution"""
        # First pass: Try without Period 7, exhausting all day combinations
        success, unscheduled = self.try_schedule_without_period_7()
        
        if success:
            return True, []
        
        # If first pass failed and user allows Period 7, try with Period 7
        if use_period_7:
            print(f"First pass failed with {len(unscheduled)} unscheduled classes. Trying with Period 7...")
            success, unscheduled = self.try_schedule_with_period_7()
            return success, unscheduled
        else:
            return False, unscheduled
    
    def generate_schedule_internal(self, use_period_7=False):
        """Internal method that actually generates the schedule"""
        self.schedule = {}
        self.conflicts = []
        self.room_assignments = {}
        assigned_rooms = {}  # Track room assignments: "day_period_room" -> class_name
        
        # Available periods (excluding period 3 for chapel)
        available_periods = [1, 2, 4, 5, 6]
        if use_period_7:
            available_periods.append(7)
        
        # Special period 8 for specific teachers
        special_teachers = ['Kawage, Kia', 'Tama, Philip']
        
        # Period 1 for specific teachers
        period_1_teachers = ['Smith, Lori']
        
        # Initialize schedule grid
        for day in DAYS:
            self.schedule[day] = {}
            for period in range(1, 9):
                self.schedule[day][period] = []
        
        # Sort classes by constraints (most constrained first)
        def class_priority(class_info):
            priority = 0
            
            # Period 1 teachers get highest priority (most constrained)
            if any(teacher in class_info['Teacher'] for teacher in period_1_teachers):
                priority += 2000
            
            # Special teachers get second highest priority
            if any(teacher in class_info['Teacher'] for teacher in special_teachers):
                priority += 1000
            
            # Computer/ESL classes get high priority (room constraint)
            course_name = class_info['Course Name'].upper()
            if 'GECO' in course_name or 'GELA' in course_name:
                priority += 500
            
            # Large classes get high priority (room constraint)
            student_count = len(self.parse_students(class_info['Students']))
            if student_count > 40:
                priority += 400
            
            # Classes with more frequency get higher priority (harder to schedule)
            frequency = self.get_class_frequency(class_info['Units'])
            priority += frequency * 50
            
            # More students = higher priority
            priority += student_count
            
            return priority
        
        sorted_classes = sorted(self.classes, key=class_priority, reverse=True)
        unscheduled_classes = []
        
        for class_info in sorted_classes:
            frequency = self.get_class_frequency(class_info['Units'])
            day_options = self.get_preferred_days(frequency)
            scheduled = False
            conflicts_found = []
            
            # Check if teacher needs special period assignments
            needs_period_8 = any(teacher in class_info['Teacher'] for teacher in special_teachers)
            needs_period_1 = any(teacher in class_info['Teacher'] for teacher in period_1_teachers)
            
            # Try each day combination in priority order
            for day_option in day_options:
                if scheduled:
                    break
                    
                # Determine available periods for this class
                if needs_period_8:
                    periods_to_try = [8]
                elif needs_period_1:
                    periods_to_try = [1]
                else:
                    periods_to_try = available_periods
                
                # Try each period for this day combination
                for period in periods_to_try:
                    if scheduled:
                        break
                    
                    can_schedule, period_conflicts = self.can_schedule_class(class_info, day_option, period, assigned_rooms)
                    
                    if can_schedule:
                        self.schedule_class(class_info, day_option, period, assigned_rooms)
                        scheduled = True
                        print(f"Scheduled {class_info['Class']} on {day_option} at Period {period}")
                        break
                    else:
                        conflicts_found.extend(period_conflicts)
            
            if not scheduled:
                unscheduled_classes.append({
                    'class': class_info,
                    'conflicts': conflicts_found
                })
                print(f"Could not schedule {class_info['Class']} - conflicts: {conflicts_found[:3]}...")  # Show first 3 conflicts
        
        return len(unscheduled_classes) == 0, unscheduled_classes

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
        
        # Convert to list of dictionaries
        classes_data = list(reader)
        print(f"Classes parsed: {len(classes_data)}")  # Debug
        
        # Count students for each class
        for class_info in classes_data:
            if 'Students' in class_info and class_info['Students']:
                student_list = [s.strip() for s in str(class_info['Students']).split(';') if s.strip()]
                class_info['student_count'] = len(student_list)
            else:
                class_info['student_count'] = 0
        
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
    global current_schedule, selected_classes, manual_room_assignments
    
    try:
        data = request.get_json() or {}
        use_period_7 = data.get('use_period_7', False)
        
        if not selected_classes:
            return jsonify({'success': False, 'error': 'No classes selected'})
        
        # Filter classes to only selected ones
        classes_to_schedule = [cls for cls in classes_data if cls['Class'] in selected_classes]
        
        # Pass manual room assignments to scheduler
        scheduler = ClassScheduler(classes_to_schedule, manual_room_assignments)
        success, unscheduled = scheduler.generate_schedule(use_period_7)
        
        current_schedule = scheduler.schedule
        
        if success:
            # Add room information to each scheduled class
            enhanced_schedule = {}
            for day in scheduler.schedule:
                enhanced_schedule[day] = {}
                for period in scheduler.schedule[day]:
                    enhanced_schedule[day][period] = []
                    for class_info in scheduler.schedule[day][period]:
                        # Get room assignment
                        room_key = f"{day}_{period}_{class_info['Class']}"
                        room_name = scheduler.room_assignments.get(room_key, 'TBD')
                        
                        # Add room info to class
                        enhanced_class = class_info.copy()
                        enhanced_class['room'] = room_name
                        enhanced_schedule[day][period].append(enhanced_class)
            
            return jsonify({
                'success': True,
                'schedule': enhanced_schedule,
                'stats': {
                    'total_classes': len(classes_to_schedule),
                    'scheduled_classes': len(classes_to_schedule) - len(unscheduled),
                    'unscheduled_classes': len(unscheduled)
                }
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Could not schedule all classes without conflicts',
                'unscheduled': unscheduled,
                'can_try_period_7': not use_period_7
            })
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/set_selection', methods=['POST'])
def set_selection():
    global selected_classes, manual_room_assignments
    
    try:
        data = request.get_json()
        selected_classes = data.get('selected_classes', [])
        manual_room_assignments = data.get('room_assignments', {})
        
        print(f"Selected classes: {selected_classes}")
        print(f"Manual room assignments: {manual_room_assignments}")
        
        return jsonify({
            'success': True,
            'selected_count': len(selected_classes)
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/export_pdf')
def export_pdf():
    global current_schedule
    
    if not current_schedule:
        return jsonify({'success': False, 'error': 'No schedule to export'})
    
    try:
        # Generate HTML for PDF
        html_content = render_template('schedule_pdf.html', 
                                     schedule=current_schedule, 
                                     periods=PERIODS, 
                                     days=DAYS,
                                     rooms=ROOMS,
                                     datetime=datetime)
        
        # Generate PDF
        pdf_buffer = BytesIO()
        weasyprint.HTML(string=html_content).write_pdf(pdf_buffer)
        pdf_buffer.seek(0)
        
        return send_file(
            pdf_buffer,
            as_attachment=True,
            download_name=f'class_schedule_{datetime.now().strftime("%Y%m%d_%H%M")}.pdf',
            mimetype='application/pdf'
        )
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

if __name__ == '__main__':
    app.run(debug=True, host='127.0.0.1', port=5000)