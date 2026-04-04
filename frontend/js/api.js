/**
 * frontend/js/api.js
 * Central API client for all backend calls.
 * All fetch calls go through this module.
 */

const API = {

  /**
   * Upload a note file (or PYQ) and get OCR + AI processing back.
   * @param {File}   file
   * @param {string} subject
   * @param {string} university
   * @param {string} uploadType - 'note' or 'pyq'
   * @returns {Promise<Object>}
   */
  uploadNote: async function (file, subject, university = '', uploadType = 'note') {
    const form = new FormData();
    form.append('file',       file);
    form.append('subject',    subject);
    form.append('university', university);

    // Use different endpoints for notes vs pyqs
    const endpoint = uploadType === 'pyq' ? '/api/upload/pyq' : '/api/upload/note';

    const res = await fetch(endpoint, {
      method: 'POST',
      body: form,
      credentials: 'include'
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  /**
   * Upload a PYQ paper (Specific legacy call if needed).
   */
  uploadPYQ: async function (file, subject, university, year) {
    const form = new FormData();
    form.append('file',       file);
    form.append('subject',    subject);
    form.append('university', university);
    form.append('year',       year);

    const res = await fetch('/api/upload/pyq', {
      method: 'POST',
      body: form,
      credentials: 'include'
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  /**
   * Generate a question paper using AI.
   * @param {string}   noteId
   * @param {number}   questionCount
   * @param {string}   subject
   * @param {string}   university
   * @param {string[]} keywords
   */
  generatePaper: async function (noteId, questionCount = 20, subject = '', university = '', keywords = []) {
    const res = await fetch('/api/ai/generate-paper', {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({ 
        note_id: noteId, 
        question_count: questionCount,
        subject, 
        university, 
        keywords 
      }),
      credentials: 'include'
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  /**
   * Summarize a note using AI.
   * @param {string} noteId
   */
  summarizeNote: async function (noteId) {
    const res = await fetch('/api/ai/summarize', {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({ note_id: noteId }),
      credentials: 'include'
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  /**
   * Tag questions with difficulty.
   * @param {Object[]} questions — array of {text, marks, section, topic}
   */
  tagDifficulty: async function (questions) {
    const res = await fetch('/api/ai/tag-difficulty', {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({ questions }),
      credentials: 'include'
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  /**
   * Get topic frequency for analytics page.
   * @param {string} subject
   * @param {string} university
   */
  getTopicFrequency: async function (subject, university = '') {
    const params = new URLSearchParams({ subject, university });
    const res    = await fetch(`/api/notes/topic-frequency?${params}`, {
      credentials: 'include'
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  /**
   * Generate an MCQ quiz using AI.
   * @param {string} noteId
   * @param {number} questionCount
   */
  generateQuiz: async function (noteId, questionCount = 10) {
    const res = await fetch('/api/ai/generate-quiz', {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({ note_id: noteId, question_count: questionCount }),
      credentials: 'include'
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  /**
   * Submit quiz results.
   */
  submitQuiz: async function (paperId, score, correct, total, timeTaken, subject, university) {
    const res = await fetch('/api/test/submit', {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({ 
        paper_id: paperId, 
        score, 
        correct, 
        total, 
        time_taken: timeTaken,
        subject,
        university
      }),
      credentials: 'include'
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },
  deleteNote: async function (noteId) {
    const res = await fetch(`/api/notes/${noteId}`, {
      method:  'DELETE',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include'
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

};

// Make globally available
window.API = API;