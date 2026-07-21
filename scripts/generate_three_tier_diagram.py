"""
FairMark — Three-Tier Software Architecture Diagram
UML 2.5 / IEEE Std 1016-2009 compliant, academic-paper quality.

Renders a clean, single-focus three-tier architecture:
    Tier 1  Presentation Tier   — React SPA (browser client)
    Tier 2  Application Tier     — FastAPI application server (OCR, NLP/LLM grading)
    Tier 3  Data Tier            — PostgreSQL relational database
plus the external OCR / LLM providers consumed by the application tier.

Output: FairMark_Three_Tier_Architecture.png
"""

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Rectangle, Ellipse, FancyArrowPatch

# ── Canvas ────────────────────────────────────────────────────────────────────
DPI = 300
FIG_W, FIG_H = 13.5, 16.5

# ── Palette (muted, print-friendly) ────────────────────────────────────────────
C_BG        = '#FFFFFF'
C_BORDER    = '#1F2933'
C_TEXT      = '#1F2933'
C_SUBTLE    = '#52606D'

C_TIER1_BAND = '#E8F1FB'   # presentation – blue
C_TIER1_HEAD = '#2563A8'
C_TIER1_NODE = '#FFFFFF'

C_TIER2_BAND = '#FFF6E5'   # application – amber
C_TIER2_HEAD = '#B5751B'
C_TIER2_NODE = '#FFFFFF'

C_TIER3_BAND = '#E7F6EC'   # data – green
C_TIER3_HEAD = '#2F855A'
C_TIER3_NODE = '#FFFFFF'

C_EXT_BAND   = '#FDECEC'   # external – red
C_EXT_HEAD   = '#B43A3A'

C_OCR        = '#EEE9FB'   # purple accent
C_NLP        = '#FBE9F2'   # pink accent

C_ARROW      = '#3A4750'
C_ARROW_DATA = '#2563A8'

FONT = 'DejaVu Sans'
MONO = 'DejaVu Sans Mono'


# ── Primitives ──────────────────────────────────────────────────────────────--
def rbox(ax, x, y, w, h, fill, edge=C_BORDER, lw=1.4, r=0.10, z=2, alpha=1.0):
    p = FancyBboxPatch((x, y), w, h,
                       boxstyle=f"round,pad=0,rounding_size={r}",
                       facecolor=fill, edgecolor=edge, linewidth=lw, alpha=alpha, zorder=z)
    ax.add_patch(p)
    return p


def label(ax, x, y, text, size=9, weight='normal', color=C_TEXT, ha='center',
          va='center', z=5, family=FONT, style='normal', ls=1.25):
    ax.text(x, y, text, ha=ha, va=va, fontsize=size, fontweight=weight, color=color,
            zorder=z, fontfamily=family, fontstyle=style, linespacing=ls)


def node(ax, x, y, w, h, title, sub='', stereo='', fill='#FFFFFF',
         accent=C_BORDER, tsize=8.5, ssize=6.8):
    """A UML component / artifact node with optional stereotype + subtitle."""
    rbox(ax, x, y, w, h, fill, edge=accent, lw=1.3, r=0.09, z=4)
    # component icon (two notched rects, top-left)
    ix, iy = x + 0.13, y + h - 0.28
    for dy in (0.0, -0.20):
        ax.add_patch(Rectangle((ix, iy + dy), 0.20, 0.13, facecolor='white',
                               edgecolor=accent, linewidth=0.8, zorder=6))
    cy = y + h / 2
    if stereo:
        label(ax, x + w / 2, y + h - 0.22, stereo, size=ssize - 0.6,
              color=C_SUBTLE, style='italic', z=7)
        cy -= 0.06
    label(ax, x + w / 2, cy + (0.16 if sub else 0), title, size=tsize,
          weight='bold', z=7)
    if sub:
        label(ax, x + w / 2, cy - 0.22, sub, size=ssize, color=C_SUBTLE, z=7)


def cylinder(ax, x, y, w, h, fill, edge=C_BORDER):
    eh = h * 0.16
    ax.add_patch(Rectangle((x, y), w, h - eh / 2, facecolor=fill, edgecolor=edge,
                           linewidth=1.4, zorder=4))
    ax.add_patch(Ellipse((x + w / 2, y + h - eh / 2), w, eh, facecolor=fill,
                         edgecolor=edge, linewidth=1.4, zorder=5))
    ax.add_patch(Ellipse((x + w / 2, y), w, eh, facecolor=fill, edgecolor=edge,
                         linewidth=1.4, zorder=4))
    # hide the rectangle's top edge line under the ellipse
    ax.plot([x, x + w], [y + h - eh / 2, y + h - eh / 2], color=fill, lw=1.6, zorder=4.5)


def conn(ax, p1, p2, color=C_ARROW, lw=1.6, style='-|>', dashed=False, z=9,
         rad=0.0, mut=14):
    ls = (0, (5, 3)) if dashed else 'solid'
    a = FancyArrowPatch(p1, p2, arrowstyle=style, mutation_scale=mut,
                        color=color, lw=lw, linestyle=ls, zorder=z,
                        connectionstyle=f"arc3,rad={rad}",
                        shrinkA=2, shrinkB=2)
    ax.add_patch(a)


def conn_label(ax, x, y, text, color=C_ARROW, size=7.0, z=11):
    ax.text(x, y, text, ha='center', va='center', fontsize=size, color=color,
            fontfamily=FONT, fontweight='bold', zorder=z,
            bbox=dict(boxstyle='round,pad=0.28', facecolor='white',
                      edgecolor=color, linewidth=0.9, alpha=0.96))


# ── Figure ──────────────────────────────────────────────────────────────────--
fig, ax = plt.subplots(figsize=(FIG_W, FIG_H), dpi=DPI)
ax.set_xlim(0, 100)
ax.set_ylim(0, 122)
ax.axis('off')
fig.patch.set_facecolor(C_BG)
ax.set_facecolor(C_BG)

# ── Title block ─────────────────────────────────────────────────────────────--
rbox(ax, 2, 114.5, 96, 6.0, '#11212B', r=0.25, z=2)
label(ax, 50, 118.6, 'FairMark — AI-Based Paper Checking System', size=17,
      weight='bold', color='white', z=3)
label(ax, 50, 116.0, 'Three-Tier Software Architecture  ·  UML 2.5 / IEEE Std 1016-2009',
      size=9.5, color='#9AA5B1', z=3)

# Geometry of tier bands
LX, RX = 3, 75          # left/right extent of the three main tier bands
BW = RX - LX            # band width
EXT_X = 78              # external-services column
EXT_W = 19

# ════════════════════════════════════════════════════════════════════════════
# TIER 1 — PRESENTATION
# ════════════════════════════════════════════════════════════════════════════
t1_y, t1_h = 92.5, 18.5
rbox(ax, LX, t1_y, BW, t1_h, C_TIER1_BAND, edge=C_TIER1_HEAD, lw=1.6, r=0.2, z=1)
rbox(ax, LX, t1_y + t1_h - 2.4, BW, 2.4, C_TIER1_HEAD, edge=C_TIER1_HEAD, r=0.2, z=2)
label(ax, LX + 1.2, t1_y + t1_h - 1.2, '«presentation tier»', size=7.6,
      color='#D6E4F0', ha='left', style='italic', z=3)
label(ax, LX + BW / 2, t1_y + t1_h - 1.2, 'TIER 1 — CLIENT  (Web Browser)',
      size=10.5, weight='bold', color='white', z=3)
label(ax, RX - 1.2, t1_y + t1_h - 1.2, 'React SPA · localhost:3000', size=7.6,
      color='#D6E4F0', ha='right', z=3)

node(ax, LX + 2.5, t1_y + 7.6, 18, 6.0, 'React SPA',
     'App.js · React Router (BrowserRouter)', '«user interface»',
     fill=C_TIER1_NODE, accent=C_TIER1_HEAD, tsize=9.5)
# pages row
pages = ['Home\n(Upload)', 'Results', 'Search', 'Dashboard', 'AnswerKey']
pw = 11.6
px = LX + 2.5
for i, pg in enumerate(pages):
    rbox(ax, px, t1_y + 2.0, pw, 4.2, '#F4F9FF', edge=C_TIER1_HEAD, lw=1.0, r=0.08, z=4)
    label(ax, px + pw / 2, t1_y + 4.1, pg, size=7.2, weight='bold', z=6)
    px += pw + 1.4
node(ax, RX - 22.5, t1_y + 7.6, 20, 6.0, 'api.js  ·  Service Layer',
     'fetch() REST client · jsPDF export', '«gateway»',
     fill=C_TIER1_NODE, accent=C_TIER1_HEAD, tsize=9)

# ════════════════════════════════════════════════════════════════════════════
# TIER 2 — APPLICATION / BUSINESS LOGIC
# ════════════════════════════════════════════════════════════════════════════
t2_y, t2_h = 47, 40
rbox(ax, LX, t2_y, BW, t2_h, C_TIER2_BAND, edge=C_TIER2_HEAD, lw=1.6, r=0.2, z=1)
rbox(ax, LX, t2_y + t2_h - 2.4, BW, 2.4, C_TIER2_HEAD, edge=C_TIER2_HEAD, r=0.2, z=2)
label(ax, LX + 1.2, t2_y + t2_h - 1.2, '«application tier»', size=7.6,
      color='#FBEAD0', ha='left', style='italic', z=3)
label(ax, LX + BW / 2, t2_y + t2_h - 1.2,
      'TIER 2 — APPLICATION SERVER  (FastAPI / Uvicorn :8000)',
      size=10.5, weight='bold', color='white', z=3)
label(ax, RX - 1.2, t2_y + t2_h - 1.2, 'Python', size=7.6, color='#FBEAD0',
      ha='right', z=3)

# API gateway / router
node(ax, LX + 3, t2_y + 30.5, 30, 5.4, 'API Router  (endpoints.py)',
     'REST /api/* · 14 routes · CORS · HTTP Basic Auth · slowapi rate-limit',
     '«controller»', fill='#FFFDF7', accent=C_TIER2_HEAD, tsize=9, ssize=6.4)

# Submission orchestrator
node(ax, RX - 33, t2_y + 30.5, 30, 5.4, 'Submission Service',
     'process_grading_submission() · orchestrates pipeline · atomic DB txn',
     '«orchestrator»', fill='#FFFDF7', accent=C_TIER2_HEAD, tsize=9, ssize=6.4)

# Pipeline label
label(ax, LX + BW / 2, t2_y + 27.0, 'Business-Logic Services',
      size=8.2, weight='bold', color=C_SUBTLE, z=5)

def titled_box(ax, x, y, w, h, title, stereo, fill, accent, lines):
    """Service box with a header strip and left-aligned detail lines."""
    rbox(ax, x, y, w, h, fill, edge=accent, lw=1.4, r=0.09, z=4)
    rbox(ax, x, y + h - 2.0, w, 2.0, accent, edge=accent, lw=1.4, r=0.09, z=5)
    label(ax, x + w / 2, y + h - 0.75, title, size=9.5, weight='bold',
          color='white', z=7)
    label(ax, x + w / 2, y + h - 1.55, stereo, size=6.2, color='#F3EEFB',
          style='italic', z=7)
    ly0 = y + h - 3.0
    for txt, kw in lines:
        label(ax, x + 1.0, ly0, txt, ha='left', z=7, **kw)
        ly0 -= 1.65

# OCR service
titled_box(ax, LX + 3, t2_y + 14.5, 31, 9.5, 'OCR Service', '«service» · ocr_service.py',
           C_OCR, '#6D4FC0', [
    ('5-provider cascade (failover on 429 / error):',
     dict(size=6.7, color=C_SUBTLE)),
    ('Groq → Gemini → OpenRouter → RapidAPI → Tesseract',
     dict(size=6.7, weight='bold', color='#4B3B91', family=MONO)),
    ('extract_text() → student info + Q&A pairs',
     dict(size=6.6, color=C_SUBTLE)),
])

# Grading service
titled_box(ax, RX - 34, t2_y + 14.5, 31, 9.5, 'Grading Engine',
           '«service» · nlp_grading_service.py', C_NLP, '#B43A78', [
    ('Path A — LLM grading (Gemini cascade)',
     dict(size=6.7, weight='bold', color='#8A2B5C')),
    ('Path B — SBERT cosine + keyword (fallback)',
     dict(size=6.7, color=C_SUBTLE)),
    ('grade_answer() · marks scaling',
     dict(size=6.6, color=C_SUBTLE)),
])

# ORM / persistence layer (spans bottom of tier 2)
node(ax, LX + 3, t2_y + 2.0, BW - 6, 5.4, 'SQLAlchemy ORM  +  Alembic',
     'database.py — SessionLocal · Engine · declarative models · migrations',
     '«data access»', fill='#FFFDF7', accent=C_TIER2_HEAD, tsize=9, ssize=6.4)

# intra-tier connectors
conn(ax, (LX + 33, t2_y + 33.2), (RX - 33, t2_y + 33.2), color=C_ARROW, lw=1.4, style='-|>')
conn_label(ax, LX + BW / 2, t2_y + 33.2, 'invoke', size=6.4)
conn(ax, (LX + 14, t2_y + 30.5), (LX + 16, t2_y + 24.0), color=C_ARROW, lw=1.3, style='-|>', rad=0.0)
conn(ax, (RX - 18, t2_y + 30.5), (RX - 18, t2_y + 24.0), color=C_ARROW, lw=1.3, style='-|>')
conn_label(ax, LX + 16.5, t2_y + 27.3, '1. OCR', size=6.2, color=C_SUBTLE)
conn_label(ax, RX - 18, t2_y + 27.3, '2. grade', size=6.2, color=C_SUBTLE)
conn(ax, (LX + BW / 2, t2_y + 14.5), (LX + BW / 2, t2_y + 7.4), color=C_ARROW, lw=1.3, style='-|>')
conn_label(ax, LX + BW / 2, t2_y + 11.0, '3. persist', size=6.2, color=C_SUBTLE)

# ════════════════════════════════════════════════════════════════════════════
# TIER 3 — DATA
# ════════════════════════════════════════════════════════════════════════════
t3_y, t3_h = 24, 20
rbox(ax, LX, t3_y, BW, t3_h, C_TIER3_BAND, edge=C_TIER3_HEAD, lw=1.6, r=0.2, z=1)
rbox(ax, LX, t3_y + t3_h - 2.4, BW, 2.4, C_TIER3_HEAD, edge=C_TIER3_HEAD, r=0.2, z=2)
label(ax, LX + 1.2, t3_y + t3_h - 1.2, '«data tier»', size=7.6, color='#D2EFDD',
      ha='left', style='italic', z=3)
label(ax, LX + BW / 2, t3_y + t3_h - 1.2,
      'TIER 3 — DATABASE SERVER  (PostgreSQL · FairMark_db)',
      size=10.5, weight='bold', color='white', z=3)

# DB cylinder
cylinder(ax, LX + 3, t3_y + 3.2, 14, 11.5, C_TIER3_BAND, edge=C_TIER3_HEAD)
label(ax, LX + 10, t3_y + 9.0, 'PostgreSQL', size=9.5, weight='bold',
      color=C_TIER3_HEAD, z=6)
label(ax, LX + 10, t3_y + 7.0, 'FairMark_db', size=7.5, color=C_SUBTLE, z=6, family=MONO)

# entity tables
entities = [
    ('students', 'student_id PK · name · class_grade'),
    ('assessments', 'id PK · subject · total_marks'),
    ('assessment_questions', 'id PK · assessment_id FK · model_answer'),
    ('submissions', 'submission_id PK · student_id FK · status'),
    ('answers', 'answer_id PK · submission_id FK · marks · sim_score'),
]
ex = LX + 22
ew = BW - 22 - 1.5
eh = 2.55
ey = t3_y + 14.2
label(ax, ex + ew / 2, ey + 1.2, 'Relational Schema  «entities»', size=7.6,
      weight='bold', color=C_SUBTLE, z=6)
for i, (tname, cols) in enumerate(entities):
    yy = ey - i * (eh + 0.25)
    rbox(ax, ex, yy - eh, ew, eh, '#FFFFFF', edge=C_TIER3_HEAD, lw=1.0, r=0.06, z=5)
    rbox(ax, ex, yy - 0.95, ew, 0.95, '#DBF1E3', edge=C_TIER3_HEAD, lw=1.0, r=0.06, z=6)
    label(ax, ex + 0.5, yy - 0.48, tname, size=7.4, weight='bold', ha='left',
          z=7, family=MONO)
    label(ax, ex + 0.5, yy - 1.75, cols, size=6.0, ha='left', color=C_SUBTLE, z=7,
          family=MONO)
# 1..* relationship hints between cylinder and tables
conn(ax, (LX + 17, t3_y + 8.5), (ex, ey - 1.2), color=C_TIER3_HEAD, lw=1.1,
     style='-|>', rad=-0.1)

# ════════════════════════════════════════════════════════════════════════════
# EXTERNAL SERVICES (consumed by Tier 2)
# ════════════════════════════════════════════════════════════════════════════
ex_y, ex_h = 47, 40
rbox(ax, EXT_X, ex_y, EXT_W, ex_h, C_EXT_BAND, edge=C_EXT_HEAD, lw=1.5, r=0.2, z=1)
rbox(ax, EXT_X, ex_y + ex_h - 4.2, EXT_W, 4.2, C_EXT_HEAD, edge=C_EXT_HEAD, r=0.2, z=2)
label(ax, EXT_X + EXT_W / 2, ex_y + ex_h - 1.6, 'EXTERNAL', size=9.5,
      weight='bold', color='white', z=3)
label(ax, EXT_X + EXT_W / 2, ex_y + ex_h - 3.0, '«external systems»', size=6.8,
      color='#F6D5D5', style='italic', z=3)

ext_items = [
    ('Groq', 'Llama Vision OCR'),
    ('Google Gemini', 'Vision OCR + LLM grade'),
    ('OpenRouter', 'Molmo vision'),
    ('RapidAPI', 'Pen-to-Print / OCR'),
    ('Tesseract', 'local OCR fallback'),
]
iy = ex_y + ex_h - 9.5
for nm, ds in ext_items:
    rbox(ax, EXT_X + 1.5, iy, EXT_W - 3, 5.0, '#FFFFFF', edge=C_EXT_HEAD, lw=1.0, r=0.1, z=4)
    label(ax, EXT_X + EXT_W / 2, iy + 3.2, nm, size=8, weight='bold', color='#8E2E2E', z=6)
    label(ax, EXT_X + EXT_W / 2, iy + 1.5, ds, size=6.0, color=C_SUBTLE, z=6)
    iy -= 6.2

# ════════════════════════════════════════════════════════════════════════════
# INTER-TIER CONNECTORS
# ════════════════════════════════════════════════════════════════════════════
# Tier 1 → Tier 2 (request) and Tier 2 → Tier 1 (response)
conn(ax, (LX + BW / 2 - 6, t2_y + t2_h), (LX + BW / 2 - 6, t1_y), color=C_ARROW_DATA,
     lw=2.0, style='-|>')
conn(ax, (LX + BW / 2 + 6, t1_y), (LX + BW / 2 + 6, t2_y + t2_h), color=C_ARROW_DATA,
     lw=2.0, style='-|>')
conn_label(ax, LX + BW / 2, (t1_y + t2_y + t2_h) / 2 + 0.3,
           'HTTP / REST  ·  JSON  ·  HTTP Basic Auth', color=C_ARROW_DATA, size=7.4)
label(ax, LX + BW / 2 - 9.5, (t1_y + t2_y + t2_h) / 2, 'request ▲', size=6.0,
      color=C_ARROW_DATA, z=11)
label(ax, LX + BW / 2 + 9.8, (t1_y + t2_y + t2_h) / 2, '▼ response', size=6.0,
      color=C_ARROW_DATA, z=11)

# Tier 2 → Tier 3 (SQL via ORM)
conn(ax, (LX + BW / 2 - 5, t2_y), (LX + BW / 2 - 5, t3_y + t3_h), color=C_ARROW_DATA,
     lw=2.0, style='-|>')
conn(ax, (LX + BW / 2 + 5, t3_y + t3_h), (LX + BW / 2 + 5, t2_y), color=C_ARROW_DATA,
     lw=2.0, style='-|>')
conn_label(ax, LX + BW / 2, (t2_y + t3_y + t3_h) / 2,
           'SQL  ·  SQLAlchemy ORM  ·  TCP 5432', color=C_ARROW_DATA, size=7.4)

# Tier 2 → External (HTTPS API calls)
conn(ax, (RX, t2_y + t2_h / 2 + 1), (EXT_X, t2_y + t2_h / 2 + 1), color=C_EXT_HEAD,
     lw=1.7, style='-|>', dashed=True)
conn(ax, (EXT_X, t2_y + t2_h / 2 - 3), (RX, t2_y + t2_h / 2 - 3), color=C_EXT_HEAD,
     lw=1.4, style='-|>', dashed=True)
conn_label(ax, (RX + EXT_X) / 2, t2_y + t2_h / 2 + 3.0, 'HTTPS\nAPI keys',
           color=C_EXT_HEAD, size=6.3)

# ════════════════════════════════════════════════════════════════════════════
# LEGEND + footer
# ════════════════════════════════════════════════════════════════════════════
ly = 18.0
label(ax, LX, ly + 1.4, 'Legend', size=8.5, weight='bold', ha='left', z=6)
leg = [
    (C_TIER1_BAND, C_TIER1_HEAD, 'Presentation tier'),
    (C_TIER2_BAND, C_TIER2_HEAD, 'Application tier'),
    (C_TIER3_BAND, C_TIER3_HEAD, 'Data tier'),
    (C_EXT_BAND,  C_EXT_HEAD,  'External systems'),
]
lx = LX + 9
for band, edge, txt in leg:
    rbox(ax, lx, ly + 0.6, 2.0, 1.6, band, edge=edge, lw=1.2, r=0.1, z=6)
    label(ax, lx + 2.6, ly + 1.4, txt, size=7.2, ha='left', z=6)
    lx += 19

# connector key
ky = ly - 2.8
ax.annotate('', xy=(LX + 5, ky), xytext=(LX, ky),
            arrowprops=dict(arrowstyle='-|>', color=C_ARROW_DATA, lw=2.0), zorder=6)
label(ax, LX + 6, ky, 'synchronous data flow (tier boundary)', size=7.0, ha='left', z=6)
ax.annotate('', xy=(LX + 49, ky), xytext=(LX + 44, ky),
            arrowprops=dict(arrowstyle='-|>', color=C_EXT_HEAD, lw=1.6,
                            linestyle=(0, (5, 3))), zorder=6)
label(ax, LX + 50, ky, 'external API call (HTTPS)', size=7.0, ha='left', z=6)

label(ax, 50, 2.0,
      'FairMark — AI-Based Paper Checking System   |   FastAPI · React · PostgreSQL · SBERT/LLM   |   '
      'Figure: Three-Tier Architecture (UML 2.5 / IEEE 1016)',
      size=7.2, color=C_SUBTLE, z=6)

# ── Save ───────────────────────────────────────────────────────────────────--
out = r'D:\FYP\fairmark-v1.1\FairMark-Ai-Based-Paper-Checking-System\FairMark_Three_Tier_Architecture.png'
plt.savefig(out, dpi=DPI, bbox_inches='tight', facecolor=C_BG, pad_inches=0.15)
plt.close()
print(f"Saved: {out}")
print(f"Size : ~{int(FIG_W * DPI)} x {int(FIG_H * DPI)} px @ {DPI} DPI")
