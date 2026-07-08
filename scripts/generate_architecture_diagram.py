#!/usr/bin/env python3
"""
SmartShop System Architecture Diagram
Hand-drawn sketch style on grid paper using Pillow.
"""

import random
import math
import os
from PIL import Image, ImageDraw, ImageFont

# ── Reproducible randomness ───────────────────────────────────────────────────
random.seed(42)

# ── Canvas ────────────────────────────────────────────────────────────────────
W, H = 2400, 1600
img = Image.new("RGB", (W, H), "#FAF6EE")
draw = ImageDraw.Draw(img)

# ── Fonts ─────────────────────────────────────────────────────────────────────
FONT_PATH_REG  = "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"
FONT_PATH_BOLD = "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"

def load_font(path, size):
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        return ImageFont.load_default()

font_tiny   = load_font(FONT_PATH_REG,  16)
font_small  = load_font(FONT_PATH_REG,  19)
font_body   = load_font(FONT_PATH_REG,  22)
font_label  = load_font(FONT_PATH_BOLD, 22)
font_head   = load_font(FONT_PATH_BOLD, 26)
font_title  = load_font(FONT_PATH_BOLD, 36)
font_sec    = load_font(FONT_PATH_BOLD, 30)

# ── Ink palette ───────────────────────────────────────────────────────────────
INK_CHARCOAL = "#2D3748"
INK_BLUE     = "#2563EB"
INK_GREEN    = "#0D9488"
INK_PURPLE   = "#7C3AED"
INK_RED      = "#B91C1C"
INK_ORANGE   = "#D97706"
GRID_COLOR   = "#E4EBF0"

# ─────────────────────────────────────────────────────────────────────────────
# 1. Grid background
# ─────────────────────────────────────────────────────────────────────────────
GRID = 40
for x in range(0, W, GRID):
    draw.line([(x, 0), (x, H)], fill=GRID_COLOR, width=1)
for y in range(0, H, GRID):
    draw.line([(0, y), (W, y)], fill=GRID_COLOR, width=1)

# ─────────────────────────────────────────────────────────────────────────────
# 2. Helper: wobbly line
# ─────────────────────────────────────────────────────────────────────────────
def wobbly_line(d, x0, y0, x1, y1, color, width=2, wobble=2.5, passes=2):
    """Draw a hand-drawn line by segmenting and adding perpendicular wobble."""
    segs = random.randint(6, 10)
    dx, dy = x1 - x0, y1 - y0
    length = math.hypot(dx, dy) or 1
    px, py = -dy / length, dx / length

    for _ in range(passes):
        pts = []
        for i in range(segs + 1):
            t = i / segs
            bx = x0 + t * dx
            by = y0 + t * dy
            w = random.uniform(-wobble, wobble) if 0 < i < segs else 0
            pts.append((bx + px * w, by + py * w))
        for i in range(len(pts) - 1):
            d.line([pts[i], pts[i + 1]], fill=color, width=width)

# ─────────────────────────────────────────────────────────────────────────────
# 3. Helper: wobbly rect
# ─────────────────────────────────────────────────────────────────────────────
def wobbly_rect(d, x0, y0, x1, y1, color, width=2, wobble=2.5, overshoot=6):
    """Draw 4 borders with slight corner overshoot."""
    os_ = random.randint(4, overshoot)
    wobbly_line(d, x0 - os_, y0, x1 + os_, y0, color, width, wobble)
    wobbly_line(d, x1, y0 - os_, x1, y1 + os_, color, width, wobble)
    wobbly_line(d, x1 + os_, y1, x0 - os_, y1, color, width, wobble)
    wobbly_line(d, x0, y1 + os_, x0, y0 - os_, color, width, wobble)

# ─────────────────────────────────────────────────────────────────────────────
# 4. Helper: wobbly arrow
# ─────────────────────────────────────────────────────────────────────────────
def wobbly_arrow(d, x0, y0, x1, y1, color, width=2, wobble=2.0, head_size=14):
    """Wobbly line + arrowhead at (x1,y1)."""
    wobbly_line(d, x0, y0, x1, y1, color, width, wobble)
    angle = math.atan2(y1 - y0, x1 - x0)
    spread = math.radians(28)
    for side in (-1, 1):
        ax = x1 - head_size * math.cos(angle - side * spread)
        ay = y1 - head_size * math.sin(angle - side * spread)
        wobbly_line(d, x1, y1, ax, ay, color, width, 1.0, 1)

# ─────────────────────────────────────────────────────────────────────────────
# 5. Helper: wobbly ellipse
# ─────────────────────────────────────────────────────────────────────────────
def wobbly_ellipse(d, cx, cy, rx, ry, color, width=2, wobble=2.5, n_pts=36):
    """Draw ellipse with slight radial wobble, closed with overlap."""
    pts = []
    for i in range(n_pts + 3):
        theta = 2 * math.pi * i / n_pts
        r = random.uniform(-wobble, wobble)
        x = cx + (rx + r) * math.cos(theta)
        y = cy + (ry + r) * math.sin(theta)
        pts.append((x, y))
    for i in range(len(pts) - 1):
        d.line([pts[i], pts[i + 1]], fill=color, width=width)

# ─────────────────────────────────────────────────────────────────────────────
# 6. Helper: centered text in box
# ─────────────────────────────────────────────────────────────────────────────
def centered_text(d, x0, y0, x1, y1, text, font, color):
    cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
    bbox = d.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    d.text((cx - tw // 2, cy - th // 2), text, font=font, fill=color)

def multiline_centered(d, cx, cy, lines, font, color, line_h=26):
    total = len(lines) * line_h
    for i, line in enumerate(lines):
        bbox = d.textbbox((0, 0), line, font=font)
        tw = bbox[2] - bbox[0]
        y = cy - total // 2 + i * line_h
        d.text((cx - tw // 2, y), line, font=font, fill=color)

# ─────────────────────────────────────────────────────────────────────────────
# 7. Helper: draw a labelled box (rect + label)
# ─────────────────────────────────────────────────────────────────────────────
def box(d, x0, y0, x1, y1, label, color,
        font=None, text_color=None, wobble=2.5, width=2,
        sublabel=None, sub_font=None):
    if font is None:
        font = font_label
    if text_color is None:
        text_color = color
    if sub_font is None:
        sub_font = font_small
    wobbly_rect(d, x0, y0, x1, y1, color, width, wobble)
    if sublabel:
        cy = (y0 + y1) // 2
        bbox = d.textbbox((0, 0), label, font=font)
        tw = bbox[2] - bbox[0]
        cx = (x0 + x1) // 2
        d.text((cx - tw // 2, cy - 18), label, font=font, fill=text_color)
        bbox2 = d.textbbox((0, 0), sublabel, font=sub_font)
        tw2 = bbox2[2] - bbox2[0]
        d.text((cx - tw2 // 2, cy + 4), sublabel, font=sub_font, fill=text_color)
    else:
        centered_text(d, x0, y0, x1, y1, label, font, text_color)

# ─────────────────────────────────────────────────────────────────────────────
# 8. Helper: section label banner
# ─────────────────────────────────────────────────────────────────────────────
def section_banner(d, x, y, text, color):
    bbox = d.textbbox((0, 0), text, font=font_sec)
    tw = bbox[2] - bbox[0]
    d.text((x, y), text, font=font_sec, fill=color)
    wobbly_line(d, x, y + bbox[3] + 2, x + tw, y + bbox[3] + 2,
                color, 2, 1.5, 1)

# ─────────────────────────────────────────────────────────────────────────────
# 9. TITLE
# ─────────────────────────────────────────────────────────────────────────────
title_text = "SmartShop  —  Agentic E-Commerce System Architecture"
bbox = draw.textbbox((0, 0), title_text, font=font_title)
tw = bbox[2] - bbox[0]
draw.text(((W - tw) // 2, 22), title_text, font=font_title, fill=INK_CHARCOAL)
wobbly_line(draw, (W - tw) // 2, 68, (W + tw) // 2, 68, INK_CHARCOAL, 2, 1.5, 1)

# ─────────────────────────────────────────────────────────────────────────────
# 10. Layout constants
# ─────────────────────────────────────────────────────────────────────────────
ROW1_Y  = 100
ROW2_Y  = 270
ROW3_Y  = 420
ROW4_Y  = 790
ROW5_Y  = 960
ROW6_Y  = 1130
ROW7_Y  = 1300

BOX_H   = 68
AGENT_H = 76

# ─────────────────────────────────────────────────────────────────────────────
# 11. CLIENT STOREFRONTS  (ROW1, left cluster)
# ─────────────────────────────────────────────────────────────────────────────
section_banner(draw, 60, ROW1_Y, "CLIENT STOREFRONTS", INK_BLUE)

clients = [
    ("Web Storefront", "(Next.js)", 60,  ROW1_Y + 40),
    ("FB Messenger",  "Webhook",   340,  ROW1_Y + 40),
    ("Instagram DM",  "Webhook",   620,  ROW1_Y + 40),
]
client_cx = []
for lbl, sub, bx, by in clients:
    box(draw, bx, by, bx + 240, by + BOX_H, lbl, INK_BLUE,
        font=font_label, sublabel=sub, sub_font=font_small)
    client_cx.append(bx + 120)

# ─────────────────────────────────────────────────────────────────────────────
# 12. EXTERNAL AGENTS (ROW1, right cluster)
# ─────────────────────────────────────────────────────────────────────────────
section_banner(draw, 1520, ROW1_Y, "EXTERNAL AGENTS", INK_ORANGE)

ext_agents = [
    ("Cursor / ChatGPT", "(MCP Client)", 1520, ROW1_Y + 40),
    ("Any MCP Client",   "(OpenAI compat)", 1810, ROW1_Y + 40),
]
ext_cx = []
for lbl, sub, bx, by in ext_agents:
    box(draw, bx, by, bx + 260, by + BOX_H, lbl, INK_ORANGE,
        font=font_label, sublabel=sub, sub_font=font_small)
    ext_cx.append(bx + 130)

# ─────────────────────────────────────────────────────────────────────────────
# 13. FASTAPI BACKEND GATEWAY (ROW2)
# ─────────────────────────────────────────────────────────────────────────────
section_banner(draw, 60, ROW2_Y, "FASTAPI BACKEND", INK_GREEN)

GW_X0, GW_X1 = 60, 900
GW_Y0, GW_Y1 = ROW2_Y + 40, ROW2_Y + 40 + BOX_H
box(draw, GW_X0, GW_Y0, GW_X1, GW_Y1,
    "FastAPI Gateway  /chat  /stream  /mcp", INK_GREEN,
    font=font_head, width=3, wobble=3)

MCP_X0, MCP_X1 = 1000, 1460
MCP_Y0, MCP_Y1 = ROW2_Y + 40, ROW2_Y + 40 + BOX_H
box(draw, MCP_X0, MCP_Y0, MCP_X1, MCP_Y1,
    "MCP Tool Endpoint", INK_ORANGE,
    font=font_head, sublabel="(OpenAI-compatible)", sub_font=font_small,
    width=2)

# ─────────────────────────────────────────────────────────────────────────────
# 14. CORE PIPELINE (ROW3)
# ─────────────────────────────────────────────────────────────────────────────
section_banner(draw, 60, ROW3_Y, "CORE PIPELINE", INK_GREEN)

pipeline_steps = [
    ("Input Sanitizer",               None),
    ("Query Rewriter",                "(w/ history ctx)"),
    ("LLM Planner Agent",             None),
    ("Capability Binder",             None),
    ("DAG Pipeline Executor",         "(Parallel)"),
    ("Response Generator",            "(SSE stream · GenUI)"),
]

PL_X0 = 60
PL_BOX_W = 300
PL_BOX_H = 70
PL_GAP   = 20
PL_Y_START = ROW3_Y + 40

pipe_centers = []
for i, (lbl, sub) in enumerate(pipeline_steps):
    bx = PL_X0 + i * (PL_BOX_W + PL_GAP)
    by = PL_Y_START
    box(draw, bx, by, bx + PL_BOX_W, by + PL_BOX_H, lbl, INK_GREEN,
        font=font_label, sublabel=sub, sub_font=font_small, width=2)
    pipe_centers.append((bx + PL_BOX_W // 2, by + PL_BOX_H // 2))

# Arrows between pipeline steps
for i in range(len(pipe_centers) - 1):
    ax1 = pipe_centers[i][0] + PL_BOX_W // 2
    ax2 = pipe_centers[i + 1][0] - PL_BOX_W // 2
    ay  = PL_Y_START + PL_BOX_H // 2
    wobbly_arrow(draw, ax1, ay, ax2, ay, INK_GREEN, width=2)

# ─────────────────────────────────────────────────────────────────────────────
# 15. SPECIALIST AGENTS (ROW4)
# ─────────────────────────────────────────────────────────────────────────────
section_banner(draw, 60, ROW4_Y, "SPECIALIST AGENTS", INK_GREEN)

agents = [
    "Product Search",
    "Recommendation",
    "Try-On Agent",
    "Cart Agent",
    "Checkout Agent",
    "Knowledge Agent",
]

AG_W    = 310
AG_H    = AGENT_H
AG_GAP  = 18
AG_Y0   = ROW4_Y + 40
AG_X_START = 60
agent_cx = []
agent_cy = AG_Y0 + AG_H // 2

for i, name in enumerate(agents):
    bx = AG_X_START + i * (AG_W + AG_GAP)
    by = AG_Y0
    box(draw, bx, by, bx + AG_W, by + AG_H, name, INK_GREEN,
        font=font_label, width=2)
    agent_cx.append(bx + AG_W // 2)

# DAG Executor fan-out -> each agent
exec_cx, exec_cy = pipe_centers[4]
exec_bottom = PL_Y_START + PL_BOX_H
for acx in agent_cx:
    wobbly_arrow(draw, exec_cx, exec_bottom + 130, acx, AG_Y0, INK_GREEN, width=2, wobble=3)

# ─────────────────────────────────────────────────────────────────────────────
# 16. DATABASES & STORAGE (ROW5)
# ─────────────────────────────────────────────────────────────────────────────
section_banner(draw, 60, ROW5_Y, "DATABASES & STORAGE", INK_PURPLE)

DB_Y0  = ROW5_Y + 40
DB_H   = 80

dbs = [
    ("Supabase PostgreSQL",   "products · sessions · cart · orders · history",  60,  DB_Y0, 500, DB_H),
    ("Pinecone Vector DB",    "Semantic / RAG embeddings",                       600, DB_Y0, 380, DB_H),
    ("Catalog Files",         "Images · JSON feeds",                             1020, DB_Y0, 280, DB_H),
]

db_cx = []
for lbl, sub, bx, by, bw, bh in dbs:
    box(draw, bx, by, bx + bw, by + bh, lbl, INK_PURPLE,
        font=font_label, sublabel=sub, sub_font=font_small, width=2, wobble=3)
    db_cx.append(bx + bw // 2)

# Arrows: agents -> dbs
agent_db_pairs = [
    (0, 0), (0, 1),
    (1, 0), (1, 1),
    (2, 2),
    (3, 0),
    (4, 0),
    (5, 1),
]
for ai, di in agent_db_pairs:
    acx = agent_cx[ai]
    _, _, dbx0, dby0, dbw, dbh = dbs[di]
    dcx = dbx0 + dbw // 2
    wobbly_arrow(draw, acx, AG_Y0 + AG_H, dcx, DB_Y0, INK_PURPLE, width=1, wobble=2)

# ─────────────────────────────────────────────────────────────────────────────
# 17. INFERENCE & TRY-ON (ROW6)
# ─────────────────────────────────────────────────────────────────────────────
section_banner(draw, 60, ROW6_Y, "INFERENCE & TRY-ON", INK_RED)

INF_Y0 = ROW6_Y + 40

inference_boxes = [
    ("vLLM Server",     "+ ngrok tunnel",       60,  INF_Y0, 320, 72),
    ("Try-On Image",    "Backend (ComfyUI)",     430, INF_Y0, 320, 72),
    ("Vision LLM",      "(Product desc / Q&A)",  800, INF_Y0, 320, 72),
]
inf_cx = []
for lbl, sub, bx, by, bw, bh in inference_boxes:
    box(draw, bx, by, bx + bw, by + bh, lbl, INK_RED,
        font=font_label, sublabel=sub, sub_font=font_small, width=2)
    inf_cx.append(bx + bw // 2)

# Try-On agent -> Try-On backend
wobbly_arrow(draw, agent_cx[2], AG_Y0 + AG_H,
             inf_cx[1], INF_Y0 - 140, INK_RED, width=2, wobble=3)

# Planner -> vLLM
wobbly_arrow(draw, pipe_centers[2][0], PL_Y_START + PL_BOX_H,
             inf_cx[0], INF_Y0, INK_RED, width=2, wobble=3)

# ─────────────────────────────────────────────────────────────────────────────
# 18. META GRAPH API (ROW7)
# ─────────────────────────────────────────────────────────────────────────────
META_Y0 = ROW7_Y + 30
box(draw, 60, META_Y0, 500, META_Y0 + 72,
    "Meta Graph API", INK_RED,
    font=font_head, sublabel="FB Messenger · Instagram DM webhooks",
    sub_font=font_small, width=2, wobble=3)

# Try-On backend -> Meta
wobbly_arrow(draw, inf_cx[1], INF_Y0 + 72, 280, META_Y0, INK_RED, width=2, wobble=3)

# ─────────────────────────────────────────────────────────────────────────────
# 19. VERTICAL FLOW: Clients -> Gateway
# ─────────────────────────────────────────────────────────────────────────────
# Web storefront -> gateway
wobbly_arrow(draw, client_cx[0], ROW1_Y + 40 + BOX_H,
             client_cx[0], GW_Y0, INK_BLUE, width=2)
# FB Messenger -> gateway
wobbly_arrow(draw, client_cx[1], ROW1_Y + 40 + BOX_H,
             (GW_X0 + GW_X1) // 3, GW_Y0, INK_BLUE, width=2)
# IG DM -> gateway
wobbly_arrow(draw, client_cx[2], ROW1_Y + 40 + BOX_H,
             GW_X1 - 80, GW_Y0, INK_BLUE, width=2)

# External agents -> MCP endpoint
for ecx in ext_cx:
    mcp_cx = (MCP_X0 + MCP_X1) // 2
    wobbly_arrow(draw, ecx, ROW1_Y + 40 + BOX_H,
                 mcp_cx, MCP_Y0, INK_ORANGE, width=2)

# MCP endpoint -> gateway
wobbly_arrow(draw, MCP_X0, (MCP_Y0 + MCP_Y1) // 2,
             GW_X1, (GW_Y0 + GW_Y1) // 2, INK_ORANGE, width=2)

# Gateway -> pipeline (Input Sanitizer)
wobbly_arrow(draw, (GW_X0 + GW_X1) // 2, GW_Y1,
             pipe_centers[0][0], PL_Y_START, INK_GREEN, width=2)

# Response Generator -> Gateway (back up)
resp_cx = pipe_centers[-1][0]
wobbly_arrow(draw, resp_cx, PL_Y_START,
             resp_cx + 40, GW_Y1 + 5, INK_GREEN, width=2, wobble=3)

# ─────────────────────────────────────────────────────────────────────────────
# 20. Session/History annotation oval on Supabase
# ─────────────────────────────────────────────────────────────────────────────
wobbly_ellipse(draw, 310, DB_Y0 - 28, 90, 18, INK_PURPLE, width=1, wobble=2)
draw.text((232, DB_Y0 - 38), "session history", font=font_tiny, fill=INK_PURPLE)

# ─────────────────────────────────────────────────────────────────────────────
# 21. Legend (bottom-right)
# ─────────────────────────────────────────────────────────────────────────────
LG_X = 1620
LG_Y = 940
draw.text((LG_X, LG_Y - 28), "LEGEND", font=font_head, fill=INK_CHARCOAL)
legend_items = [
    (INK_BLUE,    "Client / Storefront layer"),
    (INK_ORANGE,  "External Agent / MCP layer"),
    (INK_GREEN,   "Backend / Agent pipeline"),
    (INK_PURPLE,  "Database / Storage layer"),
    (INK_RED,     "Inference / External API"),
]
for i, (col, lbl) in enumerate(legend_items):
    ly = LG_Y + i * 36
    wobbly_line(draw, LG_X, ly + 10, LG_X + 50, ly + 10, col, 3, 1.5, 1)
    draw.text((LG_X + 60, ly), lbl, font=font_body, fill=INK_CHARCOAL)

# ─────────────────────────────────────────────────────────────────────────────
# 22. Corner doodle — small logo sketch (bottom-left)
# ─────────────────────────────────────────────────────────────────────────────
wobbly_ellipse(draw, 90, H - 60, 70, 32, INK_CHARCOAL, width=2, wobble=3)
draw.text((46, H - 75), "SmartShop v2", font=font_label, fill=INK_CHARCOAL)

# ─────────────────────────────────────────────────────────────────────────────
# 23. Save outputs
# ─────────────────────────────────────────────────────────────────────────────
BASE = "/home/ujjwal/codeagent/new/agentic_ecommerce_project"
OUTPUT_PATHS = [
    f"{BASE}/report/assets/architecture_diagram.png",
    f"{BASE}/typst_proposal/images/architecture_diagram.png",
    f"{BASE}/latex_proposal/images/architecture_diagram.png",
]

for path in OUTPUT_PATHS:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    img.save(path, "PNG", dpi=(150, 150))
    print(f"Saved: {path}")

print("Done.")
