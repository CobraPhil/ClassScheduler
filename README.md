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
3. **Confirm Selection**: Click "Confirm Selection" to save day/period/room choices
4. **Generate Schedule**: Create the weekly grid (errors are recalculated fresh each run)
5. **Export**: Download as PDF (if WeasyPrint installed) or styled HTML fallback

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

## What's New (Ver. 1.0)

- Drag-and-drop reliability: Moves target the exact session using original day/period and sessionIndex, preventing mis-removals after multiple drags.
- Room preserved on moves: When dragging a session, its room is kept. Room conflicts are not blocked during drag; they are reported on Generate.
- Robust conflict checks: Prevents dropping a session onto another session of the same class, even after intermediate moves. Teacher/student conflicts remain blocked.
- Export parity fixes: Period keys normalized so the exported schedule exactly matches the on-screen grid (e.g., Period 1 vs "1" issues fixed).
- Room conflict UX: On the schedule grid, conflicting rooms show a red badge; a "Room Conflicts" summary lists all collisions across the week.
- Export conflict visibility: PDF/HTML export includes a Room Conflicts summary and highlights conflicted class blocks.
- Fresh error reporting: Generate Schedule clears previous errors/warnings and recomputes new ones; Confirm Selection also clears stale panels.
- UI: Header shows "Ver. 1.0" superscript to indicate the current version.

## Tips and Notes

- Be sure to click "Confirm Selection" after changing Day/Period/Room in the Select tab so your changes are saved before generating.
- Drag-and-drop blocks teacher/student conflicts; room conflicts are allowed and surfaced during Generate/Export.
- WeasyPrint is optional. If not installed, Export will download a styled HTML file instead of a PDF.
