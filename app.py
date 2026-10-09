import os
import time
import json
import uuid
import random
import sqlite3
import base64
from io import BytesIO
import pandas as pd
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
st.set_page_config(page_title="Personal High-End AI Stylist & Companion", layout="wide")

# ==========================================
# UNIFIED SQLITE DATABASE STORAGE SETUP
# ==========================================
DB_FILE = "fashion_stylist.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    # Model Photos Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS model_photos (
            angle_key TEXT PRIMARY KEY,
            image_blob TEXT
        )
    """)
    # Wardrobe Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS wardrobe (
            id TEXT PRIMARY KEY,
            info TEXT,
            image_blob TEXT
        )
    """)
    # Outfits Table (Generated & Saved)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS outfits (
            id TEXT PRIMARY KEY,
            type TEXT, -- 'generated' or 'saved'
            text TEXT,
            gemini_prompt TEXT,
            chatgpt_prompt TEXT,
            items_breakdown TEXT, -- JSON string of table rows
            total_price TEXT,
            image_blob TEXT
        )
    """)
    conn.commit()
    conn.close()

init_db()

def pil_to_base64(img):
    if img is None:
        return None
    buffered = BytesIO()
    img.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode("utf-8")

def base64_to_pil(b64_str):
    if not b64_str:
        return None
    try:
        img_data = base64.b64decode(b64_str)
        return Image.open(BytesIO(img_data))
    except Exception:
        return None

# Load persistent data from DB into session state
def load_db_data():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Model Photos
    st.session_state["model_photos"] = {}
    cursor.execute("SELECT angle_key, image_blob FROM model_photos")
    for angle_key, blob in cursor.fetchall():
        img = base64_to_pil(blob)
        if img:
            st.session_state["model_photos"][angle_key] = img

    # Wardrobe
    st.session_state["wardrobe_items"] = []
    cursor.execute("SELECT id, info, image_blob FROM wardrobe")
    for item_id, info, blob in cursor.fetchall():
        img = base64_to_pil(blob)
        if img:
            st.session_state["wardrobe_items"].append({
                "id": item_id,
                "image": img,
                "info": info
            })

    # Generated Outfits
    st.session_state["generated_outfits"] = []
    cursor.execute("SELECT id, text, gemini_prompt, chatgpt_prompt, items_breakdown, total_price, image_blob FROM outfits WHERE type='generated'")
    for row in cursor.fetchall():
        breakdown = []
        try:
            breakdown = json.loads(row[4]) if row[4] else []
        except Exception:
            pass
        st.session_state["generated_outfits"].append({
            "id": row[0],
            "text": row[1],
            "gemini_prompt": row[2],
            "chatgpt_prompt": row[3],
            "items_breakdown": breakdown,
            "total_price": row[5],
            "image": base64_to_pil(row[6])
        })

    # Saved Closet Outfits
    st.session_state["saved_outfits"] = []
    cursor.execute("SELECT id, text, gemini_prompt, chatgpt_prompt, items_breakdown, total_price, image_blob FROM outfits WHERE type='saved'")
    for row in cursor.fetchall():
        breakdown = []
        try:
            breakdown = json.loads(row[4]) if row[4] else []
        except Exception:
            pass
        st.session_state["saved_outfits"].append({
            "id": row[0],
            "text": row[1],
            "gemini_prompt": row[2],
            "chatgpt_prompt": row[3],
            "items_breakdown": breakdown,
            "total_price": row[5],
            "image": base64_to_pil(row[6])
        })
    
    conn.close()

if "initialized_db" not in st.session_state:
    load_db_data()
    st.session_state["initialized_db"] = True

# Database helper mutation functions
def db_save_model_photo(angle_key, pil_image):
    st.session_state["model_photos"][angle_key] = pil_image
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("REPLACE INTO model_photos (angle_key, image_blob) VALUES (?, ?)", (angle_key, pil_to_base64(pil_image)))
    conn.commit()
    conn.close()

def db_delete_model_photo(angle_key):
    if angle_key in st.session_state["model_photos"]:
        del st.session_state["model_photos"][angle_key]
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM model_photos WHERE angle_key = ?", (angle_key,))
    conn.commit()
    conn.close()

def db_save_wardrobe_item(pil_image, info_str):
    item_id = str(uuid.uuid4())
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO wardrobe (id, info, image_blob) VALUES (?, ?, ?)", (item_id, info_str, pil_to_base64(pil_image)))
    conn.commit()
    conn.close()
    st.session_state["wardrobe_items"].append({
        "id": item_id,
        "image": pil_image,
        "info": info_str
    })

def db_delete_wardrobe_item(index):
    if 0 <= index < len(st.session_state["wardrobe_items"]):
        item = st.session_state["wardrobe_items"].pop(index)
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM wardrobe WHERE id = ?", (item["id"],))
        conn.commit()
        conn.close()

def db_save_generated_outfit_image(idx, pil_image):
    if 0 <= idx < len(st.session_state["generated_outfits"]):
        outfit = st.session_state["generated_outfits"][idx]
        outfit["image"] = pil_image
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("UPDATE outfits SET image_blob = ? WHERE id = ?", (pil_to_base64(pil_image), outfit["id"]))
        conn.commit()
        conn.close()

def db_delete_generated_outfit(idx):
    if 0 <= idx < len(st.session_state["generated_outfits"]):
        item = st.session_state["generated_outfits"].pop(idx)
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM outfits WHERE id = ?", (item["id"],))
        conn.commit()
        conn.close()

def db_save_to_closet(outfit_data):
    saved_item = {
        "id": outfit_data.get("id", str(uuid.uuid4())),
        "text": outfit_data["text"],
        "gemini_prompt": outfit_data.get("gemini_prompt", ""),
        "chatgpt_prompt": outfit_data.get("chatgpt_prompt", ""),
        "items_breakdown": outfit_data.get("items_breakdown", []),
        "total_price": outfit_data.get("total_price", ""),
        "image": outfit_data.get("image")
    }
    
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        REPLACE INTO outfits (id, type, text, gemini_prompt, chatgpt_prompt, items_breakdown, total_price, image_blob)
        VALUES (?, 'saved', ?, ?, ?, ?, ?, ?)
    """, (
        saved_item["id"],
        saved_item["text"],
        saved_item["gemini_prompt"],
        saved_item["chatgpt_prompt"],
        json.dumps(saved_item["items_breakdown"]),
        saved_item["total_price"],
        pil_to_base64(saved_item["image"])
    ))
    conn.commit()
    conn.close()

    if not any(o.get("id") == saved_item["id"] for o in st.session_state["saved_outfits"]):
        st.session_state["saved_outfits"].append(saved_item)

def db_delete_saved_closet(idx):
    if 0 <= idx < len(st.session_state["saved_outfits"]):
        item = st.session_state["saved_outfits"].pop(idx)
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM outfits WHERE id = ?", (item["id"],))
        conn.commit()
        conn.close()

# ==========================================
# TOOL / FUNCTION DEFINITIONS
# ==========================================
def get_trending_fashion_items(category: str) -> str:
    trends = {
        "turban": "High-end pairings: Heavyweight flannel overshirt worn open over a tucked tee; relaxed knit cardigan with straight-leg denim; premium fleece hoodies with tailored outerwear.",
        "cap": "High-end pairings: Boxy graphic tees with open camp-collar shirts; zip-up hoodies under unstructured work jackets; tonal earth-tone sweatshirts with relaxed denim.",
        "beanie": "High-end pairings: Chunky knit cardigans over heavyweight tees; minimalist fleece layers under wool overcoats; relaxed sweatshirts with straight cargos.",
        "tops": "Advanced layering: Premium textured overshirts, waffle-knit thermals, boxy resort shirts, and heavy fleece hoodies.",
        "bottoms": "Modern proportions: Structured straight-leg denim, relaxed-fit vintage wash jeans, and pleated utility trousers."
    }
    key = category.lower().strip()
    return trends.get(key, f"Curated high-end proportions for {category}: Advanced layering and premium fabric weighting.")

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
                        temperature=0.8,
                        max_output_tokens=8192
                    )
                )
                raw_text = response.text
            else:
                genai.configure(api_key=api_key)
                model = genai.GenerativeModel(
                    model_name, 
                    generation_config={"temperature": 0.8, "max_output_tokens": 8192}
                )
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
st.title("👔 Personal High-End AI Stylist & Companion")

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
                db_delete_model_photo(key_str)
                st.rerun()
    else:
        uploaded_file = st.sidebar.file_uploader(f"Upload {angle} view:", type=["jpg", "jpeg", "png"], key=f"upload_{key_str}")
        if uploaded_file:
            img = Image.open(uploaded_file)
            db_save_model_photo(key_str, img)
            st.rerun()

st.sidebar.markdown("---")
st.sidebar.header("2. Generation Settings")
source_mode = st.sidebar.radio("Outfit Source:", ["Online Shopping (Amazon/Web)", "My Wardrobe"])
batch_count = st.sidebar.radio("Number of Outfits:", [3, 5])

st.sidebar.markdown("---")
st.sidebar.header("💵 Outfit Budget Tier")
budget_tier = st.sidebar.radio(
    "Select Total Outfit Budget:",
    [
        "Budget-Friendly (~$150 total | Uniqlo, SHEIN, ASOS, H&M)",
        "Mid-Tier ($150 - $300 total | Abercrombie, Carhartt WIP, Levi's, COS)",
        "Luxury / High-End ($300 - $600 total | Buck Mason, Noah, Acne Studios, Stüssy)"
    ],
    index=1
)

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
    ["Smart casual", "Business casual", "Relaxed", "Traditional", "Experimental", "Loungewear / Sleep & Casual (Shorts & PJs)"],
    index=0
)

with st.expander("ℹ️ How to use this with Gemini & ChatGPT", expanded=False):
    st.markdown("""
    1. **Generate Outfits**: Click **'✨ Generate High-End Outfits + Prompts'** below.
    2. **Gemini Chat**: Copy the **Gemini Prompt**, paste it into your Gemini thread where you uploaded your 4-angle photos.
    3. **ChatGPT (DALL-E 3)**: Copy the **ChatGPT Prompt** and paste it into your locked character profile thread.
    4. **Shop & Save**: Review the fully hyperlinked price table with shoes & accessories, click the shopping links, then upload your final try-on image!
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
                    db_delete_model_photo(k)
                    st.rerun()
            else:
                st.info("Not uploaded")

    st.markdown("---")
    
    if st.button("✨ Generate High-End Outfits + Prompts", type="primary", use_container_width=True):
        if not api_key:
            st.error("Please enter or configure your Google AI Studio API Key.")
        elif "front" not in st.session_state["model_photos"]:
            st.error("Please upload at least the Front model photo before generating.")
        else:
            with st.spinner(f"Curating exactly {batch_count} high-end outfits with shoes, accessories, and hyperlinked price tables..."):
                prompt_parts = []
                
                coordinated_palettes = [
                    "Earthy Streetwear Palette: Olive green, sandstone, warm tan, chocolate brown, and raw denim (Headgear matches the earth tones cleanly).",
                    "Tonal Neutrals Palette: Oatmeal, heather grey, jet black, off-white, and washed black denim (Headgear is solid neutral).",
                    "Rich Heritage Palette: Deep burgundy/maroon layering piece, charcoal trousers or dark wash denim, and clean camel accents.",
                    "Modern Urban Palette: Slate grey, navy blue, crisp white, and stone gray."
                ]
                selected_palette = random.choice(coordinated_palettes)
                random_seed_salt = f"Random-Entropy-Token-{uuid.uuid4().hex[:8]}"
                
                prompt_parts.append(f"Entropy Salt Token: {random_seed_salt}")
                prompt_parts.append(f"STRICT COLOR PALETTE: {selected_palette}")

                prompt_parts.append("Model Reference Photos:")
                for angle_name, img in st.session_state["model_photos"].items():
                    prompt_parts.append(f"Angle: {angle_name}")
                    prompt_parts.append(img)

                if source_mode == "My Wardrobe" and st.session_state["wardrobe_items"]:
                    prompt_parts.append("\nUser's Wardrobe Inventory:")
                    for idx, w_item in enumerate(st.session_state["wardrobe_items"]):
                        prompt_parts.append(f"Item #{idx+1}: {w_item['info']}")
                
                fetched_trends = get_trending_fashion_items(headgear_style)
                
                pj_rule = ""
                if outfit_vibe == "Loungewear / Sleep & Casual (Shorts & PJs)":
                    pj_rule = "MANDATORY OUTFIT TYPE: Include premium loungewear, high-end sleep shorts, luxury pajama sets, or relaxed lounge pants paired with matching hoodies, tees, or robes."
                else:
                    pj_rule = "STRICT CONSTRAINT: DO NOT include shorts or pajamas. All outfits must be full-length trousers, jeans, or cargo pants appropriate for the selected vibe and weather."

                instructions = f"""
                Act as an elite personal high-end menswear stylist and fashion director. 
                Generate EXACTLY {batch_count} distinct, high-end outfit concepts.
                Style Guidelines: {fetched_trends}
                
                ENVIRONMENTAL & BUDGET CONSTRAINTS:
                - Weather / Temperature Context: {weather_range}. Ensure appropriate layering.
                - Style Vibe: {outfit_vibe}.
                - {pj_rule}
                - Outfit Budget Tier: {budget_tier}. Ensure individual item prices and the overall sum fit strictly within this budget bracket.
                
                MANDATORY OUTFIT COMPONENTS & SHOES & ACCESSORIES:
                1. Every single outfit MUST include: Tops/Layers, Bottoms, Headgear ({headgear_style}), Shoes (sneakers, loafers, or boots), AND Accessories (men's necklaces/chains, bracelets, rings, sunglasses, or watches).
                2. In the "description" text and in the table breakdown, EVERY single item (clothing, shoes, headgear, and accessories) MUST be formatted as a clickable Markdown link pointing directly to a Google Shopping search query formatted strictly as: `[Brand Item Name](https://www.google.com/search?q=Brand+Item+Name+Color&tbm=shop)`.
                3. Strictly adhere to the '{selected_palette}' color story across all garments and accessories with zero color clashing.
                
                HYPERLINKED TABLE REQUIREMENT ("items_breakdown"):
                Provide an array called "items_breakdown" containing objects with keys:
                - "Clothing Item": A Markdown-formatted string with the clickable Google Shopping search link (e.g. `[COS Minimalist Sneakers](https://www.google.com/search?q=COS+Minimalist+Sneakers&tbm=shop)`).
                - "Estimated Price": Price string (e.g. "$110").
                Also include a "total_price" string key representing the sum.
                
                DUAL-PLATFORM PROMPT GENERATION REQUIREMENTS (TEXT & IMAGE CONSISTENCY):
                - `gemini_prompt`: Designed for Gemini Chat (referencing uploaded image attachments, specifying HD 4K studio quality, absolute photorealism, and zero blurriness, describing the exact same color-graded outfit as the description).
                - `chatgpt_prompt`: Designed for ChatGPT / DALL-E 3, starting with the character profile anchor: "Using my master character profile locked in this chat (South Asian male, 36 years old, height 5'8", well-groomed dark beard), generate a razor-sharp 4K lookbook studio portrait photo of me wearing..." followed by the exact color-graded layered outfit details matching the description.
                
                Return JSON format with a key "outfits" containing a list of exactly {batch_count} objects, each with:
                - "description": Outfit breakdown tailored to {weather_range}, {outfit_vibe} vibe, and {budget_tier}, featuring cohesive color-graded descriptions and active Google Shopping search links for every piece.
                - "items_breakdown": List of objects with keys "Clothing Item" (containing Markdown links) and "Estimated Price".
                - "total_price": Total cost string (e.g. "$250").
                - "gemini_prompt": Photo generation prompt for Gemini Chat detailing this exact outfit with HD 4K studio quality including shoes and accessories.
                - "chatgpt_prompt": Photo generation prompt for ChatGPT / DALL-E 3 starting with the character profile anchor and detailing this exact outfit.
                """
                prompt_parts.append(instructions)
                
                try:
                    result_json = call_gemini_outfits(prompt_parts, api_key)
                    parsed_outfits = result_json.get("outfits", [])
                    
                    conn = sqlite3.connect(DB_FILE)
                    cursor = conn.cursor()
                    
                    st.session_state["generated_outfits"] = []
                    for item in parsed_outfits:
                        outfit_id = str(uuid.uuid4())
                        new_gen = {
                            "id": outfit_id,
                            "text": item.get("description", ""),
                            "gemini_prompt": item.get("gemini_prompt", ""),
                            "chatgpt_prompt": item.get("chatgpt_prompt", ""),
                            "items_breakdown": item.get("items_breakdown", []),
                            "total_price": item.get("total_price", ""),
                            "image": None
                        }
                        st.session_state["generated_outfits"].append(new_gen)
                        
                        cursor.execute("""
                            INSERT INTO outfits (id, type, text, gemini_prompt, chatgpt_prompt, items_breakdown, total_price, image_blob)
                            VALUES (?, 'generated', ?, ?, ?, ?, ?, NULL)
                        """, (
                            outfit_id,
                            new_gen["text"],
                            new_gen["gemini_prompt"],
                            new_gen["chatgpt_prompt"],
                            json.dumps(new_gen["items_breakdown"]),
                            new_gen["total_price"]
                        ))
                    
                    conn.commit()
                    conn.close()
                    st.success(f"Successfully generated {len(st.session_state['generated_outfits'])} high-end outfits with hyperlinked price tables, shoes, and accessories!")
                except Exception as e:
                    st.error(f"Error generating outfits: {str(e)}")

    st.header("✨ Curated Outfits & Prompts")
    if st.session_state["generated_outfits"]:
        for idx, outfit_data in enumerate(st.session_state["generated_outfits"]):
            with st.expander(f"Outfit Concept #{idx + 1}", expanded=True):
                col_txt, col_img = st.columns([2, 1])
                
                with col_txt:
                    st.markdown(f"### Look Breakdown & Shopping Links\n{outfit_data['text']}")
                    st.markdown("---")
                    
                    # RENDER HYPERLINKED PRICE BREAKDOWN TABLE
                    if outfit_data.get("items_breakdown"):
                        st.markdown("**💰 Itemized Price Breakdown (with Clickable Links):**")
                        table_markdown = "| Item / Accessory | Estimated Price |\n| :--- | :--- |\n"
                        for row in outfit_data["items_breakdown"]:
                            item_name = row.get("Clothing Item", "")
                            item_price = row.get("Estimated Price", "")
                            table_markdown += f"| {item_name} | {item_price} |\n"
                        
                        st.markdown(table_markdown)
                        if outfit_data.get("total_price"):
                            st.markdown(f"**Total Estimated Outfit Cost:** `{outfit_data['total_price']}`")
                        st.markdown("---")
                    
                    st.markdown("**1. Gemini Chat Prompt:**")
                    st.code(outfit_data["gemini_prompt"], language="text")
                    
                    st.markdown("**2. ChatGPT / DALL-E 3 Prompt:**")
                    st.code(outfit_data["chatgpt_prompt"], language="text")
                
                with col_img:
                    if outfit_data.get("image"):
                        st.image(outfit_data["image"], caption=f"Try-On Result #{idx+1}", use_container_width=True)
                        if st.button("🔄 Replace Result Image", key=f"replace_img_{idx}"):
                            db_save_generated_outfit_image(idx, None)
                            st.rerun()
                    else:
                        uploaded_img = st.file_uploader(
                            f"Upload Try-On Image #{idx+1}:", 
                            type=["jpg", "jpeg", "png"], 
                            key=f"tryon_img_up_{idx}"
                        )
                        if uploaded_img:
                            img = Image.open(uploaded_img)
                            db_save_generated_outfit_image(idx, img)
                            st.rerun()

                c1, c2 = st.columns([1, 1])
                with c1:
                    if st.button(f"💾 Save Outfit #{idx + 1}", key=f"save_gen_{idx}"):
                        db_save_to_closet(outfit_data)
                        st.toast("Saved permanently to Closet!")
                with c2:
                    if st.button(f"🗑️ Delete Outfit #{idx + 1}", key=f"del_gen_{idx}"):
                        db_delete_generated_outfit(idx)
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
                        db_save_wardrobe_item(img, analysis_text.strip())
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
                    db_delete_wardrobe_item(w_idx)
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
                    db_delete_saved_closet(s_idx)
                    st.toast("Removed from Saved Closet!")
                    st.rerun()
                st.markdown("---")
    else:
        st.info("No saved outfits yet. Click '💾 Save Outfit' in the Outfit Generator tab to store looks here.")
