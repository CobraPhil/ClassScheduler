from flask import Flask, render_template, request, jsonify, session, send_file
import csv
from io import StringIO, BytesIO
import weasyprint
from datetime import datetime
import uuid
import os

app = Flask(__name__)
app.secret_key = 'class_scheduler_secret_key'

# Global variables for session-based storage
classes_data = []
selected_classes = []
current_schedule = None

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
    def __init__(self, classes):
        self.classes = classes
        self.schedule = {}
        self.conflicts = []
        self.room_assignments = {}
        
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
        """Get preferred days based on frequency"""
        if frequency == 1:
            return [['Monday'], ['Tuesday'], ['Wednesday'], ['Thursday'], ['Friday']]
        elif frequency == 2:
            return [['Tuesday', 'Thursday'], ['Monday', 'Wednesday'], ['Monday', 'Friday'], ['Wednesday', 'Friday']]
        elif frequency == 3:
            return [['Monday', 'Wednesday', 'Friday'], ['Monday', 'Tuesday', 'Thursday'], ['Tuesday', 'Wednesday', 'Friday']]
        return [['Monday']]
    
    def assign_room(self, class_info):
        """Assign appropriate room based on class requirements"""
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
            else:  # regular classroom
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
            else:  # regular classroom
                available_room = self.get_available_regular_classroom(day, period, assigned_rooms)
                if available_room:
                    room_key = f"{day}_{period}_{available_room}"
                    assigned_rooms[room_key] = class_info['Class']
                    room_display = available_room.replace('_', ' ').title()
                    self.room_assignments[f"{day}_{period}_{class_info['Class']}"] = room_display
    
    def generate_schedule(self, use_period_7=False):
        """Generate class schedule with conflict resolution"""
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
        
        # Initialize schedule grid
        for day in DAYS:
            self.schedule[day] = {}
            for period in range(1, 9):
                self.schedule[day][period] = []
        
        # Sort classes by constraints (most constrained first)
        def class_priority(class_info):
            priority = 0
            
            # Special teachers get highest priority
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
            
            # More students = higher priority
            priority += student_count
            
            return priority
        
        sorted_classes = sorted(self.classes, key=class_priority, reverse=True)
        unscheduled_classes = []
        
        for class_info in sorted_classes:
            frequency = self.get_class_frequency(class_info['Units'])
            preferred_days_options = self.get_preferred_days(frequency)
            scheduled = False
            
            # Check if teacher needs special period 8
            needs_period_8 = any(teacher in class_info['Teacher'] for teacher in special_teachers)
            
            for day_option in preferred_days_options:
                if scheduled:
                    break
                    
                # Find available periods for this day combination
                periods_to_use = [8] if needs_period_8 else available_periods
                
                for period in periods_to_use:
                    if scheduled:
                        break
                    
                    can_schedule, conflicts_found = self.can_schedule_class(class_info, day_option, period, assigned_rooms)
                    
                    if can_schedule:
                        self.schedule_class(class_info, day_option, period, assigned_rooms)
                        scheduled = True
                        break
            
            if not scheduled:
                unscheduled_classes.append({
                    'class': class_info,
                    'conflicts': conflicts_found if 'conflicts_found' in locals() else ['Could not find suitable time slot']
                })
        
        return len(unscheduled_classes) == 0, unscheduled_classes

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_csv():
    global classes_data
    
    try:
        if 'csv_file' not in request.files:
            return jsonify({'success': False, 'error': 'No file uploaded'})
        
        file = request.files['csv_file']
        if file.filename == '':
            return jsonify({'success': False, 'error': 'No file selected'})
        
        # Read CSV file
        csv_content = file.read().decode('utf-8')
        reader = csv.DictReader(StringIO(csv_content))
        
        # Convert to list of dictionaries
        classes_data = list(reader)
        
        # Count students for each class
        for class_info in classes_data:
            if 'Students' in class_info and class_info['Students']:
                student_list = [s.strip() for s in str(class_info['Students']).split(';') if s.strip()]
                class_info['student_count'] = len(student_list)
            else:
                class_info['student_count'] = 0
        
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
        return jsonify({'success': False, 'error': str(e)})

@app.route('/generate_schedule', methods=['POST'])
def generate_schedule():
    global current_schedule, selected_classes
    
    try:
        data = request.get_json() or {}
        use_period_7 = data.get('use_period_7', False)
        
        if not selected_classes:
            return jsonify({'success': False, 'error': 'No classes selected'})
        
        # Filter classes to only selected ones
        classes_to_schedule = [cls for cls in classes_data if cls['Class'] in selected_classes]
        
        scheduler = ClassScheduler(classes_to_schedule)
        success, unscheduled = scheduler.generate_schedule(use_period_7)
        
        current_schedule = scheduler.schedule
        
        if success:
            return jsonify({
                'success': True,
                'schedule': scheduler.schedule,
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
    global selected_classes
    
    try:
        data = request.get_json()
        selected_classes = data.get('selected_classes', [])
        
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