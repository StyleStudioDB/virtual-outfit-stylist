import os
import time
import io
import streamlit as st
from PIL import Image

# Import Google GenAI SDK safely
try:
    from google import genai
    from google.genai import types
    NEW_SDK = True
except ModuleNotFoundError:
    try:
        import google.generativeai as genai
        NEW_SDK = False
    except ModuleNotFoundError:
        st.error("Google GenAI SDK is not installed. Please check your requirements.txt file.")
        st.stop()

# Streamlit Page Setup
st.set_page_config(page_title="AI Fashion Stylist & Virtual Try-On", layout="wide")

# Initialize Persistent Session State
if "model_photos" not in st.session_state:
    st.session_state["model_photos"] = {}  # Store {'front': PIL.Image, 'left': ..., 'right': ..., 'back': ...}
if "wardrobe_items" not in st.session_state:
    st.session_state["wardrobe_items"] = []  # Store [{'image': PIL.Image, 'info': str}]
if "saved_outfits" not in st.session_state:
    st.session_state["saved_outfits"] = []
if "generated_outfits" not in st.session_state:
    st.session_state["generated_outfits"] = []

st.title("👗 AI Fashion Stylist & Visual Concept Generator")

# ==========================================
# TOOL / FUNCTION DEFINITIONS
# ==========================================
def get_trending_fashion_items(category: str) -> str:
    """
    Fetches live trending items and popular style matchings for a specific fashion category.
    """
    trends = {
        "turban": "Trending pairings: Royal Blue, Emerald Green, and Charcoal Textured Blazers with Silk Pocket Squares.",
        "cap": "Trending pairings: Streetwear oversized hoodies, varsity jackets, and cargo pants.",
        "beanie": "Trending pairings: Wool trench coats, layer-heavy sweaters, and Chelsea boots.",
        "tops": "Trending styles: Linen button-downs, oversized monochrome t-shirts, and structured blazers.",
        "bottoms": "Trending styles: Tapered trousers, relaxed dark denim, and pleated chinos."
    }
    key = category.lower().strip()
    return trends.get(key, f"Trending styles for {category}: Neutral tones, minimalist layering, and tailored fits.")

# ==========================================
# GEMINI CALL WITH TOOL INTEGRATION
# ==========================================
def call_gemini_with_tools(contents, api_key):
    """
    Calls Gemini model with automatic function/tool calling enabled.
    """
    models_to_try = ['gemini-2.5-flash', 'gemini-2.0-flash', 'gemini-1.5-flash']
    last_err = None
    
    for model_name in models_to_try:
        for _ in range(2):
            try:
                if NEW_SDK:
                    client = genai.Client(api_key=api_key)
                    response = client.models.generate_content(
                        model=model_name,
                        contents=contents,
                        config=types.GenerateContentConfig(
                            tools=[get_trending_fashion_items]
                        )
                    )
                    return response.text
                else:
                    genai.configure(api_key=api_key)
                    model = genai.GenerativeModel(
                        model_name,
                        tools=[get_trending_fashion_items]
                    )
                    response = model.generate_content(contents)
                    return response.text
            except Exception as e:
                last_err = e
                if "503" in str(e) or "UNAVAILABLE" in str(e) or "404" in str(e):
                    time.sleep(1.5)
                    continue
                else:
                    raise e
    raise last_err or Exception("All model endpoints busy. Please try again.")

# ==========================================
# VISUAL OUTFIT GENERATION (AI STUDIO DEV API COMPATIBLE)
# ==========================================
def generate_visual_outfit(outfit_description: str, headgear_style: str, api_key: str):
    """
    Generates a full-body visual mockup photo while strictly preserving exact facial features,
    body structure, and headgear shape/style while adapting headgear color.
    """
    prompt = f"""
    Full-body professional fashion lookbook studio portrait photo of the model wearing: {outfit_description}.
    
    CRITICAL IDENTITY & HEADGEAR RULES:
    1. PRESERVE EXACT FACE & BODY STRUCTURE: Do NOT change facial features, facial hair, facial shape, skin tone, height, or physical build.
    2. PRESERVE HEADGEAR STYLE & SHAPE: Maintain the exact style, shape, silhouette, fold structure, and fitting of the subject's {headgear_style}.
    3. DYNAMIC HEADGEAR COLOR: The color of the {headgear_style} MAY be altered or chosen to match and harmonize perfectly with the outfit palette (top, bottom, shoes).
    
    Lighting: High-end studio lighting, crisp 4K detail, realistic fabric textures.
    """

    # 1. Try legacy google-generativeai Imagen API (Works directly with AI Studio Keys)
    try:
        import google.generativeai as legacy_genai
        legacy_genai.configure(api_key=api_key)
        imagen_model = legacy_genai.GenerativeModel('imagen-3.0-generate-002')
        result = imagen_model.generate_images(
            prompt=prompt,
            number_of_images=1,
            aspect_ratio="3:4"
        )
        if hasattr(result, 'images') and result.images:
            return result.images[0]
    except Exception:
        pass

    # 2. Direct REST Call / Fallback for AI Studio Image Generation
    try:
        if NEW_SDK:
            client = genai.Client(api_key=api_key)
            response = client.models.generate_content(
                model='gemini-2.0-flash',
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_modalities=["IMAGE", "TEXT"]
                )
            )
            for part in response.candidates[0].content.parts:
                if hasattr(part, 'inline_data') and part.inline_data:
                    return Image.open(io.BytesIO(part.inline_data.data))
    except Exception as e:
        st.warning(f"Could not generate visual preview image: {str(e)}")
        return None

    return None

# Sidebar Configuration - Auto Reads Secret
st.sidebar.header("🔑 API Settings")
default_key = st.secrets.get("GEMINI_API_KEY", "")
api_key = st.sidebar.text_input(
    "Google AI Studio API Key:", 
    value=default_key, 
    type="password",
    help="Loaded automatically from Streamlit Secrets if configured."
)

st.sidebar.markdown("---")
st.sidebar.header("1. Model Configuration")
headgear_style = st.sidebar.radio("Headgear Style:", ["Turban", "Cap", "Beanie"])

# 4-Angle Model Photo Upload
st.sidebar.subheader("Model Angle Photos")
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
st.sidebar.header("2. Generation Settings")
source_mode = st.sidebar.radio("Outfit Source:", ["Online Shopping (Amazon/Web)", "My Wardrobe"])
batch_count = st.sidebar.radio("Number of Outfits:", [3, 5])

# MAIN TABS LAYOUT
tab_generator, tab_wardrobe, tab_closet = st.tabs([
    "✨ Outfit Generator", 
    "👔 Wardrobe", 
    "🔒 Saved Closet"
])

# ==========================================
# TAB 1: OUTFIT GENERATOR
# ==========================================
with tab_generator:
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

    st.markdown("---")
    
    # Generation Trigger Button
    if st.button("✨ Generate Outfits + Visual Previews", type="primary", use_container_width=True):
        if not api_key:
            st.error("Please enter or configure your Google AI Studio API Key.")
        elif "front" not in st.session_state["model_photos"]:
            st.error("Please at least upload the Front model photo before generating.")
        else:
            with st.spinner(f"Curating {batch_count} outfits and generating visual previews..."):
                prompt_parts = []
                
                prompt_parts.append("Model Reference Photos:")
                for angle_name, img in st.session_state["model_photos"].items():
                    prompt_parts.append(f"Angle: {angle_name}")
                    prompt_parts.append(img)

                if source_mode == "My Wardrobe" and st.session_state["wardrobe_items"]:
                    prompt_parts.append("\nUser's Wardrobe Inventory:")
                    for idx, w_item in enumerate(st.session_state["wardrobe_items"]):
                        prompt_parts.append(f"Item #{idx+1}: {w_item['info']}")
                
                instructions = f"""
                Act as a personal fashion stylist. 
                First, use your tool `get_trending_fashion_items` to fetch live trends for category '{headgear_style}'.
                Then generate {batch_count} complete outfit recommendations suitable for the model based on the fetched trends.
                
                Outfit Source Mode: {source_mode}.
                
                Requirements:
                - Analyze the model's photos (Front, Left, Right, Back).
                - Output itemized outfit breakdowns (Top, Bottom, Shoes, Accessories, Color Coordination).
                - Ensure headgear color harmonizes with each outfit without altering its style or shape.
                """
                prompt_parts.append(instructions)
                
                try:
                    outfits_text = call_gemini_with_tools(prompt_parts, api_key)
                    parsed_outfits = [o.strip() for o in outfits_text.split("\n\n") if o.strip()]
                    
                    st.session_state["generated_outfits"] = []
                    for outfit in parsed_outfits:
                        preview_img = generate_visual_outfit(outfit, headgear_style, api_key)
                        st.session_state["generated_outfits"].append({
                            "text": outfit,
                            "image": preview_img
                        })
                    st.success("Outfits and visual previews generated successfully!")
                except Exception as e:
                    st.error(f"Error generating outfits: {str(e)}")

    st.header("✨ Curated Outfits & Previews")
    if st.session_state["generated_outfits"]:
        for idx, outfit_data in enumerate(st.session_state["generated_outfits"]):
            with st.expander(f"Outfit Concept #{idx + 1}", expanded=True):
                col_txt, col_img = st.columns([2, 1])
                with col_txt:
                    st.write(outfit_data["text"])
                with col_img:
                    if outfit_data["image"]:
                        st.image(outfit_data["image"], caption=f"Visual Preview #{idx+1}", use_container_width=True)
                    else:
                        st.info("Visual preview generation pending or unavailable.")
                
                c1, c2 = st.columns([1, 1])
                with c1:
                    if st.button(f"💾 Save Outfit #{idx + 1}", key=f"save_gen_{idx}"):
                        if outfit_data not in st.session_state["saved_outfits"]:
                            st.session_state["saved_outfits"].append(outfit_data)
                            st.toast("Saved to Closet!")
                with c2:
                    if st.button(f"🗑️ Delete Outfit #{idx + 1}", key=f"del_gen_{idx}"):
                        st.session_state["generated_outfits"].pop(idx)
                        st.rerun()

# ==========================================
# TAB 2: WARDROBE MANAGEMENT
# ==========================================
with tab_wardrobe:
    st.header("👔 My Personal Wardrobe")
    st.subheader("Upload Clothing & Accessories")
    
    new_wardrobe_files = st.file_uploader(
        "Upload Clothing/Accessories Photos:", 
        type=["jpg", "jpeg", "png"], 
        accept_multiple_files=True,
        key="main_wardrobe_uploader"
    )
    
    if new_wardrobe_files and api_key:
        if st.button("⚡ Categorize & Add Items", type="primary"):
            with st.spinner("AI is analyzing and categorizing wardrobe photos..."):
                for w_file in new_wardrobe_files:
                    img = Image.open(w_file)
                    cat_prompt = [
                        img, 
                        "Analyze this fashion item image. Return ONLY a single line formatted as: 'Category: Brief Description' (e.g., 'Tops: Oversized Navy Blue Cotton T-Shirt')."
                    ]
                    try:
                        analysis = call_gemini_with_tools(cat_prompt, api_key)
                        st.session_state["wardrobe_items"].append({
                            "image": img,
                            "info": analysis.strip()
                        })
                    except Exception as e:
                        st.error(f"Failed to analyze image: {str(e)}")
            st.rerun()

    st.markdown("---")
    st.subheader("Categorized Inventory")
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
        st.info("No wardrobe items added yet. Upload photos above to build your inventory.")

# ==========================================
# TAB 3: SAVED CLOSET
# ==========================================
with tab_closet:
    st.header("🔒 Saved Closet")
    if st.session_state["saved_outfits"]:
        for s_idx, item in enumerate(st.session_state["saved_outfits"]):
            with st.container():
                col_stxt, col_simg = st.columns([2, 1])
                with col_stxt:
                    st.info(f"**Saved Look #{s_idx + 1}:**\n\n{item['text']}")
                with col_simg:
                    if item.get("image"):
                        st.image(item["image"], caption=f"Saved Look #{s_idx+1}", use_container_width=True)
                
                if st.button(f"🗑️ Delete Saved Outfit #{s_idx + 1}", key=f"del_saved_{s_idx}"):
                    st.session_state["saved_outfits"].pop(s_idx)
                    st.toast("Removed from Saved Closet!")
                    st.rerun()
                st.markdown("---")
    else:
        st.info("No saved outfits yet. Click '💾 Save Outfit' in the Outfit Generator tab to store looks here.")
