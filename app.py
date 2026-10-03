import os
import time
import streamlit as st
from PIL import Image

# Import Google GenAI SDK safely
try:
    from google import genai
    NEW_SDK = True
except ModuleNotFoundError:
    try:
        import google.generativeai as genai
        NEW_SDK = False
    except ModuleNotFoundError:
        st.error("Google GenAI SDK is not installed. Please check your requirements.txt file.")
        st.stop()

# Streamlit Page Setup
st.set_page_config(page_title="AI Fashion Stylist", layout="wide")

# Initialize Persistent Session State
if "model_photos" not in st.session_state:
    st.session_state["model_photos"] = {}  # Store {'front': PIL.Image, 'left': ..., 'right': ..., 'back': ...}
if "wardrobe_items" not in st.session_state:
    st.session_state["wardrobe_items"] = []  # Store [{'image': PIL.Image, 'category': str, 'description': str}]
if "saved_outfits" not in st.session_state:
    st.session_state["saved_outfits"] = []
if "generated_outfits" not in st.session_state:
    st.session_state["generated_outfits"] = []

st.title("👗 AI Fashion Stylist & Virtual Try-On")

# Helper function to call Gemini with retries and fallback
def call_gemini_vision(contents, api_key):
    models_to_try = ['gemini-3.8-flash', 'gemini-3.7-flash', 'gemini-3.6-flash']
    last_err = None
    
    for model_name in models_to_try:
        for _ in range(2):
            try:
                if NEW_SDK:
                    client = genai.Client(api_key=api_key)
                    response = client.models.generate_content(
                        model=model_name,
                        contents=contents
                    )
                    return response.text
                else:
                    genai.configure(api_key=api_key)
                    model = genai.GenerativeModel(model_name)
                    response = model.generate_content(contents)
                    return response.text
            except Exception as e:
                last_err = e
                if "503" in str(e) or "UNAVAILABLE" in str(e) or "HIGH_DEMAND" in str(e):
                    time.sleep(1.5)
                    continue
                else:
                    raise e
    raise last_err or Exception("All model endpoints busy. Please try again.")

# Sidebar Configuration
st.sidebar.header("🔑 API Settings")
api_key = st.sidebar.text_input("Google AI Studio API Key:", type="password")

st.sidebar.markdown("---")
st.sidebar.header("1. Model Configuration")
headgear_style = st.sidebar.radio("Headgear Style:", ["Turban", "Cap", "Beanie"])

# 4-Angle Model Photo Upload
st.sidebar.subheader("Model Angle Photos (Persistent)")
angles = ["Front", "Left Profile", "Right Profile", "Back"]

for angle in angles:
    key_str = angle.lower().replace(" ", "_")
    
    if key_str in st.session_state["model_photos"]:
        col_img, col_del = st.sidebar.columns([3, 1])
        with col_img:
            st.caption(f"✓ {angle} Photo Saved")
        with col_del:
            if st.button("🗑️", key=f"del_model_{key_str}"):
                del st.session_state["model_photos"][key_str]
                st.rerun()
    else:
        uploaded_file = st.sidebar.file_uploader(f"Upload {angle} view:", type=["jpg", "jpeg", "png"], key=f"upload_{key_str}")
        if uploaded_file:
            st.session_state["model_photos"][key_str] = Image.open(uploaded_file)
            st.rerun()

st.sidebar.markdown("---")
st.sidebar.header("2. Wardrobe & Outfit Options")
source_mode = st.sidebar.radio("Outfit Source:", ["Online Shopping (Amazon/Web)", "My Wardrobe"])
batch_count = st.sidebar.radio("Number of Outfits:", [5, 10])

# Wardrobe Upload Section
if source_mode == "My Wardrobe":
    st.sidebar.subheader("Upload Wardrobe Items")
    new_wardrobe_files = st.sidebar.file_uploader(
        "Upload Clothing/Accessories:", 
        type=["jpg", "jpeg", "png"], 
        accept_multiple_files=True,
        key="wardrobe_uploader"
    )
    
    if new_wardrobe_files and api_key:
        if st.sidebar.button("⚡ Categorize New Items"):
            with st.spinner("AI is analyzing and categorizing wardrobe photos..."):
                for w_file in new_wardrobe_files:
                    img = Image.open(w_file)
                    cat_prompt = [
                        img, 
                        "Analyze this fashion item image. Return ONLY a single line formatted as: 'Category: Brief Description' (e.g., 'Tops: Oversized Navy Blue Cotton T-Shirt')."
                    ]
                    try:
                        analysis = call_gemini_vision(cat_prompt, api_key)
                        st.session_state["wardrobe_items"].append({
                            "image": img,
                            "info": analysis.strip()
                        })
                    except Exception as e:
                        st.sidebar.error(f"Failed to analyze image: {str(e)}")
            st.rerun()

# Generation Action
if st.sidebar.button("✨ Generate Outfits", type="primary"):
    if not api_key:
        st.error("Please enter your Google AI Studio API Key.")
    elif "front" not in st.session_state["model_photos"]:
        st.error("Please at least upload the Front model photo before generating.")
    else:
        with st.spinner(f"Curating {batch_count} outfits..."):
            prompt_parts = []
            
            # Append available model angles
            prompt_parts.append("Here are the model photos from available angles:")
            for angle_name, img in st.session_state["model_photos"].items():
                prompt_parts.append(f"Angle: {angle_name}")
                prompt_parts.append(img)

            # Append categorized wardrobe items if selected
            if source_mode == "My Wardrobe" and st.session_state["wardrobe_items"]:
                prompt_parts.append("\nUser's Wardrobe Inventory:")
                for idx, w_item in enumerate(st.session_state["wardrobe_items"]):
                    prompt_parts.append(f"Item #{idx+1}: {w_item['info']}")
            
            # Instructions
            instructions = f"""
            Act as a personal fashion stylist. Generate {batch_count} complete outfit recommendations suitable for the model wearing a {headgear_style}.
            Outfit Source Mode: {source_mode}.
            
            Requirements:
            - Analyze the model's structure/style from all provided photos (Front, Left, Right, Back).
            - Output itemized outfit breakdowns (Top, Bottom, Shoes, Accessories, Color Coordination).
            - Ensure headgear color harmonizes with each outfit.
            """
            prompt_parts.append(instructions)
            
            try:
                outfits_text = call_gemini_vision(prompt_parts, api_key)
                st.session_state["generated_outfits"] = [o.strip() for o in outfits_text.split("\n\n") if o.strip()]
                st.success("Outfits generated successfully!")
            except Exception as e:
                st.error(f"Error generating outfits: {str(e)}")

# MAIN DASHBOARD

# Section 1: Saved Model Angles Preview
st.header("👤 Model Angles Gallery")
m_cols = st.columns(4)
for idx, angle in enumerate(angles):
    k = angle.lower().replace(" ", "_")
    with m_cols[idx]:
        st.caption(f"**{angle} View**")
        if k in st.session_state["model_photos"]:
            st.image(st.session_state["model_photos"][k], use_container_width=True)
            if st.button(f"Delete {angle}", key=f"main_del_model_{k}"):
                del st.session_state["model_photos"][k]
                st.rerun()
        else:
            st.info("Not uploaded")

# Section 2: Wardrobe Gallery
if source_mode == "My Wardrobe":
    st.markdown("---")
    st.header("👔 Categorized Wardrobe")
    if st.session_state["wardrobe_items"]:
        w_cols = st.columns(4)
        for w_idx, item in enumerate(st.session_state["wardrobe_items"]):
            col_target = w_cols[w_idx % 4]
            with col_target:
                st.image(item["image"], use_container_width=True)
                st.caption(item["info"])
                if st.button(f"Remove Item #{w_idx+1}", key=f"del_w_{w_idx}"):
                    st.session_state["wardrobe_items"].pop(w_idx)
                    st.rerun()
    else:
        st.write("No wardrobe items categorized yet. Upload photos in the sidebar and click 'Categorize New Items'.")

# Section 3: Generated Outfits
st.markdown("---")
st.header("✨ Curated Outfits")
if st.session_state["generated_outfits"]:
    for idx, outfit_text in enumerate(st.session_state["generated_outfits"]):
        with st.expander(f"Outfit Concept #{idx + 1}", expanded=True):
            st.write(outfit_text)
            
            c1, c2 = st.columns([1, 1])
            with c1:
                if st.button(f"💾 Save Outfit #{idx + 1}", key=f"save_{idx}"):
                    if outfit_text not in st.session_state["saved_outfits"]:
                        st.session_state["saved_outfits"].append(outfit_text)
                        st.toast("Saved to Closet!")
            with c2:
                if st.button(f"🗑️ Delete Outfit #{idx + 1}", key=f"del_out_{idx}"):
                    st.session_state["generated_outfits"].pop(idx)
                    st.rerun()

# Section 4: Saved Closet
st.markdown("---")
st.header("🔒 Saved Closet")
if st.session_state["saved_outfits"]:
    for s_idx, item in enumerate(st.session_state["saved_outfits"]):
        st.info(f"**Saved Look #{s_idx + 1}:**\n\n{item}")
else:
    st.write("No saved outfits yet.")
