from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv
from app.models import Student, Submission, Answer, Assessment, AssessmentQuestion

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")
if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
else:
    engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def seed_demo_data():
    db = SessionLocal()
    try:
        # Check if already seeded
        if db.query(Student).first():
            print("Database already seeded. Skipping.")
            return

        print("Seeding database with demo data...")
        
        # Add students
        students = [
            Student(student_id='STU001', name='Ahmed Ali', class_grade='10A'),
            Student(student_id='STU002', name='Fatima Khan', class_grade='10A'),
            Student(student_id='STU003', name='Hassan Malik', class_grade='10B')
        ]
        db.add_all(students)
        db.commit()

        # Add assessment
        assessment = Assessment(
            subject='Mathematics',
            title='Midterm Exam',
            total_marks=20.0,
            num_questions=4
        )
        db.add(assessment)
        db.commit()
        db.refresh(assessment)

        # Add assessment questions
        questions = [
            AssessmentQuestion(assessment_id=assessment.id, question_number=1, question_text='What is the derivative of x^2?', model_answer='2x', max_marks=5.0),
            AssessmentQuestion(assessment_id=assessment.id, question_number=2, question_text='Solve: 2x + 5 = 15', model_answer='x = 5', max_marks=5.0),
            AssessmentQuestion(assessment_id=assessment.id, question_number=3, question_text='What is the integral of 1/x?', model_answer='ln(x) + C', max_marks=5.0),
            AssessmentQuestion(assessment_id=assessment.id, question_number=4, question_text='Define a function', model_answer='A relation where each input has exactly one output', max_marks=5.0)
        ]
        db.add_all(questions)
        db.commit()

        # Add submissions
        sub1 = Submission(
            student_id='STU001',
            assessment_id=assessment.id,
            subject_name='Mathematics',
            file_path='/uploads/papers/math_paper_001.pdf',
            status='checked',
            num_questions=4,
            total_marks=19.5,
            max_total_marks=20.0
        )
        db.add(sub1)
        db.commit()

        # Add answers
        answers = [
            Answer(submission_id=sub1.submission_id, question_number=1, question_text='What is the derivative of x^2?', answer_text='2x', model_answer='2x', marks_obtained=5.00, max_marks=5.00, correct_answer_text='2x'),
            Answer(submission_id=sub1.submission_id, question_number=2, question_text='Solve: 2x + 5 = 15', answer_text='x = 5', model_answer='x = 5', marks_obtained=5.00, max_marks=5.00, correct_answer_text='x = 5'),
            Answer(submission_id=sub1.submission_id, question_number=3, question_text='What is the integral of 1/x?', answer_text='ln(x) + C', model_answer='ln(x) + C', marks_obtained=4.50, max_marks=5.00, correct_answer_text='ln(x) + C'),
            Answer(submission_id=sub1.submission_id, question_number=4, question_text='Define a function', answer_text='A relation where each input has exactly one output', model_answer='A relation where each input has exactly one output', marks_obtained=5.00, max_marks=5.00, correct_answer_text='A relation where each input has exactly one output')
        ]
        db.add_all(answers)
        db.commit()
        
        print("Demo data seeded successfully.")
    except Exception as e:
        db.rollback()
        print(f"Error seeding data: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    seed_demo_data()
