import jsPDF from 'jspdf';
import { cleanStudentAnswer } from './textUtils';

export function exportResultPdf(result) {
    if (!result || !result.questions) {
        alert('Unable to generate PDF: Invalid result data');
        return;
    }

    const doc = new jsPDF();
    const pageWidth = doc.internal.pageSize.getWidth();
    const pageHeight = doc.internal.pageSize.getHeight();
    const margin = 15;
    const maxWidth = pageWidth - margin * 2;

    const checkPageBreak = (currentY, requiredSpace = 20) => {
        if (currentY + requiredSpace > pageHeight - margin) {
            doc.addPage();
            return margin;
        }
        return currentY;
    };

    // cleanStudentAnswer imported from textUtils

    // Header
    doc.setFillColor(245, 247, 250);
    doc.rect(0, 0, pageWidth, 35, 'F');
    doc.setFontSize(22);
    doc.setFont(undefined, 'bold');
    doc.setTextColor(30, 41, 59);
    doc.text('FairMark Assessment Report', margin, 18);

    const now = new Date();
    const dateStr = now.toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' });
    const timeStr = now.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
    doc.setFontSize(9);
    doc.setFont(undefined, 'normal');
    doc.setTextColor(100, 116, 139);
    doc.text(`Generated: ${dateStr} at ${timeStr}`, margin, 28);

    let y = 45;

    // Student Information
    doc.setFontSize(13);
    doc.setFont(undefined, 'bold');
    doc.setTextColor(30, 41, 59);
    doc.text('Student Information', margin, y);
    y += 2;
    doc.setDrawColor(226, 232, 240);
    doc.setLineWidth(0.5);
    doc.line(margin, y, pageWidth - margin, y);
    y += 8;

    doc.setFontSize(10);
    [
        { label: 'Student Name:', value: result.studentName || 'Not Detected' },
        { label: 'Student ID:', value: result.rollNumber || 'Not Detected' },
        { label: 'Subject:', value: result.subject || 'N/A' }
    ].forEach(info => {
        doc.setFont(undefined, 'bold');
        doc.setTextColor(71, 85, 105);
        doc.text(info.label, margin, y);
        doc.setFont(undefined, 'normal');
        doc.setTextColor(30, 41, 59);
        doc.text(info.value, margin + 35, y);
        y += 6;
    });

    y += 8;

    // Performance Summary
    y = checkPageBreak(y, 35);
    // Pre-blend score color with white at 10% opacity (jsPDF doesn't support RGBA)
    const scoreRaw = result.score >= 80 ? [34, 197, 94] : result.score >= 60 ? [251, 146, 60] : [239, 68, 68];
    const scoreColor = scoreRaw.map(c => Math.round(c * 0.1 + 255 * 0.9));
    doc.setFillColor(scoreColor[0], scoreColor[1], scoreColor[2]);
    doc.roundedRect(margin, y - 5, maxWidth, 28, 3, 3, 'F');
    doc.setFontSize(13);
    doc.setFont(undefined, 'bold');
    doc.setTextColor(30, 41, 59);
    doc.text('Performance Summary', margin + 5, y + 3);
    doc.setFontSize(24);
    doc.setTextColor(scoreRaw[0], scoreRaw[1], scoreRaw[2]);
    const scoreDisplay = result.totalMarks != null
      ? `${result.totalMarks}/${result.maxTotalMarks}`
      : `${result.score}%`;
    doc.text(scoreDisplay, pageWidth - margin - 35, y + 5);
    y += 15;

    doc.setFontSize(9);
    doc.setFont(undefined, 'normal');
    doc.setTextColor(71, 85, 105);
    let xPos = margin + 5;
    [
        { label: 'Total Questions:', value: result.totalQuestions || result.questions.length },
        { label: 'Attempted:', value: result.attempted || 'N/A' },
        { label: 'Correct:', value: result.correctAnswers || 'N/A' }
    ].forEach(info => {
        doc.setFont(undefined, 'bold');
        doc.text(info.label, xPos, y);
        doc.setFont(undefined, 'normal');
        doc.text(String(info.value), xPos + 30, y);
        xPos += 60;
    });
    y += 15;

    // Questions Section header
    y = checkPageBreak(y, 30);
    doc.setFontSize(13);
    doc.setFont(undefined, 'bold');
    doc.setTextColor(30, 41, 59);
    doc.text('Question-wise Analysis', margin, y);
    y += 2;
    doc.setDrawColor(226, 232, 240);
    doc.setLineWidth(0.5);
    doc.line(margin, y, pageWidth - margin, y);
    y += 10;

    // Questions — single-pass rendering (no double-draw)
    result.questions.forEach((q, idx) => {
        const cleanedAnswer = cleanStudentAnswer(q.studentAnswer);
        const questionLines = doc.splitTextToSize(q.question || 'Full Response', maxWidth - 10);
        const answerLines = doc.splitTextToSize(cleanedAnswer, maxWidth - 10);
        const expectedLines = doc.splitTextToSize(q.correctAnswer || 'N/A', maxWidth - 10);

        // Pre-calculate box height so we can draw it once
        const boxHeight =
            7 +                                // question header row
            questionLines.length * 5 + 4 +    // question text
            5 + answerLines.length * 4 + 3 +  // student answer label + lines
            5 + expectedLines.length * 4 +    // expected answer label + lines
            8;                                 // bottom padding

        y = checkPageBreak(y, boxHeight + 4);
        const boxStartY = y - 3;

        // Draw background box ONCE with correct height
        doc.setFillColor(249, 250, 251);
        doc.roundedRect(margin, boxStartY, maxWidth, boxHeight, 2, 2, 'F');

        // Question header
        doc.setFont(undefined, 'bold');
        doc.setTextColor(30, 41, 59);
        doc.setFontSize(10);
        doc.text(`Question ${idx + 1}:`, margin + 3, y);

        // Score badge
        const qScore = q.maxScore > 0 ? (q.score / q.maxScore) * 100 : 0;
        const qColorRaw = qScore >= 80 ? [34, 197, 94] : qScore >= 50 ? [251, 146, 60] : [239, 68, 68];
        const qColor = qColorRaw.map(c => Math.round(c * 0.15 + 255 * 0.85));
        doc.setFillColor(qColor[0], qColor[1], qColor[2]);
        doc.setDrawColor(qColorRaw[0], qColorRaw[1], qColorRaw[2]);
        doc.setLineWidth(0.5);
        doc.roundedRect(pageWidth - margin - 20, y - 4, 18, 6, 1, 1, 'FD');
        doc.setFontSize(9);
        doc.setTextColor(qColor[0], qColor[1], qColor[2]);
        doc.text(`${q.score}/${q.maxScore}`, pageWidth - margin - 18, y);
        y += 6;

        // Question text
        doc.setFontSize(10);
        doc.setFont(undefined, 'normal');
        doc.setTextColor(51, 65, 85);
        questionLines.forEach(line => { doc.text(line, margin + 3, y); y += 5; });
        y += 4;

        // Student answer
        doc.setFont(undefined, 'bold');
        doc.setFontSize(9);
        doc.setTextColor(71, 85, 105);
        doc.text("STUDENT'S ANSWER", margin + 3, y);
        y += 5;
        doc.setFont(undefined, 'normal');
        doc.setTextColor(51, 65, 85);
        answerLines.forEach(line => { doc.text(line, margin + 3, y); y += 4; });
        y += 3;

        // Expected answer
        doc.setFont(undefined, 'bold');
        doc.setFontSize(9);
        doc.setTextColor(71, 85, 105);
        // G2: Label shows source of reference answer
        const isAiSuggested = ['manual_review_suggested_answer', 'ai_assisted', 'gemini_assisted'].includes(q.gradingMethod);
        const expectedLabel = isAiSuggested
            ? 'EXPECTED ANSWER (AI-suggested — verify before finalising)'
            : 'EXPECTED ANSWER';
        doc.text(expectedLabel, margin + 3, y);
        y += 5;
        doc.setFont(undefined, 'normal');
        doc.setTextColor(51, 65, 85);
        expectedLines.forEach(line => { doc.text(line, margin + 3, y); y += 4; });

        y += 8;
    });

    // Footer on every page
    const totalPages = doc.internal.pages.length - 1;
    const footerDate = now.toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' });
    const footerTime = now.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
    for (let i = 1; i <= totalPages; i++) {
        doc.setPage(i);
        doc.setDrawColor(226, 232, 240);
        doc.setLineWidth(0.3);
        doc.line(margin, pageHeight - 15, pageWidth - margin, pageHeight - 15);
        doc.setFontSize(8);
        doc.setFont(undefined, 'normal');
        doc.setTextColor(148, 163, 184);
        doc.text('FairMark Assessment System', margin, pageHeight - 10);
        doc.text(`${footerDate} • ${footerTime}`, pageWidth / 2, pageHeight - 10, { align: 'center' });
        doc.text(`Page ${i} of ${totalPages}`, pageWidth - margin, pageHeight - 10, { align: 'right' });
    }

    const studentName = result.studentName?.replace(/[^a-z0-9]/gi, '_') || 'Student';
    const subject = result.subject?.replace(/[^a-z0-9]/gi, '_') || 'Assessment';
    const fileDate = now.toISOString().split('T')[0];
    doc.save(`FairMark_${studentName}_${subject}_${fileDate}.pdf`);
}

export default exportResultPdf;
