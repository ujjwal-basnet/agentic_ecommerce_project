import os
from PIL import Image, ImageDraw, ImageFont, ImageChops

def get_fonts(font_size_reg=24, font_size_bold=28):
    font_dir = "/usr/share/fonts/truetype/liberation"
    reg_font_path = os.path.join(font_dir, "LiberationSans-Regular.ttf")
    bold_font_path = os.path.join(font_dir, "LiberationSans-Bold.ttf")
    
    if os.path.exists(reg_font_path) and os.path.exists(bold_font_path):
        return (
            ImageFont.truetype(reg_font_path, font_size_reg),
            ImageFont.truetype(bold_font_path, font_size_bold)
        )
    else:
        # Fallback to default
        return ImageFont.load_default(), ImageFont.load_default()

def draw_stick_figure(draw, cx, cy, label, reg_font):
    # Head
    draw.ellipse((cx - 25, cy - 60, cx + 25, cy - 10), outline="black", width=5)
    # Body
    draw.line((cx, cy - 10, cx, cy + 50), fill="black", width=5)
    # Arms
    draw.line((cx - 40, cy + 10, cx + 40, cy + 10), fill="black", width=5)
    # Legs
    draw.line((cx, cy + 50, cx - 30, cy + 100), fill="black", width=5)
    draw.line((cx, cy + 50, cx + 30, cy + 100), fill="black", width=5)
    
    # Label
    text_bbox = draw.textbbox((0, 0), label, font=reg_font)
    tw = text_bbox[2] - text_bbox[0]
    draw.text((cx - tw // 2, cy + 115), label, fill="black", font=reg_font)

def draw_ellipse_usecase(draw, cx, cy, text, reg_font):
    w, h = 420, 110
    draw.ellipse(
        (cx - w//2, cy - h//2, cx + w//2, cy + h//2),
        fill=(235, 245, 255),
        outline=(70, 130, 180),
        width=4
    )
    
    # Split text by newline or word wrap if too long
    words = text.split(" ")
    lines = []
    current_line = []
    for word in words:
        current_line.append(word)
        line_str = " ".join(current_line)
        bbox = draw.textbbox((0, 0), line_str, font=reg_font)
        if bbox[2] - bbox[0] > w - 40:
            current_line.pop()
            lines.append(" ".join(current_line))
            current_line = [word]
    if current_line:
        lines.append(" ".join(current_line))
        
    total_h = sum([draw.textbbox((0, 0), l, font=reg_font)[3] - draw.textbbox((0, 0), l, font=reg_font)[1] for l in lines]) + 8 * (len(lines) - 1)
    
    curr_y = cy - total_h // 2
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=reg_font)
        lw = bbox[2] - bbox[0]
        lh = bbox[3] - bbox[1]
        draw.text((cx - lw // 2, curr_y - 2), line, fill=(33, 33, 33), font=reg_font)
        curr_y += lh + 8

def generate_use_case():
    w, h = 1842, 2674
    img = Image.new("RGB", (w, h), "white")
    draw = ImageDraw.Draw(img)
    
    reg_font, bold_font = get_fonts(28, 36)
    title_font = get_fonts(40, 48)[1]
    
    # Draw boundary box
    draw.rectangle((350, 100, 1500, 2580), outline="black", width=6)
    draw.text((380, 130), "SmartShop - System Boundary", fill="black", font=title_font)
    
    # Draw actors
    # Customer (left)
    draw_stick_figure(draw, 180, 1200, "Customer", bold_font)
    # Merchant (right top)
    draw_stick_figure(draw, 1670, 600, "Merchant / Owner", bold_font)
    # LLM Planner (right middle)
    draw_stick_figure(draw, 1670, 1400, "LLM Planner", bold_font)
    # Payment Gateway (right bottom)
    draw_stick_figure(draw, 1670, 2100, "Payment Gateway", bold_font)
    
    # Use cases: Customer Column (cx = 640)
    c_ucs = [
        (1, "Register / Login", 280),
        (2, "Browse / Search Products", 530),
        (3, "Chat with Shopping Agent", 780),
        (4, "Add to Cart & Checkout", 1030),
        (5, "Track Order Status", 1280),
        (6, "Leave Product Reviews", 1530),
        (7, "Logout", 1780)
    ]
    
    # Use cases: Merchant Column (cx = 1200)
    m_ucs = [
        (8, "Merchant Login", 280),
        (9, "View Sales Analytics", 530),
        (10, "Manage Product Inventory", 780),
        (11, "Configure LLM Prompts", 1030),
        (12, "Design & Launch campaigns", 1280),
        (13, "Manage Customer Orders", 1530)
    ]
    
    # System Internal UCs (cx = 920)
    sys_ucs = [
        (14, "Rewrite Search Queries", 1030),
        (15, "Generate Product Recommendations", 1280),
        (16, "Process Payments", 1880),
        (17, "Confirm Transaction", 2130)
    ]
    
    # Draw UCs
    for uc_id, txt, cy in c_ucs:
        draw_ellipse_usecase(draw, 640, cy, txt, reg_font)
    for uc_id, txt, cy in m_ucs:
        draw_ellipse_usecase(draw, 1200, cy, txt, reg_font)
    for uc_id, txt, cy in sys_ucs:
        draw_ellipse_usecase(draw, 920, cy, txt, reg_font)
        
    # Draw connections
    # Customer connections (from 180, 1200)
    customer_pos = (180, 1200)
    for uc_id, _, cy in c_ucs:
        draw.line((customer_pos[0] + 50, customer_pos[1] + 10, 640 - 210, cy), fill=(160, 160, 160), width=3)
        
    # Merchant connections (from 1670, 600)
    merchant_pos = (1670, 600)
    for uc_id, _, cy in m_ucs:
        draw.line((merchant_pos[0] - 50, merchant_pos[1] + 10, 1200 + 210, cy), fill=(160, 160, 160), width=3)
        
    # LLM Planner connections (from 1670, 1400)
    llm_pos = (1670, 1400)
    # Connects to Chat Agent (3), Configure Prompts (11), Rewrite (14), Recommend (15)
    draw.line((llm_pos[0] - 50, llm_pos[1] + 10, 640 + 210, 780), fill=(70, 130, 180), width=3)
    draw.line((llm_pos[0] - 50, llm_pos[1] + 10, 1200 - 210, 1030), fill=(70, 130, 180), width=3)
    draw.line((llm_pos[0] - 50, llm_pos[1] + 10, 920 + 210, 1030), fill=(70, 130, 180), width=3)
    draw.line((llm_pos[0] - 50, llm_pos[1] + 10, 920 + 210, 1280), fill=(70, 130, 180), width=3)
    
    # Payment Gateway connections (from 1670, 2100)
    pg_pos = (1670, 2100)
    # Connects to Add to Cart / Checkout (4), Process (16), Confirm (17)
    draw.line((pg_pos[0] - 50, pg_pos[1] + 10, 640 + 210, 1030), fill=(160, 120, 180), width=3)
    draw.line((pg_pos[0] - 50, pg_pos[1] + 10, 920 + 210, 1880), fill=(160, 120, 180), width=3)
    draw.line((pg_pos[0] - 50, pg_pos[1] + 10, 920 + 210, 2130), fill=(160, 120, 180), width=3)
    
    return img

def generate_gantt():
    w, h = 1430, 360
    img = Image.new("RGB", (w, h), "white")
    draw = ImageDraw.Draw(img)
    
    reg_font, bold_font = get_fonts(16, 18)
    
    # Draw table outline
    draw.rectangle((20, 20, 1410, 340), outline="black", width=2)
    
    # Vertical grid lines
    # ID column: width 50
    # Task Name column: width 280
    # Timeline starts at 350
    draw.line((70, 20, 70, 340), fill="black", width=2)
    draw.line((350, 20, 350, 340), fill="black", width=2)
    
    # Horizontal grid line for header
    draw.line((20, 60, 1410, 60), fill="black", width=2)
    
    # Write headers
    draw.text((35, 30), "ID", fill="black", font=bold_font)
    draw.text((90, 30), "Task Name", fill="black", font=bold_font)
    
    # Draw timeline columns (Jan 2026 to July 2026)
    months = [
        ("2026-01", 4), ("2026-02", 4), ("2026-03", 4),
        ("2026-04", 4), ("2026-05", 4), ("2026-06", 4), ("2026-07", 3)
    ]
    
    total_timeline_w = 1410 - 350
    col_w = total_timeline_w / 27 # 27 weeks total
    
    curr_x = 350
    week_idx = 0
    
    # Grid lines and headers for months
    for month_name, num_weeks in months:
        # Month vertical boundary
        month_w = num_weeks * col_w
        draw.line((curr_x + month_w, 20, curr_x + month_w, 340), fill="black", width=2)
        
        # Month label
        draw.text((curr_x + 10, 30), month_name, fill="black", font=bold_font)
        
        # Draw weekly subdivisions
        for w_i in range(num_weeks):
            wx = curr_x + w_i * col_w
            # Vertical line for week
            draw.line((wx, 60, wx, 340), fill=(220, 220, 220), width=1)
            
            # Print a number for week
            week_label = f"{w_i * 7 + 1:02d}"
            draw.text((wx + 3, 62), week_label, fill="gray", font=reg_font)
            
        curr_x += month_w
        
    # Task list (ID, Name, Start week index, duration in weeks, color)
    tasks = [
        (1, "Requirement Elicitation", 0, 3, (100, 220, 100)), # light green
        (2, "Requirement Analysis", 2, 4, (50, 100, 250)),   # blue
        (3, "System Design & Prompts Setup", 5, 4, (150, 50, 200)), # purple
        (4, "Detailed Design & DB Bootstrap", 8, 4, (220, 50, 180)), # magenta
        (5, "FastAPI Backend & LLM Planner", 11, 8, (250, 50, 100)), # pink
        (6, "Next.js Storefronts (Customer/Owner)", 15, 8, (240, 220, 50)), # yellow
        (7, "Meta API Campaigns Integration", 20, 4, (250, 150, 50)), # orange
        (8, "System Integration, Testing & Deploy", 23, 4, (150, 100, 50)) # brown
    ]
    
    # Draw rows and bars
    row_h = 35
    for i, (tid, tname, start_w, dur_w, color) in enumerate(tasks):
        ry = 80 + i * row_h
        # Draw horizontal split line
        draw.line((20, ry + row_h, 1410, ry + row_h), fill=(200, 200, 200), width=1)
        
        # Write task values
        draw.text((35, ry + 8), str(tid), fill="black", font=reg_font)
        draw.text((90, ry + 8), tname, fill="black", font=reg_font)
        
        # Draw bar
        bx0 = 350 + start_w * col_w
        bx1 = bx0 + dur_w * col_w
        by0 = ry + 6
        by1 = ry + row_h - 6
        draw.rectangle((bx0, by0, bx1, by1), fill=color, outline="black", width=1)
        
    return img

def generate_waterfall():
    w, h = 600, 700
    img = Image.new("RGB", (w, h), "white")
    draw = ImageDraw.Draw(img)
    
    reg_font, bold_font = get_fonts(18, 22)
    
    # We want to draw steps going down:
    # 1. Requirement Elicitation (x=50, y=50)
    # 2. Requirement Analysis (x=100, y=130)
    # 3. System Design (x=150, y=210)
    # 4. Detailed Design & Prompts (x=200, y=290)
    # 5. Coding & LLM Testing (x=250, y=370)
    # 6. Meta Integration (x=300, y=450)
    # 7. Deployment & Evaluation (x=350, y=530)
    
    steps = [
        "Requirement Elicitation",
        "Requirement Analysis",
        "System Design",
        "Detailed Design & Prompts",
        "Coding & LLM Testing",
        "Meta Integration",
        "Deployment & Evaluation"
    ]
    
    box_w, box_h = 240, 60
    
    # Draw boxes
    for i, step in enumerate(steps):
        bx = 50 + i * 40
        by = 40 + i * 80
        
        # Draw shadow
        draw.rectangle((bx + 5, by + 5, bx + box_w + 5, by + box_h + 5), fill=(230, 230, 230))
        
        # Draw box
        draw.rectangle((bx, by, bx + box_w, by + box_h), fill=(245, 250, 255), outline=(70, 130, 180), width=3)
        
        # Text inside
        bbox = draw.textbbox((0, 0), step, font=reg_font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        draw.text((bx + (box_w - tw)//2, by + (box_h - th)//2 - 2), step, fill="black", font=reg_font)
        
        # Draw connecting arrow going down to next box
        if i < len(steps) - 1:
            # Arrow start: bottom of current box
            ax_start = bx + box_w // 2
            ay_start = by + box_h
            # Arrow end: top of next box
            ax_end = bx + 40 + box_w // 2
            ay_end = by + 80
            
            # Draw line with elbow
            draw.line((ax_start, ay_start, ax_start, ay_start + 15), fill="black", width=2)
            draw.line((ax_start, ay_start + 15, ax_end, ay_start + 15), fill="black", width=2)
            draw.line((ax_end, ay_start + 15, ax_end, ay_end), fill="black", width=2)
            
            # Arrow head
            draw.polygon([
                (ax_end, ay_end),
                (ax_end - 8, ay_end - 10),
                (ax_end + 8, ay_end - 10)
            ], fill="black")
            
        # Draw feedback arrow back up
        if i > 0:
            # Feed back from left edge of box back up to preceding box's left edge
            ay_src = by + box_h // 2
            ay_dst = (by - 80) + box_h // 2
            
            # Elbow coordinates (drawing a line sticking out left)
            lx = 25
            draw.line((bx, ay_src, lx, ay_src), fill=(150, 150, 150), width=2)
            draw.line((lx, ay_src, lx, ay_dst), fill=(150, 150, 150), width=2)
            draw.line((lx, ay_dst, bx - 40, ay_dst), fill=(150, 150, 150), width=2)
            
            # Arrow head pointing right into the target box
            draw.polygon([
                (bx - 40, ay_dst),
                (bx - 48, ay_dst - 6),
                (bx - 48, ay_dst + 6)
            ], fill=(150, 150, 150))
            
    return img

def main():
    print("Generating diagrams for SmartShop E-commerce Project...")
    
    usecase_img = generate_use_case()
    gantt_img = generate_gantt()
    waterfall_img = generate_waterfall()
    
    # Save target locations
    workspace_latex_dir = "/home/ujjwal/codeagent/new/agentic_ecommerce_project/latex_proposal/images"
    workspace_typst_dir = "/home/ujjwal/codeagent/new/agentic_ecommerce_project/typst_proposal/images"
    
    os.makedirs(workspace_latex_dir, exist_ok=True)
    os.makedirs(workspace_typst_dir, exist_ok=True)
    
    # Save to LaTeX folder
    usecase_img.save(os.path.join(workspace_latex_dir, "use_case_diagram.png"))
    gantt_img.save(os.path.join(workspace_latex_dir, "gantt_chart.png"))
    waterfall_img.save(os.path.join(workspace_latex_dir, "waterfall_model.png"))
    print("Saved custom diagrams to LaTeX folder.")
    
    # Save to Typst folder
    usecase_img.save(os.path.join(workspace_typst_dir, "use_case_diagram.png"))
    gantt_img.save(os.path.join(workspace_typst_dir, "gantt_chart.png"))
    waterfall_img.save(os.path.join(workspace_typst_dir, "waterfall_model.png"))
    print("Saved custom diagrams to Typst folder.")
    
if __name__ == "__main__":
    main()
