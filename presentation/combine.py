#!/usr/bin/env python3
import subprocess
import os
from pypdf import PdfWriter

def run_cmd(cmd):
    print(f"Running: {cmd}")
    res = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if res.returncode != 0:
        print(f"ERROR: {res.stderr}")
        raise RuntimeError(f"Command failed: {cmd}")
    print(res.stdout)

def main():
    base_dir = "/home/ujjwal/codeagent/new/agentic_ecommerce_project"
    typst_bin = "/home/ujjwal/.gemini/antigravity-ide/scratch/typst"
    
    # 1. Generate the architecture diagram first so engine.typ can render it
    # print("Generating system architecture diagram...")
    # run_cmd(f"python3 {base_dir}/generate_architecture_diagram.py")
    
    # Define files to compile
    presentation_files = [
        ("engine/engine.typ", "engine/engine.pdf"),
        ("finetuning/finetuning.typ", "finetuning/finetuning.pdf"),
        ("integration/integration.typ", "integration/integration.pdf"),
        ("middleware_observability_guardrails_rag/middleware.typ", "middleware_observability_guardrails_rag/middleware.pdf")
    ]
    
    pres_dir = f"{base_dir}/presentation/presentation_1"
    
    # 2. Compile each presentation Typst file to PDF
    compiled_pdfs = []
    for rel_typ, rel_pdf in presentation_files:
        typ_path = os.path.join(pres_dir, rel_typ)
        pdf_path = os.path.join(pres_dir, rel_pdf)
        
        # Ensure directories exist
        os.makedirs(os.path.dirname(pdf_path), exist_ok=True)
        
        print(f"Compiling {rel_typ} to PDF...")
        run_cmd(f"{typst_bin} compile --root {base_dir} {typ_path} {pdf_path}")
        compiled_pdfs.append(pdf_path)
        
    # 3. Merge all PDFs using pypdf
    merger = PdfWriter()
    for pdf in compiled_pdfs:
        print(f"Merging: {pdf}")
        merger.append(pdf)
        
    output_combined = f"{base_dir}/presentation/presentation_1_combined.pdf"
    merger.write(output_combined)
    merger.close()
    
    print(f"SUCCESS: Combined presentation created at: {output_combined}")

if __name__ == "__main__":
    main()
