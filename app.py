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

st.set_page_config(page_title="AI Fashion Stylist & Gemini Assistant", layout="wide")

# Local Storage Persistence
STORAGE_DIR = "saved_storage"
MODEL_DIR = os.path.join(STORAGE_DIR, "models")
WARDROBE_DIR = os.path.join(STORAGE_DIR, "wardrobe")
WARDROBE_META = os.path.join(WARDROBE_DIR, "metadata.json")

os.makedirs(MODEL_DIR, exist_ok=True)
os.makedirs(WARDROBE_DIR, exist_ok=True)

if "model_photos" not in st.session_state:
    st.session_state["model_photos"] = {}
if "wardrobe_items" not in st.session_state:
    st.session_state["wardrobe_items"] = []
if "saved_outfits" not in st.session_state:
    st.session_state["saved_outfits"] = []
if "generated_outfits" not in st.session_state:
    st.session_state["generated_outfits"] = []

st.title("👗 AI Fashion Stylist & Gemini Chat Companion")

# Tool Definition
def get_trending_fashion_items(category: str) -> str:
    trends = {
        "turban": "Trending pairings: Royal Blue, Emerald Green, and Charcoal Textured Blazers with Silk Pocket Squares.",
        "cap": "Trending pairings: Streetwear oversized hoodies, varsity jackets, and cargo pants.",
        "beanie": "Trending pairings: Wool trench coats, layer-heavy sweaters, and Chelsea boots.",
        "tops": "Trending styles: Linen button-downs, oversized monochrome t-shirts, and structured blazers.",
        "bottoms": "Trending styles: Tapered trousers, relaxed dark denim, and pleated chinos."
    }
    return trends.get(category.lower().strip(), f"Trending styles for {category}: Neutral tones, minimalist layering, and tailored fits.")

def call_gemini_outfits(contents, api_key):
    """Calls Gemini 3.5 Flash Lite to curate text outfits and prompts for Gemini Web App."""
    model_name = 'gemini-3.5-flash-lite'
    if NEW_SDK:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=model_name,
            contents=contents,
            config=types.GenerateContentConfig(
                tools=[get_trending_fashion_items],
                response_mime_type="application/json"
            )
        )
        return json.loads(response.text)
    else:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(model_name, tools=[get_trending_fashion_items])
        response = model.generate_content(contents)
        clean_text = response.text.replace("```json", "").replace("```", "").strip()
        return json.loads(clean_text)

# Sidebar Setup
st.sidebar.header("🔑 Settings")
default_key = st.secrets.get("GEMINI_API_KEY", "")
api_key = st.sidebar.text_input("Google AI Studio API Key:", value=default_key, type="password")

headgear_style = st.sidebar.radio("Headgear Style:", ["Turban", "Cap", "Beanie"])
source_mode = st.sidebar.radio("Outfit Source:", ["Online Shopping (Amazon/Web)", "My Wardrobe"])
batch_count = st.sidebar.radio("Number of Outfits:", [3, 5])

# Workflow Instructions Card
with st.expander("ℹ️ How to use this with Gemini Chat", expanded=False):
    st.markdown("""
    1. **Open Gemini Chat**: Go to [gemini.google.com](https://gemini.google.com) and open your dedicated model thread.
    2. **Generate Outfits**: Click **'✨ Generate Outfits + Gemini Prompts'** below.
    3. **Copy Prompt**: Click **'📋 Copy Prompt for Gemini Chat'** under any outfit.
    4. **Paste in Chat**: Paste the prompt into Gemini Chat to get your visual try-on picture.
    5. **Upload & Save**: Download the picture from Gemini, upload it back to that outfit concept, and click **'💾 Save to Closet'**.
    """)

# Main Generation Action
if st.button("✨ Generate Outfits + Gemini Prompts", type="primary", use_container_width=True):
    if not api_key:
        st.error("Please enter or configure your Google AI Studio API Key.")
    else:
        with st.spinner(f"Curating {batch_count} outfits and building Gemini Chat prompts..."):
            prompt_parts = []
            if source_mode == "My Wardrobe" and st.session_state["wardrobe_items"]:
                prompt_parts.append("\nUser's Wardrobe Inventory:")
                for idx, w_item in enumerate(st.session_state["wardrobe_items"]):
                    prompt_parts.append(f"Item #{idx+1}: {w_item['info']}")
            
            instructions = f"""
            Act as a personal fashion stylist. 
            First, use `get_trending_fashion_items` to fetch trends for '{headgear_style}'.
            Then generate {batch_count} complete outfit recommendations suitable for the model.
            
            Outfit Source Mode: {source_mode}.
            
            Return JSON format with key "outfits", where each item is an object:
            {{
                "description": "Itemized breakdown (Top, Bottom, Shoes, Accessories, Color Coordination)",
                "gemini_chat_prompt": "An explicit photo prompt directed at Gemini Chat requesting a full-body photo of the reference subject wearing this outfit, keeping the headgear style exact."
            }}
            """
            prompt_parts.append(instructions)
            
            try:
                result_json = call_gemini_outfits(prompt_parts, api_key)
                st.session_state["generated_outfits"] = [
                    {"text": item["description"], "prompt": item["gemini_chat_prompt"], "image": None}
                    for item in result_json.get("outfits", [])
                ]
                st.success("Outfits and Gemini Chat prompts generated successfully!")
            except Exception as e:
                st.error(f"Error generating outfits: {str(e)}")

st.markdown("---")
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
                if outfit_data["image"]:
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
                if st.button(f"🗑️️ Delete Outfit #{idx + 1}", key=f"del_gen_{idx}"):
                    st.session_state["generated_outfits"].pop(idx)
                    st.rerun()
