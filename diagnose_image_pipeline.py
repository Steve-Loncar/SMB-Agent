#!/usr/bin/env python3
"""
Quick diagnostic script to check image hunt pipeline status
Run from workspace root: python diagnose_image_pipeline.py
"""

import json
import sys
from pathlib import Path

def check_backend_files():
    """Verify critical backend files exist"""
    print("=" * 60)
    print("1️⃣  BACKEND FILES CHECK")
    print("=" * 60)
    
    files_to_check = {
        "backend/n8n_client.py": "n8n webhook communication",
        "backend/state.py": "session state management",
        "pages/02_results.py": "results page with image pipeline",
        "prompts/": "system/user prompts for workflows"
    }
    
    for path, desc in files_to_check.items():
        p = Path(path)
        exists = "✅" if p.exists() else "❌"
        print(f"{exists} {path} ({desc})")
    
    print()

def check_workflows():
    """Verify n8n workflow files exist"""
    print("=" * 60)
    print("2️⃣  N8N WORKFLOW FILES CHECK")
    print("=" * 60)
    
    workflows = {
        "SMB_tier1_summariser.json": "Page analysis → asset_candidates",
        "SMB_Image_hunt.json": "Image enrichment → visual_pack",
        "smb_image_gen.json": "Poster generation (image-selection, prompt-gen, image-render)"
    }
    
    workflow_dir = Path("workflows/fpgconsulting_cloud_steve_l/my_project")
    
    for wf_name, desc in workflows.items():
        wf_path = workflow_dir / wf_name
        exists = "✅" if wf_path.exists() else "❌"
        print(f"{exists} {wf_name} ({desc})")
        
        if exists == "✅":
            try:
                with open(wf_path) as f:
                    data = json.load(f)
                    node_count = len(data.get("nodes", []))
                    print(f"   └─ Nodes: {node_count}")
            except Exception as e:
                print(f"   └─ ⚠️  Error reading: {e}")
    
    print()

def check_prompts():
    """Verify prompt files for pipeline"""
    print("=" * 60)
    print("3️⃣  PROMPT FILES CHECK")
    print("=" * 60)
    
    prompts = {
        "smb_tier1_summarise_system.txt": "Page analysis system prompt",
        "smb_image_hunt_system.txt": "Image hunt system prompt",
        "smb_poster_gen_system.txt": "Poster generation system prompt"
    }
    
    for prompt_file, desc in prompts.items():
        p = Path(f"prompts/{prompt_file}")
        exists = "✅" if p.exists() else "❌"
        size = f"({p.stat().st_size} bytes)" if exists == "✅" else ""
        print(f"{exists} {prompt_file} ({desc}) {size}")
    
    print()

def check_n8n_client():
    """Check critical functions in n8n_client.py"""
    print("=" * 60)
    print("4️⃣  N8N CLIENT FUNCTIONS CHECK")
    print("=" * 60)
    
    try:
        with open("backend/n8n_client.py") as f:
            content = f.read()
            
        functions = {
            "call_n8n_tier1_summarise": "Runs page analysis",
            "call_n8n_image_hunt": "Runs image enrichment",
            "call_n8n_generate_poster": "Generates poster images"
        }
        
        for func_name, desc in functions.items():
            exists = "✅" if f"def {func_name}" in content else "❌"
            print(f"{exists} {func_name}() - {desc}")
            
            if exists == "✅" and "call_n8n_generate_poster" in func_name:
                if "poster_concept" in content and "guidelines" in content:
                    print("   └─ ✅ All required fields in payload (poster_concept, guidelines, etc.)")
                else:
                    print("   └─ ⚠️  Missing fields in payload!")
        
    except Exception as e:
        print(f"❌ Error reading n8n_client.py: {e}")
    
    print()

def check_results_page():
    """Check results page for image handling"""
    print("=" * 60)
    print("5️⃣  RESULTS PAGE LOGIC CHECK")
    print("=" * 60)
    
    try:
        with open("pages/02_results.py", encoding="utf-8", errors="ignore") as f:
            content = f.read()
        
        checks = {
            "asset_candidates": "Asset candidates tracking",
            "visual_pack": "Enriched images tracking",
            "poster_visual_images": "Poster image selection",
            "can_run_image_hunt": "Image hunt enablement logic",
            "Re-run Page Analysis": "Recovery button for missing images"
        }
        
        for check, desc in checks.items():
            exists = "✅" if check in content else "❌"
            print(f"{exists} {check} - {desc}")
        
    except Exception as e:
        print(f"❌ Error reading pages/02_results.py: {e}")
    
    print()

def main():
    print("\n🔍 SMB IMAGE HUNT PIPELINE DIAGNOSTIC\n")
    
    check_backend_files()
    check_workflows()
    check_prompts()
    check_n8n_client()
    check_results_page()
    
    print("=" * 60)
    print("✅ DIAGNOSTIC COMPLETE")
    print("=" * 60)
    print("\n📝 NEXT STEPS:")
    print("1. Run app.py and test on a sample website")
    print("2. Check browser console for errors")
    print("3. Review n8n cloud console if workflows fail")
    print("4. Check IMAGE_HUNT_FLOW_ANALYSIS.md for detailed troubleshooting")
    print()

if __name__ == "__main__":
    main()
