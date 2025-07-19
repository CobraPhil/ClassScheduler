# ClassScheduler Project

## Project Description
A class scheduling system for assigning rooms and class times depending on class rooster and teacher schedule.

## Key Files
- `ClassList.csv` - Contains class enrollment data with students, teachers, and course details

## Common Commands
- Build: [add your build command here]
- Test: [add your test command here]
- Lint: [add your lint command here]

## Notes
- CSV contains 33 classes across various departments (BBTTS, BTBL, BTCM, etc.)
- Many courses offered in both English and Pidgin versions
- Student enrollment ranges from 3-42+ students per class

## Project Requirements
 - Develope a web interface that is easy to use, modern looking, uses the latest technology that I can run locally and can be started and stopped easily.
 - The purpose of the website is to allow the operator to upload the ClassList.csv file. So the interface must allow the operator to select the file.
 - After selecting the file, there should be a button that say "Generate Schedule". This will start the process of generating a weekly schedule of classes.
 - The schedule will list the class, the teacher, and the classroom.
 - The list of classrooms that are available to be used are as follows:
   - Classroom 2
   - Classroom 4
   - Classroom 5
   - Classroom 6
   - Computer Lab
   - Chapel
 - All computer classes and ESL classes can only meet in the Computer Lab. No other classes should meet there.
 - Any class that has over 40 students in the class should meet in the Chapel. That is the only classroom big enough to hold that many students.
 - While deteriming the class schedule, you need to take into account the following:
	- There can be no teacher conflicts. A teacher can only teach one class at a time.
	- There should be no student conflicts. A students can only be in one class at a time.
	- If the class is 4 credits, it will meet once a week.
	- If the class is 8 credits, it will meet twice a week, preferably Tuesday and Thursday.
	- If the class is 12 credits, it will meet three times a week, preferably Monday, Wednesday, and Friday.
	- There are 6 regular class periods availabe Monady through Friday that can be used for scheduling classes. Periods 1 - Periods 6.
		- Period 3 should always be open. It is for Chapel which each student attends. Never schedule a class for period 3
		- Periods 7 - Periods 10 are also special periods. They should not be used unless specified in this CLAUDE.md file. Any special requests will be on the next lines.
			- Any class taught by Kia Kawage or Philip Tama should be scheduled for Period 8 on the days best determined by the other scheduling requirements.
			- Any class taught by Lori Smith should be scheduled for Period 1 on the days best determined by the other scheduling requirements.
		- Scheduling Priority Order:
			1. Try preferred days first (Tue/Thu for 8-credit, Mon/Wed/Fri for 12-credit)
			2. If preferred days don't work, try alternative day combinations before using Period 7
			3. For 8-credit classes: try Mon/Wed, Mon/Fri, Wed/Fri as alternatives
			4. For 12-credit classes: try Mon/Tue/Thu, Tue/Wed/Fri as alternatives
			5. Period 7 should only be used as an absolute last resort when no other day/period combinations work
			6. Always exhaust all possibilities in Periods 1-6 (and Period 8 for special teachers) before adding Period 7
	
 

   