/**
 * Shared grading utilities for FairMark frontend.
 * H5: Single source of truth for grade boundaries — mirrors backend/app/utils.py.
 * Any change to grade thresholds must be made here AND in the backend utils.
 */

/**
 * Return letter grade for a percentage score (0–100).
 * @param {number} score
 * @returns {string}
 */
export const getGrade = (score) => {
  if (score >= 90) return 'A+';
  if (score >= 80) return 'A';
  if (score >= 70) return 'B';
  if (score >= 60) return 'C';
  return 'D';
};
