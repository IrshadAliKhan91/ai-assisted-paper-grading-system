import pytest
from backend.app.ocr_service import parse_student_info, parse_question_answers

def test_extract_student_info_from_text():
    sample_text = """
    Name: John Doe
    ID: STU-12345
    Subject: Computer Science
    
    Q1: What is a variable?
    A1: A variable is a storage location paired with an associated symbolic name.
    """
    
    info = parse_student_info(sample_text)
    assert info['student_name'] == 'John Doe'
    assert info['student_id'] == 'STU-12345'
    assert info['subject'] == 'Computer Science'

def test_extract_qa_pairs_from_text():
    sample_text = """
    Q1: What is a variable?
    Ans: A variable is a storage location paired with an associated symbolic name.
    
    Q2: What is a function?
    A2: A function is a block of organized, reusable code that is used to perform a single, related action.
    """
    
    qa_pairs = parse_question_answers(sample_text)
    assert len(qa_pairs) == 2
    assert qa_pairs[0]['question_number'] == 1
    assert qa_pairs[0]['question_text'] == "What is a variable?"
    assert "storage location" in qa_pairs[0]['answer_text']
    assert "What is a variable" not in qa_pairs[0]['answer_text']
    
    assert qa_pairs[1]['question_number'] == 2
    assert qa_pairs[1]['question_text'] == "What is a function?"
    assert "reusable code" in qa_pairs[1]['answer_text']
    assert "What is a function" not in qa_pairs[1]['answer_text']
