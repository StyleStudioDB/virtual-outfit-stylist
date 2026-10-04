import os
import time
import json
import uuid
import random
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
OUTFITS_DIR = os.path.join(STORAGE_DIR, "outfits")
GENERATED_DIR = os.path.join(STORAGE_DIR, "generated")

WARDROBE_META = os.path.join(WARDROBE_DIR, "metadata.json")
SAVED_OUTFITS_META = os.path.join(OUTFITS_DIR, "metadata.json")
GENERATED_OUTFITS_META = os.path.join(GENERATED_DIR, "metadata.json")

for d in [MODEL_DIR, WARDROBE_DIR, OUTFITS_DIR, GENERATED_DIR]:
    os.makedirs(d, exist_ok=True)

def load_persisted_data():
    """Fully restores model photos, wardrobe, generated outfits, and saved outfits from disk on refresh."""
    
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

    if "generated_outfits" not in st.session_state:
        st.session_state["generated_outfits"] = []
        if os.path.exists(GENERATED_OUTFITS_META):
            try:
                with open(GENERATED_OUTFITS_META, "r") as f:
                    meta = json.load(f)
                for item in meta:
                    img = None
                    if item.get("image_filename"):
                        img_path = os.path.join(GENERATED_DIR, item["image_filename"])
                        if os.path.exists(img_path):
                            img = Image.open(img_path)
                    st.session_state["generated_outfits"].append({
                        "id": item.get("id", str(uuid.uuid4())),
                        "text": item["text"],
                        "prompt": item["prompt"],
                        "image": img,
                        "image_filename": item.get("image_filename")
                    })
            except Exception:
                pass

    if "saved_outfits" not in st.session_state:
        st.session_state["saved_outfits"] = []
        if os.path.exists(SAVED_OUTFITS_META):
            try:
                with open(SAVED_OUTFITS_META, "r") as f:
                    meta = json.load(f)
                for item in meta:
                    img = None
                    if item.get("image_filename"):
                        img_path = os.path.join(OUTFITS_DIR, item["image_filename"])
                        if os.path.exists(img_path):
                            img = Image.open(img_path)
                    st.session_state["saved_outfits"].append({
                        "id": item.get("id", str(uuid.uuid4())),
                        "text": item["text"],
                        "prompt": item["prompt"],
                        "image": img,
                        "image_filename": item.get("image_filename")
                    })
            except Exception:
                pass

load_persisted_data()

# ==========================================
# STORAGE HELPER FUNCTIONS
# ==========================================
def save_model_photo_disk(angle_key, pil_image):
    st.session_state["model_photos"][angle_key] = pil_image
    file_path = os.path.join(MODEL_DIR, f"{angle_key}.png")
    pil_image.save(file_path, "PNG")

def delete_model_photo_disk(angle_key):
    if angle_key in st.session_state["model_photos"]:
        del st.session_state["model_photos"][angle_key]
    file_path = os.path.join(MODEL_DIR, f"{angle_key}.png")
    if os.path.exists(file_path):
        os.remove(file_path)

def save_wardrobe_item_disk(pil_image, info_str):
    filename = f"item_{int(time.time() * 1000)}.png"
    file_path = os.path.join(WARDROBE_DIR, filename)
    pil_image.save(file_path, "PNG")

    st.session_state["wardrobe_items"].append({
        "image": pil_image,
        "info": info_str,
        "filename": filename
    })
    _sync_metadata(WARDROBE_META, st.session_state["wardrobe_items"])

def delete_wardrobe_item_disk(index):
    if 0 <= index < len(st.session_state["wardrobe_items"]):
        item = st.session_state["wardrobe_items"].pop(index)
        file_path = os.path.join(WARDROBE_DIR, item.get("filename", ""))
        if os.path.exists(file_path):
            os.remove(file_path)
        _sync_metadata(WARDROBE_META, st.session_state["wardrobe_items"])

def save_generated_outfit_image_disk(idx, pil_image):
    if 0 <= idx < len(st.session_state["generated_outfits"]):
        outfit = st.session_state["generated_outfits"][idx]
        filename = f"gen_{int(time.time() * 1000)}.png"
        file_path = os.path.join(GENERATED_DIR, filename)
        pil_image.save(file_path, "PNG")
        
        if outfit.get("image_filename"):
            old_path = os.path.join(GENERATED_DIR, outfit["image_filename"])
            if os.path.exists(old_path):
                os.remove(old_path)
                
        outfit["image"] = pil_image
        outfit["image_filename"] = filename
        _sync_outfits_metadata(GENERATED_OUTFITS_META, st.session_state["generated_outfits"])

def delete_generated_outfit_disk(idx):
    if 0 <= idx < len(st.session_state["generated_outfits"]):
        item = st.session_state["generated_outfits"].pop(idx)
        if item.get("image_filename"):
            path = os.path.join(GENERATED_DIR, item["image_filename"])
            if os.path.exists(path):
                os.remove(path)
        _sync_outfits_metadata(GENERATED_OUTFITS_META, st.session_state["generated_outfits"])

def save_to_closet_disk(outfit_data):
    img_filename = None
    if outfit_data.get("image"):
        img_filename = f"closet_{int(time.time() * 1000)}.png"
        path = os.path.join(OUTFITS_DIR, img_filename)
        outfit_data["image"].save(path, "PNG")
        
    saved_item = {
        "id": outfit_data.get("id", str(uuid.uuid4())),
        "text": outfit_data["text"],
        "prompt": outfit_data["prompt"],
        "image": outfit_data.get("image"),
        "image_filename": img_filename
    }
    
    if not any(o.get("id") == saved_item["id"] for o in st.session_state["saved_outfits"]):
        st.session_state["saved_outfits"].append(saved_item)
        _sync_outfits_metadata(SAVED_OUTFITS_META, st.session_state["saved_outfits"])

def delete_saved_closet_disk(idx):
    if 0 <= idx < len(st.session_state["saved_outfits"]):
        item = st.session_state["saved_outfits"].pop(idx)
        if item.get("image_filename"):
            path = os.path.join(OUTFITS_DIR, item["image_filename"])
            if os.path.exists(path):
                os.remove(path)
        _sync_outfits_metadata(SAVED_OUTFITS_META, st.session_state["saved_outfits"])

def _sync_metadata(meta_path, items_list):
    meta = [{"info": item.get("info"), "filename": item.get("filename")} for item in items_list]
    with open(meta_path, "w") as f:
        json.dump(meta, f)

def _sync_outfits_metadata(meta_path, outfits_list):
    meta = []
    for item in outfits_list:
        meta.append({
            "id": item.get("id", str(uuid.uuid4())),
            "text": item.get("text"),
            "prompt": item.get("prompt"),
            "image_filename": item.get("image_filename")
        })
    with open(meta_path, "w") as f:
        json.dump(meta, f)

# ==========================================
# TOOL / FUNCTION DEFINITIONS
# ==========================================
def get_trending_fashion_items(category: str) -> str:
    trends = {
        "turban": "Cohesive style pairings: Military green paired with khaki, mustard, and brown; charcoal with cream and black; navy blue with camel and tan.",
        "cap": "Cohesive style pairings: Olive green cap paired with tan cargo pants and brown layers; black cap with dark-wash denim and heather grey hoodie; beige cap with chocolate brown jacket.",
        "beanie": "Cohesive style pairings: Chocolate brown beanie with cream sweater and tan coat; forest green beanie with khaki chinos; black beanie with charcoal layers.",
        "tops": "Cohesive styles: Neutral base layers with one cohesive color family story.",
        "bottoms": "Cohesive styles: Dark-wash denim, khaki chinos, and charcoal trousers anchoring upper layers cleanly."
    }
    key = category.lower().strip()
    return trends.get(key, f"Cohesive styles for {category}: Professional color grading across all garments and headwear.")

# ==========================================
# GEMINI CALL 
# ==========================================
def call_gemini_outfits(contents, api_key):
    model_name = 'gemini-3.5-flash-lite'
    
    for attempt in range(2):
        try:
            if NEW_SDK:
                client = genai.Client(api_key=api_key)
                safety_settings = [
                    types.SafetySetting(category=types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT, threshold=types.HarmBlockThreshold.BLOCK_ONLY_HIGH),
                    types.SafetySetting(category=types.HarmCategory.HARM_CATEGORY_HATE_SPEECH, threshold=types.HarmBlockThreshold.BLOCK_ONLY_HIGH)
                ]
                response = client.models.generate_content(
                    model=model_name,
                    contents=contents,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        safety_settings=safety_settings,
                        temperature=0.75
                    )
                )
                raw_text = response.text
            else:
                genai.configure(api_key=api_key)
                model = genai.GenerativeModel(model_name, generation_config={"temperature": 0.75})
                response = model.generate_content(contents)
                raw_text = response.text

            if not raw_text:
                finish_reason = "Unknown"
                if hasattr(response, 'candidates') and response.candidates:
                    if hasattr(response.candidates[0], 'finish_reason'):
                        finish_reason = str(response.candidates[0].finish_reason)
                raise ValueError(f"API returned an empty response (Finish Reason: {finish_reason}).")

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
                delete_model_photo_disk(key_str)
                st.rerun()
    else:
        uploaded_file = st.sidebar.file_uploader(f"Upload {angle} view:", type=["jpg", "jpeg", "png"], key=f"upload_{key_str}")
        if uploaded_file:
            img = Image.open(uploaded_file)
            save_model_photo_disk(key_str, img)
            st.rerun()

st.sidebar.markdown("---")
st.sidebar.header("2. Generation Settings")
source_mode = st.sidebar.radio("Outfit Source:", ["Online Shopping (Amazon/Web)", "My Wardrobe"])
batch_count = st.sidebar.radio("Number of Outfits:", [3, 5])

st.sidebar.markdown("---")
st.sidebar.header("🌡️ Temperature / Weather")
weather_range = st.sidebar.radio(
    "Select Weather Range:", 
    ["Current weather", "80°F+", "65–79°F", "50–64°F", "40–49°F", "25–39°F", "Below 25°F"],
    index=2
)

st.sidebar.markdown("---")
st.sidebar.header("✨ Vibe / Style")
outfit_vibe = st.sidebar.radio(
    "Select Style Vibe:", 
    ["Smart casual", "Business casual", "Relaxed", "Traditional", "Experimental"],
    index=0
)

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
                    delete_model_photo_disk(k)
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
            with st.spinner(f"Curating {batch_count} high-definition color-coordinated outfits for {weather_range}..."):
                prompt_parts = []
                
                coordinated_palettes = [
                    "Military & Earth Tones Palette: Olive/Military Green, Khaki, Sandstone, Tan, Brown, and Mustard Yellow (Headgear must match or complement this earthy palette cleanly).",
                    "Warm Neutrals & Denim Palette: Cream, Charcoal, Oatmeal, Dark Denim, and Camel (Headgear must be a neutral or matching earth tone).",
                    "Rich Autumn Palette: Burgundy/Maroon paired strictly with Charcoal, Black, or Tan — never mixed with conflicting greens or purples.",
                    "Monochrome & Minimalist Palette: Jet Black, Heather Grey, Cloud White, and Clean Dark Denim (Headgear must be black, grey, or white).",
                    "Navy & Amber Palette: Navy Blue, Camel, Tan, and Crisp White (Headgear must be navy, tan, or brown)."
                ]
                selected_palette = random.choice(coordinated_palettes)
                random_seed_salt = f"Random-Entropy-Token-{uuid.uuid4().hex[:8]}"
                
                prompt_parts.append(f"Entropy Salt Token: {random_seed_salt}")
                prompt_parts.append(f"STRICT COLOR COORDINATION & HEADGEAR THEME: {selected_palette}")

                prompt_parts.append("Model Reference Photos:")
                for angle_name, img in st.session_state["model_photos"].items():
                    prompt_parts.append(f"Angle: {angle_name}")
                    prompt_parts.append(img)

                if source_mode == "My Wardrobe" and st.session_state["wardrobe_items"]:
                    prompt_parts.append("\nUser's Wardrobe Inventory:")
                    for idx, w_item in enumerate(st.session_state["wardrobe_items"]):
                        prompt_parts.append(f"Item #{idx+1}: {w_item['info']}")
                
                fetched_trends = get_trending_fashion_items(headgear_style)
                
                instructions = f"""
                Act as a professional, high-end menswear fashion designer. 
                Style Guidelines for '{headgear_style}': {fetched_trends}
                
                ENVIRONMENTAL & STYLE CONSTRAINTS:
                - Weather / Temperature Context: {weather_range}. Ensure layering and fabric weights match.
                - Style Vibe: {outfit_vibe}.
                
                CRITICAL COLOR THEORY RULES FOR OUTFIT & HEADGEAR (NO CLASHING):
                1. You MUST strictly adhere to the '{selected_palette}' assigned above. 
                2. THE HEADGEAR ({headgear_style}) COLOR IS INCLUDED IN THIS PALETTE. The headgear color must be explicitly styled to harmonize with the jacket, layers, pants, and shoes.
                3. NEVER clash primary complementary colors blindly. Keep color combinations natural, stylish, and visually balanced as a single unified outfit story.
                
                SHOPPING & LINKS REQUIREMENT:
                Outfit Source Mode: {source_mode}.
                - If 'Online Shopping (Amazon/Web)', include direct clickable Markdown shopping links/search URLs for each piece (including the headgear).
                
                CRITICAL HD PHOTOREALISM & IDENTITY ANCHORING FOR GEMINI CHAT PROMPTS:
                In the `gemini_chat_prompt` value below, enforce crystal-clear high-definition parameters:
                - Instruct Gemini Chat to maintain the exact facial structure, facial features, facial hair, skin tone, and body proportions of the reference person.
                - Explicitly require ULTRA-HIGH DEFINITION 4K/8K lookbook photography, razor-sharp focus, crisp fabric textures, realistic cloth weaves, and professional high-end studio lighting to eliminate any blurriness.
                - Explicitly specify the exact color of the '{headgear_style}' matching the outfit's cohesive color story without clashing.
                
                Return JSON format with a key "outfits", where each item is an object:
                {{
                    "description": "Itemized breakdown tailored to {weather_range} and {outfit_vibe} vibe, featuring fully color-graded descriptions for all clothing items AND the {headgear_style}, plus clickable Markdown purchase links/search URLs",
                    "gemini_chat_prompt": "An explicit photo generation prompt directed at Gemini Chat requesting a crystal-clear, razor-sharp 4K lookbook studio portrait photo of the reference subject wearing this specific, fully color-harmonized outfit. STRICT HD QUALITY: Ultra-detailed fabric textures, crisp focus, high-end professional studio lighting, absolute photorealism, zero blurriness. The '{headgear_style}' must be colored specifically to match the outfit's palette with zero clashing colors. Do NOT alter the face structure, facial features, or body build. Preserve the exact reference subject's identity completely."
                }}
                """
                prompt_parts.append(instructions)
                
                try:
                    result_json = call_gemini_outfits(prompt_parts, api_key)
                    parsed_outfits = result_json.get("outfits", [])
                    
                    st.session_state["generated_outfits"] = []
                    for item in parsed_outfits:
                        new_gen = {
                            "id": str(uuid.uuid4()),
                            "text": item.get("description", ""),
                            "prompt": item.get("gemini_chat_prompt", ""),
                            "image": None,
                            "image_filename": None
                        }
                        st.session_state["generated_outfits"].append(new_gen)
                    
                    _sync_outfits_metadata(GENERATED_OUTFITS_META, st.session_state["generated_outfits"])
                    st.success("HD color-coordinated outfits generated successfully!")
                except Exception as e:
                    st.error(f"Error generating outfits: {str(e)}")

    st.header("✨ Curated Outfits & Gemini Prompts")
    if st.session_state["generated_outfits"]:
        for idx, outfit_data in enumerate(st.session_state["generated_outfits"]):
            with st.expander(f"Outfit Concept #{idx + 1}", expanded=True):
                col_txt, col_img = st.columns([2, 1])
                
                with col_txt:
                    st.markdown(f"### Look Breakdown & Links\n{outfit_data['text']}")
                    st.markdown("---")
                    st.markdown("**Copy this prompt to your Gemini Chat:**")
                    st.code(outfit_data["prompt"], language="text")
                
                with col_img:
                    if outfit_data.get("image"):
                        st.image(outfit_data["image"], caption=f"Gemini Chat Result #{idx+1}", use_container_width=True)
                        if st.button("🔄 Replace Result Image", key=f"replace_img_{idx}"):
                            outfit_data["image"] = None
                            outfit_data["image_filename"] = None
                            _sync_outfits_metadata(GENERATED_OUTFITS_META, st.session_state["generated_outfits"])
                            st.rerun()
                    else:
                        uploaded_img = st.file_uploader(
                            f"Upload Gemini Chat Image #{idx+1}:", 
                            type=["jpg", "jpeg", "png"], 
                            key=f"gemini_img_up_{idx}"
                        )
                        if uploaded_img:
                            img = Image.open(uploaded_img)
                            save_generated_outfit_image_disk(idx, img)
                            st.rerun()

                c1, c2 = st.columns([1, 1])
                with c1:
                    if st.button(f"💾 Save Outfit #{idx + 1}", key=f"save_gen_{idx}"):
                        save_to_closet_disk(outfit_data)
                        st.toast("Saved permanently to Closet!")
                with c2:
                    if st.button(f"🗑️ Delete Outfit #{idx + 1}", key=f"del_gen_{idx}"):
                        delete_generated_outfit_disk(idx)
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
                        save_wardrobe_item_disk(img, analysis_text.strip())
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
                    delete_wardrobe_item_disk(w_idx)
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
                    delete_saved_closet_disk(s_idx)
                    st.toast("Removed from Saved Closet!")
                    st.rerun()
                st.markdown("---")
    else:
        st.info("No saved outfits yet. Click '💾 Save Outfit' in the Outfit Generator tab to store looks here.")
