# ClassScheduler Project

## Project Description
A comprehensive web-based class scheduling system for theological seminary that generates conflict-free weekly schedules with automatic room assignments and PDF export capabilities.

## Technology Stack
- **Backend**: Python Flask web framework
- **Frontend**: Modern HTML5/CSS3/JavaScript with responsive design
- **PDF Generation**: WeasyPrint for high-quality PDF exports
- **Data Processing**: Pure Python CSV parsing with automatic data cleaning
- **Version Control**: Git with experiment/master branch workflow

## Key Files
- `app.py` - Main Flask application with scheduling algorithm
- `templates/index.html` - Modern web interface with tabbed navigation
- `templates/schedule_pdf.html` - PDF export template with dynamic formatting
- `ClassList.csv` - Contains class enrollment data with students, teachers, and course details
- `CLAUDE.md` - This documentation file

## Common Commands
- **Start Application**: `python app.py` (runs on http://localhost:5000)
- **Build**: No build step required - direct Python execution
- **Test**: Use test files like `test_csv_cleaning.py` for validation
- **Lint**: Standard Python linting tools (pylint, flake8)

## Application Features

### Web Interface
- **Modern Design**: Responsive tabbed interface with gradient styling and smooth transitions
- **Three-Step Workflow**: Upload CSV → Select Classes → Generate Schedule
- **Drag & Drop Upload**: Support for CSV file upload with visual feedback
- **Real-time Validation**: Immediate feedback on file processing and scheduling results
- **Manual Overrides**: Dropdown controls for room and period assignments per class
- **Statistics Dashboard**: Live counts and scheduling metrics

### Data Processing
- **Automatic CSV Cleaning**: Removes extra spaces, normalizes formatting, cleans student lists
- **Conflict Detection**: Advanced algorithm detects student and teacher conflicts
- **Smart Defaults**: Auto-assigns Computer Lab for GECO/GELA classes, Chapel for large classes
- **Session Management**: Maintains state across workflow steps without persistence

### PDF Export
- **Professional Layout**: A4 landscape format with clean typography
- **Dynamic Formatting**: Period 3 compression and smart page breaks
- **Complete Information**: Shows class names, teachers, rooms, and student counts
- **Time Display**: All period times clearly labeled for reference

## Classroom Configuration
Available classrooms and their constraints:
- **Classroom 2** - General purpose classroom
- **Classroom 4** - General purpose classroom  
- **Classroom 5** - General purpose classroom
- **Classroom 6** - General purpose classroom
- **Computer Lab** - Reserved for computer classes (GECO) and ESL classes (GELA)
- **Chapel** - Required for classes with over 40 students
## Scheduling Constraints

### Core Conflict Rules
- **No Teacher Conflicts**: A teacher can only teach one class at a time
- **No Student Conflicts**: A student can only be in one class at a time  
- **Room Capacity**: Classes over 40 students must use Chapel
- **Room Restrictions**: Computer/ESL classes must use Computer Lab

### Credit-Based Frequency
- **4 Credits**: Meets once per week (typically Friday)
- **8 Credits**: Meets twice per week (preferably Tuesday/Thursday)
- **12 Credits**: Meets three times per week (preferably Monday/Wednesday/Friday)

### Period Schedule
Available time periods Monday through Friday:
- **Period 1**: 7:00am-7:50am (early morning - use sparingly)
- **Period 2**: 8:00am-8:50am (core period - preferred)
- **Period 3**: 9:00am-9:30am (Chapel - NEVER schedule classes)
- **Period 4**: 9:40am-10:30am (core period - preferred)
- **Period 5**: 10:40am-11:30am (core period - preferred)
- **Period 6**: 11:40am-12:30pm (core period - preferred)
- **Period 7**: 12:40pm-1:30pm (lunch period - last resort)
- **Period 8**: 5:30pm-6:20pm (evening - manual assignment only)
- **Period 9**: 6:30pm-7:20pm (evening - manual assignment only)
- **Period 10**: 7:30pm-8:20pm (evening - manual assignment only)
## Enhanced Scheduling Algorithm

### Priority Hierarchy (Most to Least Constrained)
1. **Manual Period Assignments** - Highest priority, user-specified periods via dropdown
2. **Room Constraints** - Computer Lab and Chapel requirements  
3. **Class Size** - Largest classes scheduled first to secure optimal periods
4. **Preferred Periods** - Core periods (2,4,5,6) before early/late periods (1,7,8)
5. **Day Combinations** - Optimal day patterns based on credit hours

### Period Usage Strategy
1. **Fill Core Periods First** - Periods 2,4,5,6 are the primary teaching periods
2. **Minimize Period 1** - Early morning only when necessary or manually assigned
3. **Avoid Period 7** - Lunch period used as absolute last resort
4. **Periods 8-10 Manual Only** - Evening periods only for manual assignments
5. **Complete Core Before Fallback** - Fill all core periods before using Period 1 or 7

### Day Combination Logic
1. **Preferred Days First**: 
   - 8-credit classes: Tuesday/Thursday
   - 12-credit classes: Monday/Wednesday/Friday
2. **Alternative Combinations** when preferred days conflict:
   - 8-credit: Try Monday/Wednesday, Monday/Friday, Wednesday/Friday
   - 12-credit: Try Monday/Tuesday/Thursday, Tuesday/Wednesday/Friday
3. **Alternative Days Before Bad Periods** - Use non-preferred days before Period 1 or 7

### Multi-Pass Optimization
1. **Never Accept First Solution** - Algorithm tries multiple approaches
2. **Sophisticated Search** - Multiple constraint satisfaction passes
3. **Solution Comparison** - Selects best solution based on scoring:
   - Minimizes Period 7 usage (heavily penalized)
   - Minimizes Period 1 usage  
   - Maximizes core period usage (2,4,5,6)
   - Prefers optimal day combinations
4. **Fallback Strategies** - Graceful degradation when perfect solution impossible
5. **Always Provide Best Solution** - Even if not perfect, system provides optimal available schedule

## Data Quality Features
- **Automatic CSV Cleaning** - Removes extra spaces, normalizes formatting during import
- **Student List Normalization** - Cleans semicolon-separated student names
- **Conflict Detection** - Precise matching prevents false conflicts from formatting issues
- **Real-time Validation** - Immediate feedback on data quality and scheduling conflicts

## Current Status
- **All Core Features Complete** - Upload, selection, scheduling, PDF export fully functional
- **Bug Fixes Applied** - PDF room assignment bug resolved
- **Data Cleaning Implemented** - Automatic CSV cleaning during import
- **Algorithm Enhanced** - Multi-pass optimization with intelligent prioritization
- **UI Improvements** - Schedule status tracking and automatic display clearing