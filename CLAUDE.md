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
		- Period times:
			- Period 1: 7:00am-7:50am
			- Period 2: 8:00am-8:50am
			- Period 3: 9:00am-9:30am (Chapel - Never schedule classes)
			- Period 4: 9:40am-10:30am
			- Period 5: 10:40am-11:30am
			- Period 6: 11:40am-12:30pm
			- Period 7: 12:40pm-1:30pm (Special period - use only as last resort)
			- Period 8: 6:00pm-6:50pm (Special period for specific teachers)
		- Period 3 should always be open. It is for Chapel which each student attends. Never schedule a class for period 3
		- Periods 7 - Periods 10 are also special periods. They should not be used unless specified through manual period assignments via the dropdown interface.
		- Enhanced Scheduling Priority System:
			
			A. Overall Priority Hierarchy (most to least constrained):
				1. Manual period assignments (highest priority)
				2. Room constraints (Computer Lab, Chapel requirements)
				3. Class size (largest classes scheduled first)
				4. Preferred periods (2,4,5,6 before 1,7,8)
				5. Day combinations and period optimization
			
			B. Period Usage Priority:
				1. Periods 2,4,5,6 should be filled FIRST (core teaching periods)
				2. Period 1 used only when necessary or manually assigned
				3. Period 7 used as last resort
				4. Period 8 used only when manually assigned
				5. Always fill periods 2,4,5,6 completely before using Period 1 or 7
			
			C. Day Combination Strategy:
				1. Try preferred days first (Tue/Thu for 8-credit, Mon/Wed/Fri for 12-credit)
				2. If preferred days don't work in periods 2,4,5,6, try alternative day combinations
				3. For 8-credit classes: try Mon/Wed, Mon/Fri, Wed/Fri as alternatives
				4. For 12-credit classes: try Mon/Tue/Thu, Tue/Wed/Fri as alternatives
				5. Use non-preferred days before resorting to Period 1 or Period 7
			
			D. Solution Optimization:
				1. Do not use the first solution found
				2. Use multiple passes and sophisticated search algorithms
				3. Find optimal solution that:
					- Avoids Period 7 entirely if possible
					- Minimizes Period 1 usage (except required teachers)
					- Maximizes usage of core periods (2,4,5,6)
				4. Compare multiple solutions and select the best one
				5. Teacher-specific period requirements are now handled through manual period assignments in the web interface
	
 

   