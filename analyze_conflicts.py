#!/usr/bin/env python3

import json
import csv
from collections import defaultdict

def parse_students(student_string):
    """Parse semicolon-separated student names into a set"""
    if not student_string:
        return set()
    return set(name.strip() for name in student_string.split(';') if name.strip())

def load_class_data():
    """Load class enrollment data from CSV"""
    class_data = {}
    try:
        with open('ClassCustomReport.csv', 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                class_name = row['Class'].strip()
                students = parse_students(row['Students'])
                class_data[class_name] = students
    except Exception as e:
        print(f"Error loading CSV: {e}")
        return {}
    
    return class_data

def load_schedule():
    """Load current schedule from JSON"""
    try:
        with open('last_schedule.json', 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading schedule: {e}")
        return None

def analyze_conflicts():
    """Analyze student conflicts in the current schedule"""
    class_data = load_class_data()
    schedule = load_schedule()
    
    if not class_data or not schedule:
        return
    
    print("=== STUDENT CONFLICT ANALYSIS ===\n")
    print(f"Loaded {len(class_data)} classes with enrollment data")
    print(f"Current schedule has {len(schedule['selected_classes'])} selected classes\n")
    
    # Group classes by time slot
    time_slots = defaultdict(list)
    
    for class_name, sessions in schedule['session_assignments'].items():
        if class_name not in schedule['selected_classes']:
            continue
            
        for session in sessions:
            day = session.get('day')
            period = session.get('period')
            
            if day and period and day != 'Open' and period != 'Open':
                slot_key = f"{day} P{period}"
                time_slots[slot_key].append(class_name)
    
    # Check for student conflicts in each time slot
    conflicts_found = []
    
    for time_slot, classes_in_slot in time_slots.items():
        if len(classes_in_slot) <= 1:
            continue
            
        # Get all students in this time slot
        students_by_class = {}
        for class_name in classes_in_slot:
            if class_name in class_data:
                students_by_class[class_name] = class_data[class_name]
            else:
                print(f"Warning: No enrollment data for {class_name}")
        
        # Find conflicting students
        all_students = set()
        student_to_classes = defaultdict(list)
        
        for class_name, students in students_by_class.items():
            for student in students:
                if student in all_students:
                    student_to_classes[student].append(class_name)
                else:
                    all_students.add(student)
                    student_to_classes[student] = [class_name]
        
        # Report conflicts
        slot_conflicts = []
        for student, student_classes in student_to_classes.items():
            if len(student_classes) > 1:
                slot_conflicts.append((student, student_classes))
        
        if slot_conflicts:
            conflicts_found.append((time_slot, classes_in_slot, slot_conflicts))
    
    # Report results
    if conflicts_found:
        print("🔴 STUDENT CONFLICTS DETECTED:\n")
        for time_slot, classes, conflicts in conflicts_found:
            print(f"TIME SLOT: {time_slot}")
            print(f"Classes scheduled: {', '.join(classes)}")
            print("Student conflicts:")
            for student, student_classes in conflicts:
                print(f"  • {student} is enrolled in: {', '.join(student_classes)}")
            print()
    else:
        print("✅ NO STUDENT CONFLICTS DETECTED")
        print("All students can attend their scheduled classes without time conflicts.\n")
    
    # Summary statistics
    total_students = set()
    for class_name in schedule['selected_classes']:
        if class_name in class_data:
            total_students.update(class_data[class_name])
    
    total_conflicts = sum(len(conflicts) for _, _, conflicts in conflicts_found)
    
    print("=== SUMMARY ===")
    print(f"Total unique students across all classes: {len(total_students)}")
    print(f"Time slots with multiple classes: {len([slot for slot, classes in time_slots.items() if len(classes) > 1])}")
    print(f"Time slots with conflicts: {len(conflicts_found)}")
    print(f"Students with scheduling conflicts: {total_conflicts}")

if __name__ == "__main__":
    analyze_conflicts()