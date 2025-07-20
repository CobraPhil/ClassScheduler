from flask import Flask, render_template, request, jsonify, session, send_file, make_response
import csv
from io import StringIO, BytesIO
from datetime import datetime
import uuid
import os

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
manual_room_assignments = {}  # Track manual room assignments
manual_period_assignments = {}  # Track manual period assignments

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
    def __init__(self, classes, manual_rooms=None, manual_periods=None):
        self.classes = classes
        self.schedule = {}
        self.conflicts = []
        self.room_assignments = {}
        self.manual_room_assignments = manual_rooms or {}
        self.manual_period_assignments = manual_periods or {}
        
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
            [7],           # Period 7 (last resort)
            [8]            # Period 8 (special teachers only)
        ]
    
    def evaluate_solution_quality(self, schedule):
        """Evaluate the quality of a scheduling solution"""
        score = 0
        period_usage = {p: 0 for p in range(1, 9)}
        
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
        score += period_usage[8] * 8   # Period 8 is okay for special teachers
        
        return score, period_usage
    
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
        assigned_rooms = {}  # Track room assignments: "day_period_room" -> class_name
        
        # Available periods (excluding period 3 for chapel)
        available_periods = [1, 2, 4, 5, 6]
        if use_period_7:
            available_periods.append(7)
        
        # Removed hardcoded teacher period requirements - now handled via manual dropdowns
        
        # Initialize schedule grid
        for day in DAYS:
            self.schedule[day] = {}
            for period in range(1, 9):
                self.schedule[day][period] = []
        
        # Sort classes by enhanced priority hierarchy
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
        
        sorted_classes = sorted(self.classes, key=class_priority, reverse=True)
        unscheduled_classes = []
        
        # Enhanced scheduling with sophisticated search and optimization
        for class_info in sorted_classes:
            frequency = self.get_class_frequency(class_info['Units'])
            day_options = self.get_preferred_days(frequency)
            scheduled = False
            conflicts_found = []
            best_option = None
            
            # Check for manual period assignment first
            class_name = class_info['Class']
            has_manual_period = class_name in self.manual_period_assignments
            
            # Teacher period requirements removed - now handled via manual dropdowns
            needs_period_8 = False
            needs_period_1 = False
            
            # Determine period priorities for this class
            if has_manual_period:
                period_groups = [[self.manual_period_assignments[class_name]]]
            # Removed hardcoded teacher period assignments
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
                            
                        can_schedule, period_conflicts = self.can_schedule_class(class_info, day_option, period, assigned_rooms)
                        
                        if can_schedule:
                            # Found a valid slot - record it
                            potential_option = {
                                'day_option': day_option,
                                'period': period,
                                'priority_score': self.get_option_priority_score(period, day_option, frequency)
                            }
                            
                            # If this is core period or manual assignment, schedule immediately
                            if period in [2, 4, 5, 6] or has_manual_period:
                                self.schedule_class(class_info, day_option, period, assigned_rooms)
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
                self.schedule_class(class_info, best_option['day_option'], best_option['period'], assigned_rooms)
                scheduled = True
                print(f"Scheduled {class_info['Class']} on {best_option['day_option']} at Period {best_option['period']} (fallback)")
            
            if not scheduled:
                unscheduled_classes.append({
                    'class': class_info,
                    'conflicts': conflicts_found
                })
                print(f"Could not schedule {class_info['Class']} - conflicts: {conflicts_found[:3]}...")  # Show first 3 conflicts
        
        # Always return the current state - whether complete or partial
        total_classes = len(self.classes)
        scheduled_classes = total_classes - len(unscheduled_classes)
        print(f"Scheduling complete: {scheduled_classes}/{total_classes} classes scheduled")
        
        return len(unscheduled_classes) == 0, unscheduled_classes
    
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
    global current_schedule, selected_classes, manual_room_assignments, manual_period_assignments
    
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
        
        print(f"Manual room assignments: {manual_room_assignments}")
        print(f"Manual period assignments: {manual_period_assignments}")
        
        # Pass manual room and period assignments to scheduler
        scheduler = ClassScheduler(classes_to_schedule, manual_room_assignments, manual_period_assignments)
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
            
            # Save the enhanced schedule with room assignments for PDF export
            current_schedule = enhanced_schedule
            
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
            # Even for partial schedules, save the enhanced schedule for PDF export
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
            
            current_schedule = enhanced_schedule
            
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
    global selected_classes, manual_room_assignments, manual_period_assignments, current_schedule
    
    try:
        data = request.get_json()
        selected_classes = data.get('selected_classes', [])
        manual_room_assignments = data.get('room_assignments', {})
        manual_period_assignments = data.get('period_assignments', {})
        
        # Clear the current schedule when selections change
        # This ensures users see a blank generate page after making changes
        current_schedule = None
        
        print(f"Selected classes: {selected_classes}")
        print(f"Manual room assignments: {manual_room_assignments}")
        print(f"Manual period assignments: {manual_period_assignments}")
        print("Current schedule cleared due to selection changes")
        
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
        
        # Generate HTML for PDF
        html_content = render_template('schedule_pdf.html', 
                                     schedule=current_schedule, 
                                     periods=PERIODS, 
                                     days=DAYS,
                                     rooms=ROOMS,
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
            background-color: #e8f0fe;
            border: 1px solid #667eea;
            border-radius: 3px;
            padding: 3px;
            margin-bottom: 2px;
            font-size: 8px;
        }}
        
        .class-block:last-child {{
            margin-bottom: 0;
        }}
        
        .class-title {{
            font-weight: bold;
            color: #333;
            margin-bottom: 1px;
            line-height: 1.1;
        }}
        
        .class-teacher {{
            color: #666;
            font-size: 7px;
            line-height: 1.1;
        }}
        
        .class-room {{
            color: #999;
            font-size: 7px;
            font-style: italic;
        }}
        
        .class-students {{
            color: #333;
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
        for period_num in [1, 2, 3, 4, 5, 6, 7, 8]:
            complete_html += f"""
            <tr>
                <td class="period-label {'chapel-period' if period_num == 3 else ''}">
                    Period {period_num}<br>
                    <small>"""
            
            # Add period times
            if period_num == 1: complete_html += "7:00am-7:50am"
            elif period_num == 2: complete_html += "8:00am-8:50am"
            elif period_num == 3: complete_html += "9:00am-9:30am<br>(Chapel)"
            elif period_num == 4: complete_html += "9:40am-10:30am"
            elif period_num == 5: complete_html += "10:40am-11:30am"
            elif period_num == 6: complete_html += "11:40am-12:30pm"
            elif period_num == 7: complete_html += "12:40pm-1:30pm"
            elif period_num == 8: complete_html += "6:00pm-6:50pm"
            
            complete_html += """</small>
                </td>"""
            
            # Add cells for each day
            for day in days:
                complete_html += "<td>"
                if current_schedule.get(day) and current_schedule[day].get(period_num):
                    for class_info in current_schedule[day][period_num]:
                        complete_html += f"""
                        <div class="class-block">
                            <div class="class-title">{class_info.get('Class', '')}</div>
                            <div class="class-teacher">{class_info.get('Teacher', '')}</div>
                            <div class="class-room">{class_info.get('room', 'TBD')}</div>
                            <div class="class-students">{class_info.get('student_count', 0)} students</div>
                        </div>"""
                complete_html += "</td>"
            
            complete_html += "</tr>"
        
        complete_html += """
        </tbody>
    </table>
    
    <div class="footer">
        <p>Class Schedule Generator - Conflict-free scheduling with room assignments</p>
    </div>
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