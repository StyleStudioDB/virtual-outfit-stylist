import os
import time
import json
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
        st.error("Google GenAI SDK is not installed. Please add `google-genai` to your requirements.txt file.")
        st.stop()

# Streamlit Page Setup
st.set_page_config(page_title="AI Fashion Stylist & Gemini Chat Companion", layout="wide")

# ==========================================
# LOCAL DISK PERSISTENCE SETUP
# ==========================================
STORAGE_DIR = "saved_storage"
MODEL_DIR = os.path.join(STORAGE_DIR, "models")
WARDROBE_DIR = os.path.join(STORAGE_DIR, "wardrobe")
WARDROBE_META = os.path.join(WARDROBE_DIR, "metadata.json")

os.makedirs(MODEL_DIR, exist_ok=True)
os.makedirs(WARDROBE_DIR, exist_ok=True)

def load_persisted_data():
    if "model_photos" not in st.session_state:
        st.session_state["model_photos"] = {}
        for fname in os.listdir(MODEL_DIR):
            if fname.lower().endswith(('.png', '.jpg', '.jpeg')):
                angle_key = os.path.splitext(fname)[0]
                img_path = os.path.join(MODEL_DIR, fname)
                try:
                    st.session_state["model_photos"][angle_key] = Image.open(img_path)
                except Exception:
                    pass

    if "wardrobe_items" not in st.session_state:
        st.session_state["wardrobe_items"] = []
        if os.path.exists(WARDROBE_META):
            try:
                with open(WARDROBE_META, "r") as f:
                    meta = json.load(f)
                for item in meta:
                    img_path = os.path.join(WARDROBE_DIR, item["filename"])
                    if os.path.exists(img_path):
                        st.session_state["wardrobe_items"].append({
                            "image": Image.open(img_path),
                            "info": item["info"],
                            "filename": item["filename"]
                        })
            except Exception:
                pass

    if "saved_outfits" not in st.session_state:
        st.session_state["saved_outfits"] = []
    if "generated_outfits" not in st.session_state:
        st.session_state["generated_outfits"] = []

load_persisted_data()

def save_model_photo(angle_key, pil_image):
    st.session_state["model_photos"][angle_key] = pil_image
    file_path = os.path.join(MODEL_DIR, f"{angle_key}.png")
    pil_image.save(file_path, "PNG")

def delete_model_photo(angle_key):
    if angle_key in st.session_state["model_photos"]:
        del st.session_state["model_photos"][angle_key]
    file_path = os.path.join(MODEL_DIR, f"{angle_key}.png")
    if os.path.exists(file_path):
        os.remove(file_path)

def save_wardrobe_item(pil_image, info_str):
    filename = f"item_{int(time.time() * 1000)}.png"
    file_path = os.path.join(WARDROBE_DIR, filename)
    pil_image.save(file_path, "PNG")

    item_data = {
        "image": pil_image,
        "info": info_str,
        "filename": filename
    }
    st.session_state["wardrobe_items"].append(item_data)
    _sync_wardrobe_metadata()

def delete_wardrobe_item(index):
    if 0 <= index < len(st.session_state["wardrobe_items"]):
        item = st.session_state["wardrobe_items"].pop(index)
        file_path = os.path.join(WARDROBE_DIR, item.get("filename", ""))
        if os.path.exists(file_path):
            os.remove(file_path)
        _sync_wardrobe_metadata()

def _sync_wardrobe_metadata():
    meta = []
    for item in st.session_state["wardrobe_items"]:
        meta.append({
            "filename": item.get("filename"),
            "info": item.get("info")
        })
    with open(WARDROBE_META, "w") as f:
        json.dump(meta, f)

# ==========================================
# TOOL / FUNCTION DEFINITIONS
# ==========================================
def get_trending_fashion_items(category: str) -> str:
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
# GEMINI CALL 
# ==========================================
def call_gemini_outfits(contents, api_key):
    """Calls Gemini 3.5 Flash Lite to curate text outfits and prompts for Gemini Web App."""
    model_name = 'gemini-3.5-flash-lite'
    
    for attempt in range(2):
        try:
            if NEW_SDK:
                client = genai.Client(api_key=api_key)
                
                safety_settings = [
                    types.SafetySetting(
                        category=types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
                        threshold=types.HarmBlockThreshold.BLOCK_ONLY_HIGH
                    ),
                    types.SafetySetting(
                        category=types.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
                        threshold=types.HarmBlockThreshold.BLOCK_ONLY_HIGH
                    )
                ]
                
                response = client.models.generate_content(
                    model=model_name,
                    contents=contents,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        safety_settings=safety_settings
                    )
                )
                raw_text = response.text
            else:
                genai.configure(api_key=api_key)
                model = genai.GenerativeModel(model_name)
                response = model.generate_content(contents)
                raw_text = response.text

            if not raw_text:
                finish_reason = "Unknown"
                if hasattr(response, 'candidates') and response.candidates:
                    if hasattr(response.candidates[0], 'finish_reason'):
                        finish_reason = str(response.candidates[0].finish_reason)
                
                raise ValueError(
                    f"API returned an empty response (Finish Reason: {finish_reason}). "
                    "This usually means a Safety Filter mistakenly blocked the model photos."
                )

            clean_text = raw_text.replace("```json", "").replace("```", "").strip()
            return json.loads(clean_text)

        except Exception as e:
            if attempt == 0 and ("503" in str(e) or "UNAVAILABLE" in str(e)):
                time.sleep(1.5)
                continue
            else:
                raise e

# ==========================================
# UI BUILD
# ==========================================
st.title("👗 AI Fashion Stylist & Gemini Chat Companion")

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
                delete_model_photo(key_str)
                st.rerun()
    else:
        uploaded_file = st.sidebar.file_uploader(f"Upload {angle} view:", type=["jpg", "jpeg", "png"], key=f"upload_{key_str}")
        if uploaded_file:
            img = Image.open(uploaded_file)
            save_model_photo(key_str, img)
            st.rerun()

st.sidebar.markdown("---")
st.sidebar.header("2. Generation Settings")
source_mode = st.sidebar.radio("Outfit Source:", ["Online Shopping (Amazon/Web)", "My Wardrobe"])
batch_count = st.sidebar.radio("Number of Outfits:", [3, 5])

with st.expander("ℹ️ How to use this with Gemini Chat", expanded=False):
    st.markdown("""
    1. **Open Gemini Chat**: Go to [gemini.google.com](https://gemini.google.com) and open your dedicated model thread.
    2. **Generate Outfits**: Click **'✨ Generate Outfits + Gemini Prompts'** below.
    3. **Copy Prompt**: Click **'📋 Copy Prompt for Gemini Chat'** under any outfit.
    4. **Paste in Chat**: Paste the prompt into Gemini Chat to get your visual try-on picture.
    5. **Upload & Save**: Download the picture from Gemini, upload it back to that outfit concept, and click **'💾 Save to Closet'**.
    """)

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
                    delete_model_photo(k)
                    st.rerun()
            else:
                st.info("Not uploaded")

    st.markdown("---")
    
    if st.button("✨ Generate Outfits + Gemini Prompts", type="primary", use_container_width=True):
        if not api_key:
            st.error("Please enter or configure your Google AI Studio API Key.")
        elif "front" not in st.session_state["model_photos"]:
            st.error("Please upload at least the Front model photo before generating.")
        else:
            with st.spinner(f"Curating {batch_count} outfits and building Gemini Chat prompts..."):
                prompt_parts = []
                
                prompt_parts.append("Model Reference Photos:")
                for angle_name, img in st.session_state["model_photos"].items():
                    prompt_parts.append(f"Angle: {angle_name}")
                    prompt_parts.append(img)

                if source_mode == "My Wardrobe" and st.session_state["wardrobe_items"]:
                    prompt_parts.append("\nUser's Wardrobe Inventory:")
                    for idx, w_item in enumerate(st.session_state["wardrobe_items"]):
                        prompt_parts.append(f"Item #{idx+1}: {w_item['info']}")
                
                # Fetch trends locally in Python to avoid API function call interruptions
                fetched_trends = get_trending_fashion_items(headgear_style)
                
                instructions = f"""
                Act as a personal fashion stylist. 
                Current live trends for '{headgear_style}': {fetched_trends}
                
                Generate {batch_count} complete outfit recommendations suitable for the model based on these trends.
                
                Outfit Source Mode: {source_mode}.
                
                Return JSON format with a key "outfits", where each item is an object:
                {{
                    "description": "Itemized breakdown (Top, Bottom, Shoes, Accessories, Color Coordination)",
                    "gemini_chat_prompt": "An explicit photo generation prompt directed at Gemini Chat requesting a full-body lookbook photo of the reference subject wearing this outfit, strictly keeping the exact '{headgear_style}' style but harmonizing its color."
                }}
                """
                prompt_parts.append(instructions)
                
                try:
                    result_json = call_gemini_outfits(prompt_parts, api_key)
                    parsed_outfits = result_json.get("outfits", [])
                    
                    st.session_state["generated_outfits"] = []
                    for item in parsed_outfits:
                        st.session_state["generated_outfits"].append({
                            "text": item.get("description", ""),
                            "prompt": item.get("gemini_chat_prompt", ""),
                            "image": None
                        })
                    st.success("Outfits and Gemini Chat prompts generated successfully!")
                except Exception as e:
                    st.error(f"Error generating outfits: {str(e)}")

    st.header("✨ Curated Outfits & Gemini Prompts")
    if st.session_state["generated_outfits"]:
        for idx, outfit_data in enumerate(st.session_state["generated_outfits"]):
            with st.expander(f"Outfit Concept #{idx + 1}", expanded=True):
                col_txt, col_img = st.columns([2, 1])
                
                with col_txt:
                    st.markdown(f"### Look Breakdown\n{outfit_data['text']}")
                    st.markdown("---")
                    st.markdown("**Copy this prompt to your Gemini Chat:**")
                    st.code(outfit_data["prompt"], language="text")
                
                with col_img:
                    if outfit_data.get("image"):
                        st.image(outfit_data["image"], caption=f"Gemini Chat Result #{idx+1}", use_container_width=True)
                    else:
                        uploaded_img = st.file_uploader(
                            f"Upload Gemini Chat Image #{idx+1}:", 
                            type=["jpg", "jpeg", "png"], 
                            key=f"gemini_img_up_{idx}"
                        )
                        if uploaded_img:
                            outfit_data["image"] = Image.open(uploaded_img)
                            st.rerun()

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
                        if NEW_SDK:
                            client = genai.Client(api_key=api_key)
                            resp = client.models.generate_content(model='gemini-3.5-flash-lite', contents=cat_prompt)
                            analysis_text = resp.text
                        else:
                            genai.configure(api_key=api_key)
                            m = genai.GenerativeModel('gemini-3.5-flash-lite')
                            resp = m.generate_content(cat_prompt)
                            analysis_text = resp.text
                        save_wardrobe_item(img, analysis_text.strip())
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
                    delete_wardrobe_item(w_idx)
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
                    st.markdown(f"**Saved Look #{s_idx + 1}:**\n\n{item['text']}")
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
