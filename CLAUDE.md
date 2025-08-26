# ClassScheduler Project

## Project Description
A comprehensive web-based class scheduling system for theological seminary that generates conflict-free weekly schedules with advanced multi-session management, smart session consistency, automatic room assignments, and PDF export capabilities.

## Technology Stack
- **Backend**: Python Flask web framework
- **Frontend**: Modern HTML5/CSS3/JavaScript with responsive design
- **PDF Generation**: WeasyPrint for high-quality PDF exports  
- **Data Processing**: Pure Python CSV parsing with automatic data cleaning
- **Version Control**: Git with experiment/master branch workflow

## Key Files
- `app.py` - Main Flask application with advanced scheduling algorithm (1664+ lines)
- `templates/index.html` - Modern web interface with multi-session dropdown controls
- `templates/schedule_pdf.html` - PDF export template with 10-period support
- `ClassList.csv` - Contains class enrollment data with students, teachers, and course details
- `CLAUDE.md` - This comprehensive documentation file

## Common Commands
- **Start Application**: `python app.py` (runs on http://localhost:5000)
- **Build**: No build step required - direct Python execution
- **Test**: Use test files like `test_csv_cleaning.py` for validation
- **Lint**: Standard Python linting tools (pylint, flake8)

## Application Features

### Advanced Web Interface
- **Modern Design**: Responsive tabbed interface with gradient styling and smooth transitions
- **Three-Step Workflow**: Upload CSV → Select Classes → Generate Schedule
- **Drag & Drop Upload**: Support for CSV file upload with visual feedback
- **Real-time Validation**: Immediate feedback on file processing and scheduling results
- **Multi-Session Dropdowns**: Individual Day/Period/Room controls for each class session with time display
- **Smart Session Management**: Credit-based session generation (4/8/12 credit = 1/2/3 sessions)
- **Statistics Dashboard**: Live counts and scheduling metrics
- **Hybrid Manual/Auto Scheduling**: Mix manual assignments with automatic optimization
- **Dynamic Class Colors**: Each class assigned unique, distinctive colors for easy visual identification

### Multi-Session Class Management
- **Session-Based Architecture**: Each class broken into individual sessions based on credit hours
- **Individual Session Controls**: Separate Day/Period/Room dropdowns for each session (Class 1, Class 2, Class 3)
- **Time-Enhanced Period Dropdowns**: Period selections display actual meeting times (e.g., "Period 2 (8:00am-8:50am)")
- **Credit-Based Session Count**: 
  - 4 credits or less = 1 session per week
  - 8 credits or less = 2 sessions per week  
  - 12+ credits = 3 sessions per week
- **Smart Default Assignment**: Computer Lab auto-assigned for GECO/GELA classes
- **Open vs Manual Values**: "Open" allows auto-scheduling, specific values force manual assignment

### Smart Session Consistency Engine
- **Pattern Analysis**: `analyze_manual_session_pattern()` method detects patterns from manual assignments
- **Day Pattern Inference**: Automatically completes academic patterns
  - 8-credit classes: Infers T/Th or M/W patterns from single manual assignment
  - 12-credit classes: Infers M/W/F patterns from single manual assignment
- **Period Consistency**: Uses same period for remaining sessions when one is manually assigned
- **Room Consistency**: Uses same room for remaining sessions when one is manually assigned
- **Intelligent Fallback**: Uses standard academic patterns when manual patterns unclear

### Enhanced Data Processing
- **Automatic CSV Cleaning**: Removes extra spaces, normalizes formatting, cleans student lists
- **Advanced Conflict Detection**: Detects student and teacher conflicts with precise matching
- **Session-Specific Room Preferences**: Tracks room preferences even for auto-scheduled sessions
- **Comprehensive Error Handling**: Detailed logging and graceful error recovery
- **Real-time Session Updates**: Live updates to session assignments via AJAX

### Professional PDF Export
- **Extended Period Support**: A4 landscape format supporting all 10 periods
- **Complete Information**: Shows class names, teachers, rooms, and student counts
- **Dynamic Period Times**: All period times clearly labeled including evening periods
- **Smart Page Layout**: Period 3 compression and intelligent page breaks
- **Session Integration**: Shows all assigned sessions with proper room assignments
- **Color-Coded Classes**: Each class displays in its unique assigned color for easy identification

### Dynamic Class Color System
- **Smart Color Generation**: Uses HSL color space for optimal visual distribution across 25+ classes
- **Consistent Assignment**: Each class maintains the same color across all days, periods, and sessions
- **White Text Optimization**: All colors use darker tones (30-42% lightness) ensuring excellent contrast with white text
- **Gradual Progression**: Subtle hue variations prevent adjacent colors from being too similar
- **Full System Integration**: Colors appear in web interface, PDF exports, and HTML fallback documents
- **Automatic Scaling**: Algorithm adapts seamlessly from small (4 classes) to large (25+ classes) course loads

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
- **Session Isolation**: Each session of a multi-session class treated independently for conflicts

### Credit-Based Frequency
- **4 Credits**: Meets once per week (typically Friday)
- **8 Credits**: Meets twice per week (preferably Tuesday/Thursday)
- **12 Credits**: Meets three times per week (preferably Monday/Wednesday/Friday)

### Extended Period Schedule
Available time periods Monday through Friday:
- **Period 1**: 7:00am-7:50am (early morning - use sparingly)
- **Period 2**: 8:00am-8:50am (core period - preferred)
- **Period 3**: 9:00am-9:30am (Chapel - NEVER schedule classes, excluded from dropdowns)
- **Period 4**: 9:40am-10:30am (core period - preferred)
- **Period 5**: 10:40am-11:30am (core period - preferred)
- **Period 6**: 11:40am-12:30pm (core period - preferred)
- **Period 7**: 12:40pm-1:30pm (lunch period - last resort)
- **Period 8**: 5:30pm-6:20pm (evening - manual assignment only)
- **Period 9**: 6:30pm-7:20pm (evening - manual assignment only)
- **Period 10**: 7:30pm-8:20pm (evening - manual assignment only)

**Note**: All period dropdowns display the actual meeting times for easy reference (e.g., "Period 2 (8:00am-8:50am)"). Period 3 is intentionally excluded from dropdown menus since it's reserved for Chapel.

## Advanced Scheduling Algorithm

### Multi-Tier Priority Hierarchy (Most to Least Constrained)
1. **Fully Manual Session Assignments** - Highest priority, user-specified day AND period via dropdowns
2. **Manual Room Preferences** - Room assignments specified but day/period auto-scheduled
3. **Smart Session Consistency** - Inferred patterns from partial manual assignments
4. **Room Constraints** - Computer Lab and Chapel requirements  
5. **Class Size Priority** - Largest classes scheduled first to secure optimal periods
6. **Preferred Periods** - Core periods (2,4,5,6) before early/late periods (1,7)
7. **Day Pattern Optimization** - Academic patterns based on credit hours

### Smart Session Consistency Logic
1. **Pattern Detection**: Analyzes manual assignments to detect academic patterns
2. **Day Pattern Completion**: 
   - If Class 1 manual = Monday → Try to complete M/W/F for 12-credit or M/W for 8-credit
   - If Class 1 manual = Tuesday → Try to complete T/Th for 8-credit or T/W/Th for 12-credit
3. **Period Inheritance**: If Class 1 = Period 2, try Period 2 for remaining sessions
4. **Room Inheritance**: If Class 1 = Classroom 6, try Classroom 6 for remaining sessions
5. **Graceful Degradation**: Falls back to standard patterns if consistency impossible

### Enhanced Period Usage Strategy
1. **Fill Core Periods First** - Periods 2,4,5,6 are the primary teaching periods
2. **Respect Manual Preferences** - Manual period assignments get absolute priority
3. **Smart Period Consistency** - Use same period for multiple sessions when possible
4. **Minimize Period 1** - Early morning only when necessary or manually assigned
5. **Avoid Period 7** - Lunch period used as absolute last resort
6. **Periods 8-10 Manual Only** - Evening periods only for manual assignments
7. **Complete Core Before Fallback** - Fill all core periods before using Period 1 or 7

### Intelligent Day Pattern Logic
1. **Academic Standard Patterns**:
   - 8-credit classes: Tuesday/Thursday (preferred), Monday/Wednesday (alternative)
   - 12-credit classes: Monday/Wednesday/Friday (preferred), Tuesday/Wednesday/Friday (alternative)
2. **Manual Pattern Inference**:
   - Single manual day triggers completion of academic pattern
   - Example: Manual Monday → Auto Wednesday/Friday for 12-credit class
3. **Conflict-Aware Pattern Selection**: Chooses alternative patterns when preferred days conflict
4. **Alternative Days Before Bad Periods**: Use non-preferred days before Period 1 or 7

### Multi-Pass Optimization with Smart Consistency
1. **Never Accept First Solution** - Algorithm tries multiple approaches
2. **Sophisticated Search** - Multiple constraint satisfaction passes with session consistency
3. **Solution Comparison** - Selects best solution based on enhanced scoring:
   - Maximizes manual assignment compliance
   - Maintains session consistency (same period/room when possible)
   - Minimizes Period 7 usage (heavily penalized)
   - Minimizes Period 1 usage  
   - Maximizes core period usage (2,4,5,6)
   - Prefers optimal day combinations
4. **Partial Schedule Success** - Returns success if ANY classes scheduled (not all-or-nothing)
5. **Always Provide Best Solution** - Even if not perfect, system provides optimal available schedule

### Room Assignment Intelligence
1. **Manual Room Priority**: Specific room assignments always honored
2. **Room Preference Inheritance**: Manual room choices extended to other sessions
3. **Auto-Assignment Logic**: 
   - GECO/GELA classes → Computer Lab
   - Classes >40 students → Chapel  
   - Regular classes → Available classroom (2,4,5,6)
4. **Availability Checking**: Prevents double-booking of specific rooms
5. **TBD Elimination**: Enhanced logic prevents "TBD" assignments for valid classes

## Technical Implementation Details

### Backend Architecture (app.py)
- **ClassScheduler Class**: Core scheduling engine with 1664+ lines of advanced logic
- **Manual Session Processing**: Comprehensive handling of mixed manual/auto assignments
- **Smart Pattern Analysis**: `analyze_manual_session_pattern()` method for pattern detection
- **Room Preference Application**: `apply_room_preferences()` method for post-scheduling room assignment
- **Enhanced Conflict Detection**: Session-aware conflict checking with detailed logging
- **Partial Schedule Support**: Improved success criteria for better user experience
- **Color Generation System**: `generate_class_colors()` function using HSL color space for optimal distribution
- **Color Persistence**: Global `class_colors` dictionary maintains color assignments throughout session

### Frontend Architecture (templates/index.html)
- **Dynamic Session Generation**: JavaScript creates appropriate number of session dropdowns with time-enhanced period options
- **Real-time Session Updates**: `updateClassSession()` function handles live dropdown changes
- **Credit-Based UI Logic**: Automatic session count determination from credit hours
- **Compact Session Layout**: CSS grid system for clean multi-session display
- **Session State Management**: `classSessionAssignments` object tracks all session configurations
- **Dynamic Color Application**: JavaScript applies class colors from backend response to schedule blocks
- **Color State Management**: `classColors` object maintains color mappings throughout interface

### API Enhancements
- **Enhanced /set_selection**: Accepts `session_assignments` data structure
- **Improved /generate_schedule**: Returns partial schedules with detailed statistics and class colors
- **Session-Aware Data Flow**: Complete integration of session data throughout request lifecycle
- **Color-Enhanced Responses**: All schedule data includes color information for frontend rendering

## Data Quality & Error Handling Features
- **Automatic CSV Cleaning** - Removes extra spaces, normalizes formatting during import
- **Student List Normalization** - Cleans semicolon-separated student names
- **Advanced Conflict Detection** - Precise matching prevents false conflicts from formatting issues
- **Comprehensive Error Logging** - Detailed debugging for manual session processing
- **Graceful Failure Recovery** - System continues operation even with partial failures
- **Real-time Validation** - Immediate feedback on data quality and scheduling conflicts

## Smart Session Consistency Examples

### 12-Credit Class Example
- **Manual Assignment**: Class 1 = Monday, Period 2, Classroom 6
- **Smart Auto-Assignment**: 
  - Class 2 = Wednesday, Period 2, Classroom 6
  - Class 3 = Friday, Period 2, Classroom 6
- **Result**: Complete M/W/F pattern with period and room consistency

### 8-Credit Class Example  
- **Manual Assignment**: Class 1 = Tuesday, Period 4, Open (room)
- **Smart Auto-Assignment**: Class 2 = Thursday, Period 4, (available classroom)
- **Result**: T/Th pattern with period consistency and automatic room assignment

### Mixed Manual/Auto Example
- **Manual Assignment**: Class 1 = Monday, Period 8, Classroom 2
- **Room Preference**: Class 2 = Open (day/period), Classroom 2 (room)
- **Smart Auto-Assignment**: Class 2 = Wednesday, Period 2, Classroom 2  
- **Result**: Academic M/W pattern with room consistency preserved

### Hybrid Flexibility Example
- **Manual Assignment**: Class 1 = Friday, Period 1, Computer Lab
- **Auto Sessions**: Class 2 & 3 = Open, Open, Computer Lab
- **Smart Auto-Assignment**: Auto-scheduler places remaining sessions maintaining Computer Lab room assignment while finding optimal day/period combinations

## Current Status & Recent Enhancements
- **All Core Features Complete** - Upload, selection, multi-session scheduling, PDF export fully functional
- **Smart Session Consistency Implemented** - Advanced pattern detection and session coordination
- **Multi-Session Dropdown Interface** - Individual controls for each class session with time-enhanced period dropdowns
- **Enhanced Room Assignment Logic** - Eliminates TBD assignments, supports room preferences
- **Partial Schedule Support** - Returns useful schedules even with some conflicts
- **Extended Period Support** - Full 10-period scheduling including evening periods
- **Comprehensive Error Handling** - Detailed logging and graceful error recovery
- **Advanced Conflict Resolution** - Session-aware conflict detection and reporting
- **Academic Pattern Intelligence** - Automatic completion of standard scheduling patterns
- **Dynamic Class Colors** - HSL-based color generation system for visual class identification (NEW)

## Development Notes
- **Experiment Branch Active** - Latest features developed in `experiment` branch for testing
- **Comprehensive Test Coverage** - Multiple test scenarios for session consistency validation
- **Future Enhancements**: Additional pattern recognition, advanced optimization algorithms
- **Performance Optimized** - Efficient algorithms handle complex multi-session scenarios
- **User Experience Focus** - Intuitive interface with smart defaults and helpful feedback

## Git Configuration
- **GitHub Repository**: https://github.com/CobraPhil/ClassScheduler.git
- **Deploy Command**: `git push origin master` (pushes to Render via GitHub integration)
- **Note**: Personal access token required for authentication (stored securely outside repository)