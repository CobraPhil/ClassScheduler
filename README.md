# Class Schedule Generator

A web-based application for generating conflict-free weekly class schedules with automatic room assignments.

## Features

- **CSV Upload**: Upload ClassList.csv files with course enrollment data
- **Automatic Scheduling**: Generate conflict-free schedules respecting all constraints
- **Room Assignment**: Automatic assignment based on course type and enrollment
- **Weekly Grid View**: Visual schedule display showing all periods 1-8
- **PDF Export**: Professional PDF output for printing and sharing
- **Conflict Resolution**: Two-tier approach with Period 7 fallback option

## Quick Start

### Windows Users
1. Open Command Prompt or PowerShell
2. Navigate to the ClassScheduler folder
3. Run: `python run.py`
4. Open browser to: http://127.0.0.1:5000

### Linux/Mac Users
1. Run: `./install_requirements.sh` (first time only)
2. Run: `python3 app.py`
3. Open browser to: http://127.0.0.1:5000

## Requirements

- Python 3.7 or higher
- Flask 2.3.3
- pandas 2.1.3
- WeasyPrint 60.2

## Usage

1. **Upload CSV**: Select your ClassList.csv file
2. **Select Classes**: Choose which classes to include in the schedule
3. **Generate Schedule**: Click "Generate Schedule" to create the weekly grid
4. **Export PDF**: Download the schedule as a professional PDF

## Scheduling Rules

### Room Assignments
- **Computer Lab**: All computer classes (GECO) and ESL classes (GELA)
- **Chapel**: Classes with over 40 students
- **Regular Classrooms**: Classroom 2, 4, 5, 6 for other classes

### Time Periods
- **Periods 1-2, 4-6**: Regular class periods (Period 3 reserved for Chapel)
- **Period 7**: Available when conflicts occur in regular periods
- **Period 8**: Reserved for Kia Kawage and Philip Tama classes

### Meeting Frequency
- **4 credits**: 1 time per week
- **8 credits**: 2 times per week (preferably Tuesday/Thursday)
- **12 credits**: 3 times per week (preferably Monday/Wednesday/Friday)

### Conflict Prevention
- No teacher can teach multiple classes at the same time
- No student can be enrolled in multiple classes at the same time

## CSV Format

Your ClassList.csv should contain these columns:
- `Class`: Course code/identifier
- `Course Name`: Full course name
- `Units`: Credit hours (4, 8, or 12)
- `Teacher`: Instructor name
- `Students`: Semicolon-separated list of enrolled students

## Troubleshooting

If the schedule generation fails:
1. Try clicking "Try with Period 7" to use additional time slots
2. Review conflict details to identify problematic classes
3. Consider reducing class selections or manual adjustments

## Technical Details

Built with Flask (Python) for easy local deployment. The constraint satisfaction algorithm prioritizes classes by scheduling difficulty and uses a greedy approach with backtracking for optimal room and time assignments.

## Support

For issues or questions, refer to the CLAUDE.md file for project-specific notes and requirements.