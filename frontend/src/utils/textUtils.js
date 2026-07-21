/**
 * Shared text utilities for FairMark frontend.
 * Single source of truth for text cleaning functions.
 */

/**
 * Extract clean student answer (remove date and question text if present in OCR output)
 * @param {string} answer - Raw student answer text
 * @returns {string} Cleaned answer text
 */
export const cleanStudentAnswer = (answer) => {
  if (!answer) return 'Not Answered';
  
  // Remove date pattern (e.g., "October 24, 2024 Date :")
  let cleaned = answer.replace(/^[A-Za-z]+\s+\d{1,2},\s+\d{4}\s+Date\s*:\s*/i, '');
  
  // Remove question pattern (e.g., "Question-2: What is...") 
  cleaned = cleaned.replace(/^Question-?\d+\s*:\s*.+?\?\s*/i, '');
  
  // Remove numbered question pattern (e.g., "1. What is...")
  cleaned = cleaned.replace(/^\d+\.\s*.+?\?\s*/i, '');
  
  // Remove Answer prefix
  cleaned = cleaned.replace(/^(?:Answer|Ans)[\s:]*/i, '');
  
  return cleaned.trim() || answer;
};

/**
 * Extract clean question text (remove "Q1." and "[5 Marks]" artifacts)
 */
export const cleanQuestionText = (question) => {
  if (!question) return 'Full Response';
  
  let cleaned = question;
  // Strip "Question 1: " or "Q1. " or "Q1: " prefixes
  cleaned = cleaned.replace(/^(?:Question\s*\d+|Q\d+)[\s:\.]*/i, '');
  
  // Strip trailing marks like "[5 Marks]" or "(5 Marks)"
  cleaned = cleaned.replace(/\s*[\(\[]\d+\s*[Mm]arks?[\)\]][\s\.]*$/i, '');
  
  return cleaned.trim() || question;
};
