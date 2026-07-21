// ============================================
// FILE: src/services/api.js
// ============================================
const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000/api';

// C2: Credentials must be set via environment variables.
// Create frontend/my-app/.env and set REACT_APP_API_USER and REACT_APP_API_PASS.
// No hardcoded fallback — missing credentials will produce a clear 401 error
// rather than silently using a known default password.
const _apiUser = process.env.REACT_APP_API_USER;
const _apiPass = process.env.REACT_APP_API_PASS;

if (!_apiUser || !_apiPass) {
  console.error(
    '[FairMark] REACT_APP_API_USER or REACT_APP_API_PASS is not set in .env. ' +
    'All API calls will fail with 401. Add these to frontend/my-app/.env and restart.'
  );
}

// M6: Every request gets an AbortController-backed timeout so a hung backend
// surfaces as a clear error instead of an infinite spinner. Grading is slow
// (OCR + model), so it uses a longer timeout than the lightweight reads.
const DEFAULT_TIMEOUT_MS = 30000;

const fetchWithAuth = async (url, options = {}) => {
  const authHeader = 'Basic ' + btoa(`${_apiUser || ''}:${_apiPass || ''}`);

  const headers = new Headers(options.headers || {});
  headers.append('Authorization', authHeader);

  const { timeoutMs = DEFAULT_TIMEOUT_MS, retries = 2, ...fetchOptions } = options;

  let lastError;
  for (let attempt = 0; attempt <= retries; attempt++) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);
    try {
      const response = await fetch(url, {
        ...fetchOptions,
        headers,
        credentials: 'omit',
        signal: controller.signal,
      });
      clearTimeout(timer);
      return response;
    } catch (err) {
      clearTimeout(timer);
      lastError = err;
      // Only retry on network errors (TypeError), not on aborts or other errors
      if (err.name === 'AbortError' || attempt === retries) throw err;
      // Wait before retrying: 500ms, then 1000ms
      await new Promise((r) => setTimeout(r, 500 * (attempt + 1)));
    }
  }
  throw lastError;
};

const buildValidationMessage = (detail) => {
  if (!Array.isArray(detail)) return '';

  return detail
    .map((item) => {
      if (typeof item === 'string') return item;
      if (item?.msg && Array.isArray(item?.loc)) {
        return `${item.loc.join(' -> ')}: ${item.msg}`;
      }
      if (item?.msg) return item.msg;
      return '';
    })
    .filter(Boolean)
    .join(' | ');
};

const extractErrorMessage = async (response, fallbackMessage) => {
  let payload = null;

  try {
    payload = await response.json();
  } catch {
    try {
      const text = await response.text();
      if (text?.trim()) {
        payload = { detail: text.trim() };
      }
    } catch {
      payload = null;
    }
  }

  const detail = payload?.detail ?? payload?.error ?? payload?.message;

  let message = '';
  if (typeof detail === 'string') {
    message = detail;
  } else if (Array.isArray(detail)) {
    message = buildValidationMessage(detail);
  } else if (detail && typeof detail === 'object') {
    message = detail.message || detail.msg || '';
  } else if (typeof payload === 'string') {
    message = payload;
  }

  if (!message) {
    message = fallbackMessage;
  }

  if (response.status === 401) {
    return `${message} Please check the backend username and password used by the frontend.`;
  }

  if (response.status === 403) {
    return `${message} You do not have permission to perform this action.`;
  }

  if (response.status === 429) {
    return `${message} Too many requests were sent. Please wait a moment and try again.`;
  }

  if (response.status >= 500) {
    return `${message} The backend hit an internal error while processing the request.`;
  }

  return message;
};

const normalizeRequestError = (error, fallbackMessage) => {
  if (error?.name === 'AbortError') {
    return 'The request took too long and was cancelled. Please try again.';
  }

  if (error instanceof TypeError && /fetch/i.test(error.message)) {
    return `Could not reach the backend at ${API_URL}. Make sure the backend server is running and accessible.`;
  }

  return error?.message || fallbackMessage;
};

export const api = {
  getStatus: async () => {
    try {
      const response = await fetchWithAuth(`${API_URL}/status`);
      if (!response.ok) throw new Error('Status check failed');
      return await response.json();
    } catch {
      return { status: 'unknown', nlp_loaded: true, nlp_available: false };
    }
  },

  uploadAnswerKey: async (subject, questions, file = null) => {
    try {
      const formData = new FormData();
      if (file) {
        formData.append('file', file);
      } else {
        formData.append('subject', subject);
        formData.append('questions', JSON.stringify(questions));
      }
      const response = await fetchWithAuth(`${API_URL}/upload-answer-key`, {
        method: 'POST',
        body: formData,
      });
      if (!response.ok) {
        throw new Error(await extractErrorMessage(response, 'Failed to upload answer key'));
      }
      return await response.json();
    } catch (error) {
      console.error('Upload Answer Key Error:', error);
      throw new Error(normalizeRequestError(error, 'Failed to upload answer key'));
    }
  },

  getDashboard: async () => {
    try {
      const response = await fetchWithAuth(`${API_URL}/dashboard`);
      if (!response.ok) throw new Error('Failed to fetch dashboard');
      return await response.json();
    } catch (error) {
      console.error('Get Dashboard Error:', error);
      return { recentActivity: [], topPerformers: [], subjectStats: [] };
    }
  },

  getQuestionBank: async (subject = null) => {
    try {
      const url = subject
        ? `${API_URL}/question-bank?subject=${encodeURIComponent(subject)}`
        : `${API_URL}/question-bank`;
      const response = await fetchWithAuth(url);
      if (!response.ok) throw new Error('Failed to fetch question bank');
      return await response.json();
    } catch (error) {
      console.error('Get Question Bank Error:', error);
      return [];
    }
  },

  deleteQuestionBankEntry: async (id) => {
    const response = await fetchWithAuth(`${API_URL}/question-bank/${id}`, { method: 'DELETE' });
    if (!response.ok) {
      throw new Error(await extractErrorMessage(response, 'Failed to delete entry'));
    }
    return await response.json();
  },

  /**
   * Update a question-bank entry in place (e.g. fill/edit the model answer).
   * @param {number} id - Entry ID
   * @param {{question_text?: string, answer?: string, max_marks?: number}} fields
   */
  updateQuestionBankEntry: async (id, fields) => {
    try {
      const response = await fetchWithAuth(`${API_URL}/question-bank/${id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(fields),
      });
      if (!response.ok) {
        throw new Error(await extractErrorMessage(response, 'Failed to update entry'));
      }
      return await response.json();
    } catch (error) {
      console.error('Update Question Bank Error:', error);
      throw new Error(normalizeRequestError(error, 'Failed to update entry'));
    }
  },

  /**
   * Upload and grade a paper.
   * Subject, student ID, and total marks are auto-detected by OCR from the paper.
   * @param {File} file - The image file to upload
   * @returns {Promise} - Grading results
   */
  gradePaper: async (file) => {
    try {
      const formData = new FormData();
      formData.append('file', file);

      const response = await fetchWithAuth(`${API_URL}/grade`, {
        method: 'POST',
        body: formData,
        timeoutMs: 120000, // OCR + grading can legitimately take up to ~2 min
      });

      if (!response.ok) {
        throw new Error(await extractErrorMessage(response, 'Failed to grade paper'));
      }

      return await response.json();
    } catch (error) {
      console.error('Grade Paper Error:', error);
      throw new Error(normalizeRequestError(error, 'Failed to grade paper'));
    }
  },

  /**
   * Search for students by ID or Name
   * @param {string} query - Student ID or Name
   * @param {number} skip - Number of results to skip (for pagination)
   * @param {number} limit - Max results to return
   * @returns {Promise} - Array of matching results
   */
  searchStudents: async (query, skip = 0, limit = 50) => {
    try {
      const response = await fetchWithAuth(
        `${API_URL}/search?query=${encodeURIComponent(query)}&skip=${skip}&limit=${limit}`
      );

      if (!response.ok) {
        throw new Error(await extractErrorMessage(response, 'Search failed'));
      }

      return await response.json();
    } catch (error) {
      console.error('Search Error:', error);
      throw new Error(normalizeRequestError(error, 'Search failed'));
    }
  },

  /**
   * Get all grading history
   * @returns {Promise} - Array of all grading records
   */
  getHistory: async () => {
    try {
      const response = await fetchWithAuth(`${API_URL}/history`);

      if (!response.ok) {
        throw new Error(await extractErrorMessage(response, 'Failed to fetch history'));
      }

      return await response.json();
    } catch (error) {
      console.error('Get History Error:', error);
      throw new Error(normalizeRequestError(error, 'Failed to fetch history'));
    }
  },

  /**
   * Get specific grading result by ID
   * @param {number} id - Result ID
   * @returns {Promise} - Detailed result object
   */
  getResult: async (id) => {
    try {
      const response = await fetchWithAuth(`${API_URL}/result/${id}`);

      if (!response.ok) {
        throw new Error(await extractErrorMessage(response, 'Failed to fetch result'));
      }

      return await response.json();
    } catch (error) {
      console.error('Get Result Error:', error);
      throw new Error(normalizeRequestError(error, 'Failed to fetch result'));
    }
  },

  /**
   * Get dashboard statistics
   * @returns {Promise} - Statistics object
   */
  getStats: async () => {
    try {
      const response = await fetchWithAuth(`${API_URL}/stats`);

      if (!response.ok) {
        throw new Error(await extractErrorMessage(response, 'Failed to fetch statistics'));
      }

      return await response.json();
    } catch (error) {
      console.error('Get Stats Error:', error);
      throw new Error(normalizeRequestError(error, 'Failed to fetch statistics'));
    }
  },

  /**
   * Get list of available subjects
   * @returns {Promise} - Array of subjects
   */
  getSubjects: async () => {
    try {
      const response = await fetchWithAuth(`${API_URL}/subjects`);

      if (!response.ok) {
        throw new Error(await extractErrorMessage(response, 'Failed to fetch subjects'));
      }

      return await response.json();
    } catch (error) {
      console.error('Get Subjects Error:', error);
      // Return default subjects if API fails
      return {
        subjects: ['General Science']
      };
    }
  },

  /**
   * Approve or edit an AI-generated expected answer
   */
  approveAnswer: async (submissionId, questionNumber, modelAnswer) => {
    try {
      const response = await fetchWithAuth(`${API_URL}/assessments/approve-answer`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          submission_id: submissionId,
          question_number: questionNumber,
          model_answer: modelAnswer
        }),
        timeoutMs: 90000, // LLM regrading can take up to ~60s
      });

      if (!response.ok) {
        throw new Error(await extractErrorMessage(response, 'Failed to approve answer'));
      }

      return await response.json();
    } catch (error) {
      console.error('Approve Answer Error:', error);
      throw new Error(normalizeRequestError(error, 'Failed to approve answer'));
    }
  },

  /**
   * Save teacher-corrected OCR text and regrade only if a verified key matches.
   */
  correctOcrAnswer: async (submissionId, questionNumber, questionText, answerText) => {
    try {
      const response = await fetchWithAuth(`${API_URL}/answers/correct-ocr`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          submission_id: submissionId,
          question_number: questionNumber,
          question_text: questionText,
          answer_text: answerText
        }),
        timeoutMs: 90000, // regrading can involve LLM calls
      });

      if (!response.ok) {
        throw new Error(await extractErrorMessage(response, 'Failed to save OCR correction'));
      }

      return await response.json();
    } catch (error) {
      console.error('Correct OCR Error:', error);
      throw new Error(normalizeRequestError(error, 'Failed to save OCR correction'));
    }
  }
};

export default api;
