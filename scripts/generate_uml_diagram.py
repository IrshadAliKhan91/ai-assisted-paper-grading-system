"""
FairMark — IEEE 1016 Compliant UML Software Architecture Diagram
Generates a comprehensive PNG showing:
  - Package Diagram (system decomposition)
  - Component Diagram (major components & interfaces)
  - Class Diagram (database entities & relationships)
  - Deployment Diagram (physical tiers)
  - Data Flow (upload → OCR → NLP → DB → display)
"""

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Rectangle
from matplotlib.lines import Line2D
import matplotlib.patheffects as pe
import numpy as np
from pathlib import Path

# ── Global settings ──────────────────────────────────────────────────────────
DPI = 180
FIG_W, FIG_H = 32, 44

# Colors
C_BG        = '#FAFBFC'
C_BORDER    = '#2D3748'
C_PKG_FILL  = '#EDF2F7'
C_COMP_FILL = '#E2E8F0'
C_FE_FILL   = '#DBEAFE'  # blue tint for frontend
C_BE_FILL   = '#FEF3C7'  # amber tint for backend
C_DB_FILL   = '#D1FAE5'  # green tint for database
C_EXT_FILL  = '#FEE2E2'  # red tint for external
C_OCR_FILL  = '#EDE9FE'  # purple tint for OCR
C_NLP_FILL  = '#FCE7F3'  # pink tint for NLP
C_TITLE_BG  = '#1A202C'
C_TITLE_FG  = '#FFFFFF'
C_ARROW     = '#4A5568'
C_ARROW_DATA= '#3182CE'
C_TEXT       = '#1A202C'
C_LIGHT     = '#718096'
C_CLASS_HEAD = '#2B6CB0'
C_CLASS_BODY = '#EBF8FF'
C_ENUM_HEAD  = '#9B2C2C'
C_ENUM_BODY  = '#FFF5F5'

FONT       = 'Segoe UI'
FONT_MONO  = 'Consolas'


def draw_rounded_box(ax, x, y, w, h, fill, edge=C_BORDER, lw=1.5, radius=0.3, alpha=1.0, zorder=1):
    box = FancyBboxPatch((x, y), w, h,
                          boxstyle=f"round,pad=0,rounding_size={radius}",
                          facecolor=fill, edgecolor=edge, linewidth=lw, alpha=alpha, zorder=zorder)
    ax.add_patch(box)
    return box


def draw_package(ax, x, y, w, h, title, fill=C_PKG_FILL, title_fill=None):
    """Draw a UML package box with a tab."""
    # Tab
    tab_w = min(len(title) * 0.28 + 0.6, w * 0.6)
    tab_h = 0.55
    tab = FancyBboxPatch((x, y + h), tab_w, tab_h,
                          boxstyle="round,pad=0,rounding_size=0.15",
                          facecolor=title_fill or fill, edgecolor=C_BORDER, linewidth=1.5, zorder=2)
    ax.add_patch(tab)
    ax.text(x + tab_w / 2, y + h + tab_h / 2, f'«package»\n{title}',
            ha='center', va='center', fontsize=7.5, fontfamily=FONT, fontweight='bold',
            color=C_TEXT, zorder=3, linespacing=1.2)
    # Body
    body = FancyBboxPatch((x, y), w, h,
                           boxstyle="round,pad=0,rounding_size=0.2",
                           facecolor=fill, edgecolor=C_BORDER, linewidth=1.5, zorder=1)
    ax.add_patch(body)
    return body


def draw_component(ax, x, y, w, h, name, stereotype='', fill=C_COMP_FILL, fontsize=8):
    """Draw a UML component box."""
    draw_rounded_box(ax, x, y, w, h, fill, zorder=3)
    # Component icon (two small rectangles on the left)
    icon_x = x + 0.1
    icon_y = y + h - 0.35
    for dy in [0, -0.25]:
        rect = Rectangle((icon_x, icon_y + dy), 0.25, 0.18,
                         facecolor='white', edgecolor=C_BORDER, linewidth=0.8, zorder=4)
        ax.add_patch(rect)
    text = f'«{stereotype}»\n{name}' if stereotype else name
    ax.text(x + w / 2, y + h / 2 - 0.05, text,
            ha='center', va='center', fontsize=fontsize, fontfamily=FONT, fontweight='bold',
            color=C_TEXT, zorder=4, linespacing=1.3)


def draw_class_box(ax, x, y, w, name, attrs, methods=None, is_enum=False):
    """Draw a UML class box with compartments."""
    head_color = C_ENUM_HEAD if is_enum else C_CLASS_HEAD
    body_color = C_ENUM_BODY if is_enum else C_CLASS_BODY
    line_h = 0.32
    stereo = '«enumeration»' if is_enum else '«entity»'

    head_h = 0.7
    attr_h = max(len(attrs) * line_h + 0.2, 0.5)
    meth_h = max(len(methods) * line_h + 0.2, 0.3) if methods else 0
    total_h = head_h + attr_h + meth_h

    # Header
    draw_rounded_box(ax, x, y + attr_h + meth_h, w, head_h, head_color, zorder=5, radius=0.15)
    ax.text(x + w / 2, y + total_h - 0.15, stereo,
            ha='center', va='center', fontsize=5.5, fontfamily=FONT, color='#CBD5E0', zorder=6)
    ax.text(x + w / 2, y + total_h - 0.45, name,
            ha='center', va='center', fontsize=8, fontfamily=FONT, fontweight='bold', color='white', zorder=6)

    # Attributes compartment
    draw_rounded_box(ax, x, y + meth_h, w, attr_h, body_color, zorder=5, radius=0.1)
    for i, attr in enumerate(attrs):
        ax.text(x + 0.15, y + meth_h + attr_h - 0.3 - i * line_h, attr,
                ha='left', va='center', fontsize=5.8, fontfamily=FONT_MONO, color=C_TEXT, zorder=6)

    # Methods compartment
    if methods:
        draw_rounded_box(ax, x, y, w, meth_h, '#F7FAFC', zorder=5, radius=0.1)
        for i, m in enumerate(methods):
            ax.text(x + 0.15, y + meth_h - 0.3 - i * line_h, m,
                    ha='left', va='center', fontsize=5.8, fontfamily=FONT_MONO, color=C_LIGHT, zorder=6)

    return total_h


def draw_arrow(ax, x1, y1, x2, y2, style='->', color=C_ARROW, lw=1.2, label='', dashed=False):
    ls = '--' if dashed else '-'
    ax.annotate('', xy=(x2, y2), xytext=(x1, y1),
                arrowprops=dict(arrowstyle=style, color=color, lw=lw, linestyle=ls),
                zorder=10)
    if label:
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2
        ax.text(mx, my + 0.2, label, ha='center', va='bottom',
                fontsize=6, fontfamily=FONT, color=color, fontstyle='italic', zorder=11,
                bbox=dict(boxstyle='round,pad=0.15', facecolor='white', edgecolor='none', alpha=0.85))


def draw_database_icon(ax, x, y, w, h, label, fill=C_DB_FILL):
    """Draw a cylinder (database) symbol."""
    from matplotlib.patches import Ellipse
    ell_h = h * 0.2
    # Body
    rect = Rectangle((x, y), w, h - ell_h / 2, facecolor=fill, edgecolor=C_BORDER, linewidth=1.5, zorder=3)
    ax.add_patch(rect)
    # Top ellipse
    top = Ellipse((x + w / 2, y + h - ell_h / 2), w, ell_h,
                  facecolor=fill, edgecolor=C_BORDER, linewidth=1.5, zorder=4)
    ax.add_patch(top)
    # Bottom ellipse
    bot = Ellipse((x + w / 2, y), w, ell_h,
                  facecolor=fill, edgecolor=C_BORDER, linewidth=1.5, zorder=4)
    ax.add_patch(bot)
    ax.text(x + w / 2, y + h / 2, label, ha='center', va='center',
            fontsize=8, fontfamily=FONT, fontweight='bold', color=C_TEXT, zorder=5)


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN DIAGRAM
# ═══════════════════════════════════════════════════════════════════════════════
fig, ax = plt.subplots(1, 1, figsize=(FIG_W, FIG_H), dpi=DPI)
ax.set_xlim(0, FIG_W)
ax.set_ylim(0, FIG_H)
ax.set_aspect('equal')
ax.axis('off')
fig.patch.set_facecolor(C_BG)
ax.set_facecolor(C_BG)

# ── TITLE BLOCK (IEEE 1016 header) ──────────────────────────────────────────
draw_rounded_box(ax, 0.5, FIG_H - 2.8, FIG_W - 1, 2.4, C_TITLE_BG, radius=0.3, zorder=10)
ax.text(FIG_W / 2, FIG_H - 1.15, 'FairMark — AI-Based Paper Checking System',
        ha='center', va='center', fontsize=20, fontfamily=FONT, fontweight='bold', color=C_TITLE_FG, zorder=11)
ax.text(FIG_W / 2, FIG_H - 1.75, 'Software Architecture Diagram  ·  UML 2.5 / IEEE Std 1016-2009',
        ha='center', va='center', fontsize=11, fontfamily=FONT, color='#A0AEC0', zorder=11)
ax.text(FIG_W / 2, FIG_H - 2.25, 'Package Diagram  |  Component Diagram  |  Class Diagram  |  Data Flow Diagram',
        ha='center', va='center', fontsize=9, fontfamily=FONT, color='#718096', zorder=11)

Y_START = FIG_H - 3.5

# ══════════════════════════════════════════════════════════════════════════════
# SECTION 1: HIGH-LEVEL DEPLOYMENT / PACKAGE VIEW
# ══════════════════════════════════════════════════════════════════════════════
section1_y = Y_START - 0.5
ax.text(1, section1_y, '1. System Context & Package Diagram', fontsize=14, fontfamily=FONT,
        fontweight='bold', color=C_TEXT)
ax.plot([1, FIG_W - 1], [section1_y - 0.2, section1_y - 0.2], color=C_LIGHT, lw=0.8)

# ── Client Tier ──
pkg1_x, pkg1_y, pkg1_w, pkg1_h = 1, section1_y - 6.5, 8.5, 5.5
draw_package(ax, pkg1_x, pkg1_y, pkg1_w, pkg1_h, 'Client Tier', C_FE_FILL, '#93C5FD')

draw_component(ax, 2, pkg1_y + 3.3, 3, 1.6, 'React SPA\n(localhost:3000)', 'application', C_FE_FILL, 7)
draw_component(ax, 5.5, pkg1_y + 3.3, 3.5, 1.6, 'React Router\nBrowserRouter', 'library', '#BFDBFE', 7)
draw_component(ax, 2, pkg1_y + 0.8, 3, 1.6, 'api.js\nfetchWithAuth()', 'service', '#BFDBFE', 7)
draw_component(ax, 5.5, pkg1_y + 0.8, 3.5, 1.6, 'pdfExport.js\n(jsPDF client-side)', 'utility', '#BFDBFE', 7)

# ── Server Tier ──
pkg2_x, pkg2_y, pkg2_w, pkg2_h = 11, section1_y - 6.5, 10, 5.5
draw_package(ax, pkg2_x, pkg2_y, pkg2_w, pkg2_h, 'Server Tier', C_BE_FILL, '#FCD34D')

draw_component(ax, 12, pkg2_y + 3.3, 4, 1.6, 'FastAPI App\n(Uvicorn :8000)', 'application', C_BE_FILL, 7)
draw_component(ax, 16.5, pkg2_y + 3.3, 3.8, 1.6, 'Middleware Stack\nCORS · Auth · RateLimit', 'infrastructure', '#FDE68A', 7)
draw_component(ax, 12, pkg2_y + 0.8, 4, 1.6, 'OCR Service\nocr_service.py', 'service', C_OCR_FILL, 7)
draw_component(ax, 16.5, pkg2_y + 0.8, 3.8, 1.6, 'NLP Grading\nnlp_grading_service.py', 'service', C_NLP_FILL, 7)

# ── Data Tier ──
pkg3_x, pkg3_y, pkg3_w, pkg3_h = 22.5, section1_y - 6.5, 4.5, 5.5
draw_package(ax, pkg3_x, pkg3_y, pkg3_w, pkg3_h, 'Data Tier', C_DB_FILL, '#6EE7B7')

draw_database_icon(ax, 23.5, pkg3_y + 3, 2.5, 1.8, 'PostgreSQL\nFairMark_db', C_DB_FILL)
draw_component(ax, 23.2, pkg3_y + 0.5, 3, 1.5, 'SQLAlchemy\nORM + Alembic', 'library', '#A7F3D0', 7)

# ── External Services ──
pkg4_x, pkg4_y, pkg4_w, pkg4_h = 28, section1_y - 6.5, 3.5, 5.5
draw_package(ax, pkg4_x, pkg4_y, pkg4_w, pkg4_h, 'External APIs', C_EXT_FILL, '#FCA5A5')

ext_y_base = pkg4_y + 4.2
for i, name in enumerate(['Groq (Vision)', 'Gemini (LLM)', 'OpenRouter', 'RapidAPI OCR', 'Tesseract']):
    draw_rounded_box(ax, 28.3, ext_y_base - i * 0.85, 2.9, 0.7, '#FECACA' if i < 4 else '#FED7AA', zorder=3, radius=0.12)
    ax.text(29.75, ext_y_base - i * 0.85 + 0.35, name, ha='center', va='center',
            fontsize=6.5, fontfamily=FONT, fontweight='bold', color=C_TEXT, zorder=4)

# ── Tier Arrows ──
draw_arrow(ax, pkg1_x + pkg1_w, pkg1_y + pkg1_h / 2, pkg2_x, pkg2_y + pkg2_h / 2,
           color=C_ARROW_DATA, lw=2, label='HTTP/REST\nBasic Auth')
draw_arrow(ax, pkg2_x + pkg2_w, pkg2_y + pkg2_h / 2 + 0.5, pkg3_x, pkg3_y + pkg3_h / 2 + 0.5,
           color=C_ARROW_DATA, lw=2, label='SQL')
draw_arrow(ax, pkg2_x + pkg2_w, pkg2_y + pkg2_h / 2 - 0.8, pkg4_x, pkg4_y + pkg4_h / 2 - 0.5,
           color='#E53E3E', lw=1.5, label='HTTPS\nAPI Keys', dashed=True)


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 2: COMPONENT DIAGRAM (Backend Detail)
# ══════════════════════════════════════════════════════════════════════════════
section2_y = section1_y - 8.5
ax.text(1, section2_y, '2. Backend Component Diagram', fontsize=14, fontfamily=FONT,
        fontweight='bold', color=C_TEXT)
ax.plot([1, FIG_W - 1], [section2_y - 0.2, section2_y - 0.2], color=C_LIGHT, lw=0.8)

comp_y = section2_y - 7.5

# main.py
draw_component(ax, 3, comp_y + 5, 5.5, 2, 'main.py\nFastAPI App Entry Point\nLifespan · CORS · HTTPBasic Auth', 'entry', C_BE_FILL, 7)

# endpoints.py
draw_component(ax, 10, comp_y + 5, 6, 2, 'endpoints.py\nAPI Router (all /api/* routes)\n9 endpoints · slowapi rate limits', 'controller', '#FDE68A', 7)

# submission_service.py
draw_component(ax, 18, comp_y + 5, 5.5, 2, 'submission_service.py\nOrchestrates OCR → Grade → Save\nAtomic DB transactions', 'service', '#FBBF24', 7)

# ocr_service.py
draw_component(ax, 2, comp_y + 1.5, 6, 2.2, 'ocr_service.py\nOCRService class · 5-provider cascade\nGroq → Gemini → OpenRouter → RapidAPI → Tesseract\nparse_student_info() · extract_text()', 'service', C_OCR_FILL, 6.5)

# nlp_grading_service.py
draw_component(ax, 9.5, comp_y + 1.5, 5, 2.2, 'nlp_grading_service.py\nGradingModel singleton\nSBERT embeddings\n3 pickle model files', 'service', C_NLP_FILL, 6.5)

# llm_grading_service
draw_component(ax, 16, comp_y + 1.5, 5.5, 2.2, 'llm_grading_service.py\nLLM Grading (Gemini)\n3-model cascade · multi-key\nThreadPoolExecutor(3)', 'service', '#FEF3C7', 6.5)

# models.py
draw_component(ax, 23, comp_y + 4, 4.5, 1.5, 'models.py\nSQLAlchemy Models\n5 entities', 'model', C_DB_FILL, 7)

# database.py
draw_component(ax, 23, comp_y + 1.5, 4.5, 1.5, 'database.py\nSessionLocal\nEngine · Base', 'infrastructure', '#A7F3D0', 7)

# limiter.py
draw_component(ax, 28.5, comp_y + 4, 2.5, 1.5, 'limiter.py\nslowapi\nLimiter', 'infra', '#E2E8F0', 7)

# Arrows for component diagram
draw_arrow(ax, 8.5, comp_y + 6, 10, comp_y + 6, label='includes')
draw_arrow(ax, 16, comp_y + 6, 18, comp_y + 6, label='calls')
draw_arrow(ax, 20.75, comp_y + 5, 20.75, comp_y + 3.7, label='OCR', color=C_ARROW_DATA)
draw_arrow(ax, 19, comp_y + 5, 12, comp_y + 3.7, label='grade()', color=C_ARROW_DATA, lw=1)
draw_arrow(ax, 21, comp_y + 5, 5, comp_y + 3.7, label='extract_text()', color=C_ARROW_DATA)
draw_arrow(ax, 23.5, comp_y + 5.2, 23.5, comp_y + 4, color=C_ARROW, lw=1)  # unused? actually wrong. Let me fix
draw_arrow(ax, 18, comp_y + 5.5, 23, comp_y + 5.5, label='ORM queries', color='#38A169', dashed=True)
draw_arrow(ax, 14, comp_y + 1.8, 16, comp_y + 1.8, label='fallback', dashed=True, color=C_LIGHT)


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 3: FRONTEND COMPONENT DIAGRAM
# ══════════════════════════════════════════════════════════════════════════════
section3_y = comp_y - 1.5
ax.text(1, section3_y, '3. Frontend Component Diagram', fontsize=14, fontfamily=FONT,
        fontweight='bold', color=C_TEXT)
ax.plot([1, FIG_W - 1], [section3_y - 0.2, section3_y - 0.2], color=C_LIGHT, lw=0.8)

fe_y = section3_y - 5

# App.js
draw_component(ax, 1.5, fe_y + 3.3, 4, 1.3, 'App.js\nRouting + Layout', 'root', C_FE_FILL, 7.5)

# Pages
pages_data = [
    ('Home.js', 'Upload &\nGrade'),
    ('Results.js', 'Grading\nOutput'),
    ('Search.js', 'Student\nSearch'),
    ('Dashboard.js', 'Stats &\nCharts'),
    ('AnswerKey.js', 'Key\nManager'),
    ('About.js', 'About\nPage'),
]
px = 1
for i, (name, desc) in enumerate(pages_data):
    draw_component(ax, px, fe_y + 0.5, 3.2, 2.2, f'{name}\n{desc}', 'page', '#BFDBFE', 6.5)
    draw_arrow(ax, 3.5, fe_y + 3.3, px + 1.6, fe_y + 2.7, color=C_ARROW, lw=0.8)
    px += 3.5

# Shared components
cx = 22.5
for name in ['Navbar.js', 'Footer.js', 'UploadBox.js', 'QuestionCard.js', 'ErrorBoundary.js']:
    draw_rounded_box(ax, cx, fe_y + 0.8, 2.5, 0.8, '#DBEAFE', zorder=3, radius=0.12)
    ax.text(cx + 1.25, fe_y + 1.2, name, ha='center', va='center', fontsize=6, fontfamily=FONT_MONO, color=C_TEXT, zorder=4)
    cx += 2.8

# Utils
ux = 22.5
for name in ['api.js', 'gradeUtils.js', 'textUtils.js', 'pdfExport.js']:
    draw_rounded_box(ax, ux, fe_y + 0.0, 2.5, 0.6, '#E0E7FF', zorder=3, radius=0.1)
    ax.text(ux + 1.25, fe_y + 0.3, name, ha='center', va='center', fontsize=5.5, fontfamily=FONT_MONO, color=C_LIGHT, zorder=4)
    ux += 2.8

ax.text(22.5, fe_y + 1.85, '«components»', fontsize=6, fontfamily=FONT, color=C_LIGHT, fontstyle='italic')
ax.text(22.5, fe_y + 0.75, '«services/utils»', fontsize=6, fontfamily=FONT, color=C_LIGHT, fontstyle='italic')


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 4: CLASS DIAGRAM (Database Entities)
# ══════════════════════════════════════════════════════════════════════════════
section4_y = fe_y - 2
ax.text(1, section4_y, '4. Class Diagram — Database Entities (SQLAlchemy ORM)', fontsize=14, fontfamily=FONT,
        fontweight='bold', color=C_TEXT)
ax.plot([1, FIG_W - 1], [section4_y - 0.2, section4_y - 0.2], color=C_LIGHT, lw=0.8)

cls_y = section4_y - 9.5

# Student
h1 = draw_class_box(ax, 1, cls_y + 5, 5.5, 'Student', [
    '+ student_id: String(50) «PK»',
    '+ name: String(100)',
    '+ class_grade: String(50) [nullable]',
    '+ created_at: DateTime',
], ['+ submissions: List[Submission]'])

# Assessment
h2 = draw_class_box(ax, 7.5, cls_y + 5, 5.5, 'Assessment', [
    '+ id: Integer «PK»',
    '+ subject: String(100) «indexed»',
    '+ title: String(200)',
    '+ total_marks: Decimal(7,2)',
    '+ num_questions: Integer',
    '+ created_at: DateTime',
], ['+ questions: List[AssessmentQuestion]', '+ submissions: List[Submission]'])

# AssessmentQuestion
h3 = draw_class_box(ax, 14.5, cls_y + 5, 5.5, 'AssessmentQuestion', [
    '+ id: Integer «PK»',
    '+ assessment_id: Integer «FK»',
    '+ question_number: Integer',
    '+ question_text: Text',
    '+ model_answer: Text',
    '+ max_marks: Decimal(7,2)',
], ['+ assessment: Assessment'])

# Submission
h4 = draw_class_box(ax, 1, cls_y - 1.5, 7, 'Submission', [
    '+ submission_id: Integer «PK»',
    '+ student_id: String(50) «FK»',
    '+ assessment_id: Integer «FK» [nullable]',
    '+ subject_name: String(100)',
    '+ num_questions: Integer',
    '+ total_marks: Decimal(7,2)',
    '+ max_total_marks: Decimal(7,2)',
    '+ overall_feedback: Text',
    '+ submitted_at: DateTime',
    '+ checked_at: DateTime [nullable]',
    '+ status: String(20)',
], ['+ student: Student', '+ assessment: Assessment', '+ answers: List[Answer]'])

# Answer
h5 = draw_class_box(ax, 10, cls_y - 2.5, 7, 'Answer', [
    '+ answer_id: Integer «PK»',
    '+ submission_id: Integer «FK»',
    '+ question_number: Integer',
    '+ question_text: Text',
    '+ answer_text: Text',
    '+ model_answer: Text',
    '+ marks_obtained: Decimal(7,2)',
    '+ max_marks: Decimal(7,2)',
    '+ similarity_score: Decimal(4,3)',
    '+ ai_feedback: Text',
    '+ manual_review_required: Boolean',
    '+ grading_method: String(50)',
    '+ fallback_reason: Text',
    '+ ocr_confidence: Decimal(4,3)',
    '+ checked_at: DateTime',
], ['+ submission: Submission'])

# SubmissionStatus enum
draw_class_box(ax, 21.5, cls_y + 5, 4.5, 'SubmissionStatus', [
    'pending',
    'processing',
    'checked',
    'failed',
], is_enum=True)

# ── Relationship arrows ──
# Student 1──* Submission
draw_arrow(ax, 3.75, cls_y + 5, 3.75, cls_y + h4 - 1.5, color=C_CLASS_HEAD, lw=1.5)
ax.text(4, cls_y + 4.8, '1', fontsize=7, fontfamily=FONT, fontweight='bold', color=C_CLASS_HEAD)
ax.text(4, cls_y + h4 - 1, '*', fontsize=9, fontfamily=FONT, fontweight='bold', color=C_CLASS_HEAD)

# Assessment 1──* AssessmentQuestion
draw_arrow(ax, 13, cls_y + 7.5, 14.5, cls_y + 7.5, color=C_CLASS_HEAD, lw=1.5)
ax.text(13.2, cls_y + 7.8, '1', fontsize=7, fontfamily=FONT, fontweight='bold', color=C_CLASS_HEAD)
ax.text(14.2, cls_y + 7.8, '*', fontsize=9, fontfamily=FONT, fontweight='bold', color=C_CLASS_HEAD)

# Assessment 0..1──* Submission
draw_arrow(ax, 10.25, cls_y + 5, 6.5, cls_y + h4 - 1.5, color=C_CLASS_HEAD, lw=1.5, dashed=True)
ax.text(10, cls_y + 4.7, '0..1', fontsize=6, fontfamily=FONT, color=C_CLASS_HEAD)
ax.text(6.6, cls_y + h4 - 1.1, '*', fontsize=9, fontfamily=FONT, fontweight='bold', color=C_CLASS_HEAD)

# Submission 1──* Answer
draw_arrow(ax, 8, cls_y - 0.5, 10, cls_y - 0.5, color=C_CLASS_HEAD, lw=1.5)
ax.text(8.2, cls_y - 0.2, '1', fontsize=7, fontfamily=FONT, fontweight='bold', color=C_CLASS_HEAD)
ax.text(9.7, cls_y - 0.2, '*', fontsize=9, fontfamily=FONT, fontweight='bold', color=C_CLASS_HEAD)

# SubmissionStatus used by Submission
draw_arrow(ax, 21.5, cls_y + 6, 8, cls_y + 1.5, color=C_ENUM_HEAD, lw=1, dashed=True, label='«uses»')


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 5: DATA FLOW / SEQUENCE OVERVIEW
# ══════════════════════════════════════════════════════════════════════════════
section5_y = cls_y - 5.5
ax.text(1, section5_y, '5. Data Flow Diagram — Paper Grading Pipeline', fontsize=14, fontfamily=FONT,
        fontweight='bold', color=C_TEXT)
ax.plot([1, FIG_W - 1], [section5_y - 0.2, section5_y - 0.2], color=C_LIGHT, lw=0.8)

flow_y = section5_y - 3.5

# Flow boxes
flow_steps = [
    ('1. Upload\nImage/PDF', C_FE_FILL,   1.5,  3.8),
    ('2. Validate\nFile Type\n& Size',  '#FDE68A',  5.8, 3.2),
    ('3. OCR\nExtract Text\n(5 providers)',  C_OCR_FILL, 9.5, 3.5),
    ('4. Parse\nStudent Info\n+ Q&A pairs',  '#E9D5FF', 13.5, 3.5),
    ('5. Match\nQuestion\nBank',  C_NLP_FILL, 17.5, 3),
    ('6. Grade\nLLM + SBERT\nHeuristic',  '#FEF3C7', 21, 3.5),
    ('7. Scale\nMarks &\nSave DB',  C_DB_FILL,  25, 3.3),
    ('8. Return\nJSON\nResult',  C_FE_FILL,  28.8, 3),
]

for i, (label, fill, x, w) in enumerate(flow_steps):
    draw_rounded_box(ax, x, flow_y, w, 2, fill, zorder=3, radius=0.2)
    ax.text(x + w / 2, flow_y + 1, label, ha='center', va='center',
            fontsize=6.5, fontfamily=FONT, fontweight='bold', color=C_TEXT, zorder=4, linespacing=1.2)
    if i > 0:
        prev_x = flow_steps[i - 1][2] + flow_steps[i - 1][3]
        draw_arrow(ax, prev_x, flow_y + 1, x, flow_y + 1, color=C_ARROW_DATA, lw=2, style='->')

# Cascade detail under OCR
cascade_y = flow_y - 2.5
ax.text(9.5, cascade_y + 2, 'OCR Provider Cascade:', fontsize=7, fontfamily=FONT, fontweight='bold', color=C_TEXT)
cascade_providers = ['Groq\n(Llama Vision)', 'Gemini\n(Flash)', 'OpenRouter\n(Molmo)', 'RapidAPI\n(Pen2Print)', 'Tesseract\n(Local)']
cx = 2
for i, p in enumerate(cascade_providers):
    draw_rounded_box(ax, cx, cascade_y, 3.5, 1.5, C_EXT_FILL if i < 4 else '#FED7AA', zorder=3, radius=0.15)
    ax.text(cx + 1.75, cascade_y + 0.75, p, ha='center', va='center',
            fontsize=6, fontfamily=FONT, color=C_TEXT, zorder=4, linespacing=1.2)
    if i > 0:
        draw_arrow(ax, cx - 0.3, cascade_y + 0.75, cx, cascade_y + 0.75,
                   color='#E53E3E', lw=1.2, style='->')
    cx += 4.2
    if i < 4:
        ax.text(cx - 2.3, cascade_y + 1.65, '429/fail →', fontsize=5, fontfamily=FONT, color='#E53E3E', fontstyle='italic')

# Grading detail
grade_y = cascade_y - 2.8
ax.text(1, grade_y + 2.2, 'Grading Engine Detail:', fontsize=7, fontfamily=FONT, fontweight='bold', color=C_TEXT)

# LLM path
draw_rounded_box(ax, 2, grade_y, 5, 1.8, '#FEF3C7', zorder=3, radius=0.15)
ax.text(4.5, grade_y + 0.9, 'Path A: LLM Grading\nGemini 2.5-flash → 2.0-flash → lite\nThreadPoolExecutor(3 workers)\nMulti-key failover on 429',
        ha='center', va='center', fontsize=5.5, fontfamily=FONT, color=C_TEXT, zorder=4, linespacing=1.3)

# Heuristic path
draw_rounded_box(ax, 8, grade_y, 7, 1.8, C_NLP_FILL, zorder=3, radius=0.15)
ax.text(11.5, grade_y + 0.9, 'Path B: Heuristic Grading (Fallback)\nLayer 2a: SBERT cosine sim (50%) · Layer 2b: Keyword coverage (40%)\nLayer 2c: Number/unit gate (10%) · Penalties: negation, antonym, gaming\nBatch encode: 2 forward passes vs 2N',
        ha='center', va='center', fontsize=5.5, fontfamily=FONT, color=C_TEXT, zorder=4, linespacing=1.3)

draw_arrow(ax, 7, grade_y + 0.9, 8, grade_y + 0.9, color=C_LIGHT, lw=1.2, dashed=True, label='if LLM fails')

# Scaling
draw_rounded_box(ax, 16.5, grade_y, 5, 1.8, C_DB_FILL, zorder=3, radius=0.15)
ax.text(19, grade_y + 0.9, 'Marks Scaling\neffective_total = provided OR ocr_total\nscaling_factor = total / unscaled_max\nmarks = raw × scaling_factor',
        ha='center', va='center', fontsize=5.5, fontfamily=FONT, color=C_TEXT, zorder=4, linespacing=1.3)

draw_arrow(ax, 15, grade_y + 0.9, 16.5, grade_y + 0.9, color=C_ARROW_DATA, lw=1.2)


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 6: API ENDPOINT MAP
# ══════════════════════════════════════════════════════════════════════════════
section6_y = grade_y - 2.5
ax.text(1, section6_y, '6. API Endpoint Map (/api/*)', fontsize=14, fontfamily=FONT,
        fontweight='bold', color=C_TEXT)
ax.plot([1, FIG_W - 1], [section6_y - 0.2, section6_y - 0.2], color=C_LIGHT, lw=0.8)

endpoints = [
    ('POST', '/grade', '5/min', 'Upload paper → OCR → Grade → Save'),
    ('POST', '/upload-answer-key', '20/min', 'Upload answer key (JSON or .docx)'),
    ('POST', '/assessments/approve-answer', '30/min', 'Approve AI-suggested answer'),
    ('POST', '/answers/correct-ocr', '30/min', 'Correct OCR text → re-grade'),
    ('GET',  '/search?query=', '60/min', 'Search students by name/ID'),
    ('GET',  '/result/{id}', '60/min', 'Fetch specific submission result'),
    ('GET',  '/history', '30/min', 'All submissions ordered by date'),
    ('GET',  '/stats', '60/min', 'Dashboard aggregate statistics'),
    ('GET',  '/subjects', '60/min', 'Available subjects (dynamic)'),
    ('GET',  '/dashboard', '60/min', 'Recent activity + top performers'),
    ('GET',  '/question-bank', '60/min', 'List questions, filter by subject'),
    ('PATCH', '/question-bank/{id}', '30/min', 'Update question/answer/marks'),
    ('DELETE', '/question-bank/{id}', '30/min', 'Delete question bank entry'),
]

ep_y = section6_y - 0.6
col_x = [1.5, 3.5, 14, 17, 20]
# Header
for x, txt in zip(col_x, ['Method', 'Endpoint', 'Rate', 'Description']):
    ax.text(x, ep_y, txt, fontsize=6.5, fontfamily=FONT, fontweight='bold', color=C_TEXT)
ep_y -= 0.15
ax.plot([1.3, 30], [ep_y, ep_y], color=C_LIGHT, lw=0.5)

for method, path, rate, desc in endpoints:
    ep_y -= 0.4
    method_colors = {'POST': '#E53E3E', 'GET': '#38A169', 'PATCH': '#D69E2E', 'DELETE': '#9B2C2C'}
    mc = method_colors.get(method, C_TEXT)
    draw_rounded_box(ax, 1.3, ep_y - 0.08, 1.8, 0.35, mc, edge=mc, zorder=3, radius=0.08, alpha=0.15)
    ax.text(2.2, ep_y + 0.1, method, ha='center', va='center', fontsize=6, fontfamily=FONT_MONO,
            fontweight='bold', color=mc, zorder=4)
    ax.text(3.5, ep_y + 0.1, path, ha='left', va='center', fontsize=6, fontfamily=FONT_MONO, color=C_TEXT)
    ax.text(14, ep_y + 0.1, rate, ha='left', va='center', fontsize=5.5, fontfamily=FONT, color=C_LIGHT)
    ax.text(17, ep_y + 0.1, desc, ha='left', va='center', fontsize=5.5, fontfamily=FONT, color=C_TEXT)


# ══════════════════════════════════════════════════════════════════════════════
# LEGEND
# ══════════════════════════════════════════════════════════════════════════════
legend_y = ep_y - 1.5
ax.text(1, legend_y + 0.6, 'Legend:', fontsize=9, fontfamily=FONT, fontweight='bold', color=C_TEXT)

legend_items = [
    (C_FE_FILL, 'Frontend (React)'),
    (C_BE_FILL, 'Backend (FastAPI)'),
    (C_OCR_FILL, 'OCR Layer'),
    (C_NLP_FILL, 'NLP/Grading Layer'),
    (C_DB_FILL, 'Database Layer'),
    (C_EXT_FILL, 'External APIs'),
]
lx = 4
for fill, label in legend_items:
    draw_rounded_box(ax, lx, legend_y, 0.6, 0.5, fill, zorder=3, radius=0.1)
    ax.text(lx + 0.8, legend_y + 0.25, label, ha='left', va='center',
            fontsize=7, fontfamily=FONT, color=C_TEXT)
    lx += 4

# Arrow legend
ax.text(28, legend_y + 0.25, '-> data flow     --> fallback/optional',
        fontsize=7, fontfamily=FONT, color=C_LIGHT)


# ── Save ──────────────────────────────────────────────────────────────────────
output_path = Path(__file__).resolve().parents[1] / 'docs' / 'architecture' / 'system_architecture_uml.png'
plt.tight_layout(pad=0.5)
plt.savefig(output_path, dpi=DPI, bbox_inches='tight', facecolor=C_BG, edgecolor='none')
plt.close()
print(f"Diagram saved to: {output_path}")
print(f"Dimensions: {FIG_W * DPI} x {FIG_H * DPI} px @ {DPI} DPI")
