#!/usr/bin/env python3
"""
SmartShop Architecture Diagram
Hand-drawn sketch style (pencil/pen on grid paper) using Pillow.
"""

import random
import math
import os
from PIL import Image, ImageDraw, ImageFont

# ─────────────────────────────────────────────
# Seeded RNG for reproducible wobble
# ─────────────────────────────────────────────
random.seed(42)

# ─────────────────────────────────────────────
# Canvas constants
# ─────────────────────────────────────────────
W, H = 2400, 1600
BG_COLOR   = "#FAF6EE"
GRID_COLOR = "#E4EBF0"
GRID_STEP  = 40

# ─────────────────────────────────────────────
# Ink-pen colour palette
# ─────────────────────────────────────────────
INK_CHARCOAL = "#2D3748"
INK_BLUE     = "#2563EB"
INK_GREEN    = "#0D9488"
INK_PURPLE   = "#7C3AED"
INK_RED      = "#B91C1C"
INK_ORANGE   = "#C2410C"
INK_GRAY     = "#64748B"

# ─────────────────────────────────────────────
# Font loader
# ─────────────────────────────────────────────
def load_fonts():
    reg_path  = "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"
    bold_path = "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"
    try:
        font_sm   = ImageFont.truetype(reg_path,  18)
        font_md   = ImageFont.truetype(reg_path,  22)
        font_lg   = ImageFont.truetype(bold_path, 28)
        font_xl   = ImageFont.truetype(bold_path, 36)
        font_hdr  = ImageFont.truetype(bold_path, 44)
        font_tiny = ImageFont.truetype(reg_path,  15)
    except Exception:
        default   = ImageFont.load_default()
        font_sm = font_md = font_lg = font_xl = font_hdr = font_tiny = default
    return font_tiny, font_sm, font_md, font_lg, font_xl, font_hdr

# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

def _perp_offset(p1, p2, amount):
    """Return a point offset perpendicular to the p1→p2 direction."""
    dx, dy = p2[0] - p1[0], p2[1] - p1[1]
    length = math.hypot(dx, dy) or 1
    nx, ny = -dy / length, dx / length
    return nx * amount, ny * amount


def draw_wobbly_line(draw, p1, p2, color, width=2, wobble=2):
    """Draw a hand-drawn wobbly line from p1 to p2 (two overlapping passes)."""
    segs = random.randint(6, 10)
    for _pass in range(2):
        pts = [p1]
        for i in range(1, segs):
            t = i / segs
            mx = p1[0] + (p2[0] - p1[0]) * t
            my = p1[1] + (p2[1] - p1[1]) * t
            ox, oy = _perp_offset(p1, p2, random.uniform(-wobble, wobble))
            pts.append((mx + ox, my + oy))
        pts.append(p2)
        draw.line(pts, fill=color, width=width)


def draw_hand_drawn_box(draw, x, y, w, h, color, width=2, wobble=2):
    """Draw a wobbly rectangle with corners extending slightly beyond vertices."""
    ext = random.randint(4, 9)
    # top
    draw_wobbly_line(draw, (x - ext, y),     (x + w + ext, y),     color, width, wobble)
    # bottom
    draw_wobbly_line(draw, (x - ext, y + h), (x + w + ext, y + h), color, width, wobble)
    # left
    draw_wobbly_line(draw, (x, y - ext),     (x, y + h + ext),     color, width, wobble)
    # right
    draw_wobbly_line(draw, (x + w, y - ext), (x + w, y + h + ext), color, width, wobble)


def draw_hand_drawn_arrow(draw, p1, p2, color, width=2, wobble=2, head_len=18):
    """Draw a wobbly line with a two-stroke arrowhead at p2."""
    draw_wobbly_line(draw, p1, p2, color, width, wobble)
    angle = math.atan2(p2[1] - p1[1], p2[0] - p1[0])
    spread = math.radians(28)
    for side in (-1, 1):
        ax = p2[0] - head_len * math.cos(angle - side * spread)
        ay = p2[1] - head_len * math.sin(angle - side * spread)
        draw_wobbly_line(draw, p2, (ax, ay), color, width, wobble=1)


def draw_wobbly_circle(draw, cx, cy, r, color, width=2, wobble=3):
    """Draw a hand-drawn circle by connecting equally-spaced points with radial wobble."""
    n = 40
    pts = []
    for i in range(n + 2):          # +2 so the end overlaps slightly
        angle = 2 * math.pi * i / n
        rr = r + random.uniform(-wobble, wobble)
        pts.append((cx + rr * math.cos(angle), cy + rr * math.sin(angle)))
    draw.line(pts, fill=color, width=width)


def draw_label(draw, text, x, y, font, color=INK_CHARCOAL, anchor="mm"):
    draw.text((x, y), text, font=font, fill=color, anchor=anchor)


def draw_box_with_label(draw, x, y, w, h, label, font, box_color,
                        label_color=None, sub=None, sub_font=None,
                        width=2, wobble=2):
    """Draw a box and centred label."""
    draw_hand_drawn_box(draw, x, y, w, h, box_color, width=width, wobble=wobble)
    lc = label_color or box_color
    cx, cy = x + w // 2, y + h // 2
    if sub:
        draw_label(draw, label, cx, cy - 12, font, lc)
        draw_label(draw, sub, cx, cy + 14, sub_font or font, lc)
    else:
        draw_label(draw, label, cx, cy, font, lc)


# ─────────────────────────────────────────────
# Build the image
# ─────────────────────────────────────────────

def build_diagram():
    img  = Image.new("RGB", (W, H), BG_COLOR)
    draw = ImageDraw.Draw(img)

    font_tiny, font_sm, font_md, font_lg, font_xl, font_hdr = load_fonts()

    # ── Grid ──────────────────────────────────
    for x in range(0, W, GRID_STEP):
        draw.line([(x, 0), (x, H)], fill=GRID_COLOR, width=1)
    for y in range(0, H, GRID_STEP):
        draw.line([(0, y), (W, y)], fill=GRID_COLOR, width=1)

    # ── Title ─────────────────────────────────
    draw_label(draw, "SmartShop  —  Agentic E-Commerce System Architecture",
               W // 2, 52, font_hdr, INK_CHARCOAL)
    draw_label(draw, "Hand-drawn sketch overview  |  v1.0",
               W // 2, 94, font_sm, INK_GRAY)
    draw_wobbly_line(draw, (80, 110), (W - 80, 110), INK_CHARCOAL, width=2, wobble=1)

    # ══════════════════════════════════════════
    # LAYER 0 — Client Storefronts  (top-left cluster)
    # ══════════════════════════════════════════
    draw_wobbly_line(draw, (40, 130), (40, 420), INK_BLUE, width=3, wobble=2)
    draw_label(draw, "CLIENT LAYER", 68, 145, font_lg, INK_BLUE, anchor="lm")

    # Web Storefront
    draw_box_with_label(draw, 80, 165, 280, 80,
                        "Web Storefront", font_md, INK_BLUE,
                        sub="(Next.js)", sub_font=font_sm, width=2)

    # FB Messenger
    draw_box_with_label(draw, 80, 275, 280, 75,
                        "FB Messenger", font_md, INK_BLUE,
                        sub="Webhook DMs", sub_font=font_sm, width=2)

    # IG DM
    draw_box_with_label(draw, 80, 375, 280, 75,
                        "Instagram DM", font_md, INK_BLUE,
                        sub="Webhook DMs", sub_font=font_sm, width=2)

    # ── External Agent (MCP) ──────────────────
    draw_wobbly_line(draw, (40, 480), (40, 590), INK_ORANGE, width=3, wobble=2)
    draw_label(draw, "EXTERNAL AGENTS", 68, 496, font_lg, INK_ORANGE, anchor="lm")

    draw_box_with_label(draw, 80, 515, 280, 85,
                        "Cursor / ChatGPT", font_md, INK_ORANGE,
                        sub="MCP Client", sub_font=font_sm, width=2)

    # ══════════════════════════════════════════
    # LAYER 1 — FastAPI Backend  (centre column)
    # ══════════════════════════════════════════
    BX = 520   # backend column left
    BW = 360   # box width

    draw_wobbly_line(draw, (BX - 20, 130), (BX - 20, 1460),
                     INK_GREEN, width=3, wobble=2)
    draw_label(draw, "FASTAPI BACKEND  (Core Pipeline)",
               BX + BW // 2, 145, font_lg, INK_GREEN)

    pipeline_boxes = [
        ("Input Sanitizer",              160),
        ("Query Rewriter",               270),
        ("LLM Planner Agent",            390),
        ("Capability Binder",            500),
        ("Parallel DAG Pipeline Executor", 610),
        ("Response Generator",           730),
    ]

    pipe_subs = {
        "Query Rewriter":    "w/ History Context",
        "Response Generator": "SSE streaming / GenUI cards",
    }

    pipe_centers = {}
    prev_bottom = None
    for name, top in pipeline_boxes:
        sub = pipe_subs.get(name)
        draw_box_with_label(draw, BX, top, BW, 80,
                            name, font_md, INK_GREEN,
                            sub=sub, sub_font=font_sm, width=2)
        cy = top + 40
        pipe_centers[name] = (BX + BW // 2, cy)
        if prev_bottom is not None:
            draw_hand_drawn_arrow(draw,
                                  (BX + BW // 2, prev_bottom),
                                  (BX + BW // 2, top),
                                  INK_GREEN, width=2)
        prev_bottom = top + 80

    # Arrow: Response Generator → SSE out label
    draw_hand_drawn_arrow(draw,
                          (BX + BW, 770),
                          (BX + BW + 60, 770),
                          INK_GREEN, width=2)
    draw_label(draw, "SSE stream", BX + BW + 110, 770, font_sm, INK_GREEN, anchor="lm")

    # ══════════════════════════════════════════
    # LAYER 2 — Specialist Agents  (right of backend)
    # ══════════════════════════════════════════
    AX = 1040
    AW = 260
    AH = 68

    draw_wobbly_line(draw, (AX - 20, 130), (AX - 20, 1100),
                     INK_PURPLE, width=3, wobble=2)
    draw_label(draw, "SPECIALIST AGENTS",
               AX + AW // 2, 145, font_lg, INK_PURPLE)

    agents = [
        ("Product Search Agent",  180),
        ("Recommendation Agent",  278),
        ("Try-On Agent",          376),
        ("Cart Agent",            474),
        ("Checkout Agent",        572),
        ("Knowledge Agent",       670),
    ]

    agent_centers = {}
    for name, top in agents:
        draw_box_with_label(draw, AX, top, AW, AH, name, font_md,
                            INK_PURPLE, width=2)
        agent_centers[name] = (AX + AW // 2, top + AH // 2)

    # Arrows: Executor → each agent
    ex_right = BX + BW
    ex_cy    = 650
    for name, top in agents:
        ay = top + AH // 2
        draw_hand_drawn_arrow(draw,
                              (ex_right, ex_cy),
                              (AX, ay),
                              INK_PURPLE, width=2, wobble=2)

    # ══════════════════════════════════════════
    # LAYER 3 — Databases & Storage  (bottom centre)
    # ══════════════════════════════════════════
    DX = 520
    DY = 960
    DW = 340
    DH = 90

    draw_wobbly_line(draw, (DX - 20, DY - 30), (DX - 20, DY + 380),
                     INK_PURPLE, width=3, wobble=2)
    draw_label(draw, "DATABASES & STORAGE",
               DX + DW // 2, DY - 15, font_lg, INK_PURPLE)

    dbs = [
        ("Supabase PostgreSQL",   "products / sessions / cart / orders / history", DY + 20),
        ("Pinecone Vector DB",    "Semantic search embeddings",                    DY + 135),
        ("Catalog Files",         "S3-compatible object store",                    DY + 250),
    ]

    db_centers = {}
    for title, sub, top in dbs:
        draw_box_with_label(draw, DX, top, DW, DH,
                            title, font_md, INK_PURPLE,
                            sub=sub, sub_font=font_sm, width=2)
        db_centers[title] = (DX + DW // 2, top + DH // 2)

    # Arrows: Response Generator ↓ → Supabase (pipeline writes)
    draw_hand_drawn_arrow(draw,
                          (BX + BW // 2, 810),
                          (db_centers["Supabase PostgreSQL"][0],
                           db_centers["Supabase PostgreSQL"][1] - 45),
                          INK_GREEN, width=2, wobble=2)

    # Agents → DBs
    for agent_name in ["Product Search Agent", "Recommendation Agent", "Knowledge Agent"]:
        ax, ay = agent_centers[agent_name]
        draw_hand_drawn_arrow(draw,
                              (ax, ay + AH // 2 + 4),
                              (DX + DW, db_centers["Supabase PostgreSQL"][1]),
                              INK_PURPLE, width=1, wobble=2)

    draw_hand_drawn_arrow(draw,
                          agent_centers["Product Search Agent"],
                          (DX + DW, db_centers["Pinecone Vector DB"][1]),
                          INK_PURPLE, width=1, wobble=2)

    # ══════════════════════════════════════════
    # LAYER 4 — Inference / Try-On  (far right)
    # ══════════════════════════════════════════
    IX = 1420
    IW = 320

    draw_wobbly_line(draw, (IX - 20, 130), (IX - 20, 700),
                     INK_RED, width=3, wobble=2)
    draw_label(draw, "INFERENCE / TRY-ON",
               IX + IW // 2, 145, font_lg, INK_RED)

    inference = [
        ("vLLM Server",           "Local GPU endpoint",      190),
        ("ngrok Tunnel",          "Public HTTPS relay",      310),
        ("Try-On Image Backend",  "Virtual fitting service", 430),
        ("Meta Graph API",        "FB/IG webhook gateway",   550),
    ]

    inf_centers = {}
    for title, sub, top in inference:
        draw_box_with_label(draw, IX, top, IW, 88,
                            title, font_md, INK_RED,
                            sub=sub, sub_font=font_sm, width=2)
        inf_centers[title] = (IX + IW // 2, top + 44)

    # vLLM → ngrok
    draw_hand_drawn_arrow(draw,
                          (IX + IW // 2, 278),
                          (IX + IW // 2, 310),
                          INK_RED, width=2)

    # Try-On Agent → Try-On Image Backend
    ax, ay = agent_centers["Try-On Agent"]
    draw_hand_drawn_arrow(draw,
                          (ax + AW // 2, ay),
                          (IX, inf_centers["Try-On Image Backend"][1]),
                          INK_RED, width=2, wobble=2)

    # Meta Graph API → Messenger / IG (return webhooks)
    for client_y in [312, 412]:
        draw_hand_drawn_arrow(draw,
                              (IX, inf_centers["Meta Graph API"][1]),
                              (360, client_y),
                              INK_ORANGE, width=2, wobble=2)

    # LLM Planner → vLLM
    px, py = pipe_centers.get("LLM Planner Agent", (BX + BW // 2, 430))
    draw_hand_drawn_arrow(draw,
                          (BX + BW, py),
                          (IX, inf_centers["vLLM Server"][1]),
                          INK_RED, width=2, wobble=2)

    # ══════════════════════════════════════════
    # CLIENT → Backend arrows
    # ══════════════════════════════════════════
    draw_hand_drawn_arrow(draw, (360, 205), (BX, 200), INK_BLUE, width=2)
    draw_label(draw, "HTTPS/REST", 398, 192, font_tiny, INK_BLUE)

    draw_hand_drawn_arrow(draw, (360, 312), (BX, 240), INK_BLUE, width=2)
    draw_label(draw, "Webhook POST", 398, 302, font_tiny, INK_BLUE)

    draw_hand_drawn_arrow(draw, (360, 412), (BX, 260), INK_BLUE, width=2)

    draw_hand_drawn_arrow(draw, (360, 557), (BX, 280), INK_ORANGE, width=2)
    draw_label(draw, "MCP / OpenAI API", 382, 545, font_tiny, INK_ORANGE)

    # ══════════════════════════════════════════
    # Session History store  (left mid-bottom)
    # ══════════════════════════════════════════
    HX, HY = 80, 900
    draw_box_with_label(draw, HX, HY, 280, 90,
                        "Session History", font_md, INK_PURPLE,
                        sub="Redis / Supabase", sub_font=font_sm, width=2)

    draw_hand_drawn_arrow(draw,
                          (BX, 310),
                          (HX + 280, HY + 45),
                          INK_PURPLE, width=1, wobble=2)
    draw_label(draw, "ctx fetch", 340, 620, font_tiny, INK_PURPLE)

    # ══════════════════════════════════════════
    # LEGEND  (bottom-left)
    # ══════════════════════════════════════════
    LX, LY = 80, 1080
    draw_wobbly_line(draw, (LX, LY), (LX + 500, LY), INK_CHARCOAL, width=1)
    draw_label(draw, "LEGEND", LX + 4, LY + 20, font_lg, INK_CHARCOAL, anchor="lm")

    legend_items = [
        (INK_BLUE,   "Web / Client layer"),
        (INK_GREEN,  "FastAPI backend pipeline"),
        (INK_PURPLE, "Agents, DBs & storage"),
        (INK_RED,    "Inference / Try-On services"),
        (INK_ORANGE, "External agents & webhooks"),
    ]
    for i, (col, label) in enumerate(legend_items):
        lx = LX + 8
        ly = LY + 60 + i * 46
        draw_wobbly_line(draw, (lx, ly), (lx + 36, ly), col, width=3, wobble=1)
        draw_label(draw, label, lx + 50, ly, font_md, INK_CHARCOAL, anchor="lm")

    # ══════════════════════════════════════════
    # Notes / annotations  (bottom-right)
    # ══════════════════════════════════════════
    NX, NY = 1700, 1080
    draw_wobbly_line(draw, (NX, NY), (NX + 620, NY), INK_CHARCOAL, width=1)
    draw_label(draw, "NOTES", NX, NY + 20, font_lg, INK_CHARCOAL, anchor="lm")
    notes = [
        "* All agent calls are async, streamed over SSE.",
        "* Parallel DAG Executor fans-out to specialist agents.",
        "* Try-On pipeline: agent -> vLLM -> ngrok -> image backend.",
        "* FB/IG webhooks verified via Meta Graph API secret.",
        "* Pinecone used for semantic product / FAQ retrieval.",
        "* Supabase RLS policies enforce per-session data isolation.",
    ]
    for i, note in enumerate(notes):
        draw_label(draw, note, NX + 4, NY + 62 + i * 38, font_sm, INK_GRAY, anchor="lm")

    # ══════════════════════════════════════════
    # Bottom border
    # ══════════════════════════════════════════
    draw_wobbly_line(draw, (80, H - 45), (W - 80, H - 45), INK_CHARCOAL, width=2, wobble=1)
    draw_label(draw, "SmartShop  |  Agentic Architecture  |  Confidential",
               W // 2, H - 22, font_sm, INK_GRAY)

    return img


# ─────────────────────────────────────────────
# Output paths
# ─────────────────────────────────────────────
OUTPUT_PATHS = [
    "report/assets/architecture_diagram.png",
    "typst_proposal/images/architecture_diagram.png",
    "latex_proposal/images/architecture_diagram.png",
]

if __name__ == "__main__":
    diagram = build_diagram()

    base = "/home/ujjwal/codeagent/new/agentic_ecommerce_project"
    for rel in OUTPUT_PATHS:
        dest = os.path.join(base, rel)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        diagram.save(dest, dpi=(150, 150))
        print(f"Saved -> {dest}")
