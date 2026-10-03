import os
import streamlit as st
from google import genai
from google.genai import types

# Page setup - Mobile friendly responsive design
st.set_page_config(page_title="AI Outfit Stylist", layout="wide", initial_sidebar_state="expanded")

# Initialize Session States for Saved Outfits & Selected Model
if "saved_outfits" not in st.session_state:
    st.session_state["saved_outfits"] = []
if "generated_outfits" not in st.session_state:
    st.session_state["generated_outfits"] = []

st.title("👗 AI Fashion Stylist & Virtual Try-On")

# 1. MODEL & CONFIGURATION SIDEBAR
st.sidebar.header("1. Select Your Model Base")
model_type = st.sidebar.radio("Headgear Style:", ["Turban", "Cap", "Beanie"])

uploaded_model = st.sidebar.file_uploader(
    f"Upload your base photo wearing a {model_type}:", 
    type=["jpg", "jpeg", "png"]
)

st.sidebar.markdown("---")
st.sidebar.header("2. Outfit Parameters")
source_mode = st.sidebar.radio("Outfit Source:", ["Online Shopping (Amazon/Web)", "My Wardrobe"])
batch_count = st.sidebar.radio("Number of Outfits to Generate:", [5, 10])

# Wardrobe upload mode if user selects 'My Wardrobe'
wardrobe_files = []
if source_mode == "My Wardrobe":
    wardrobe_files = st.sidebar.file_uploader("Upload Wardrobe Items:", type=["jpg", "png"], accept_multiple_files=True)

api_key = st.sidebar.text_input("Google AI Studio API Key:", type="password")

# Initialize Gemini Client
client = None
if api_key:
    client = genai.Client(api_key=api_key)

# 2. GENERATE OUTFITS SECTION
if st.sidebar.button("✨ Generate Outfits", type="primary"):
    if not client:
        st.error("Please enter your Google AI Studio API Key in the sidebar.")
    elif not uploaded_model:
        st.error(f"Please upload your base photo with a {model_type}.")
    else:
        with st.spinner(f"Curating {batch_count} stylish outfits..."):
            prompt = f"""
            Act as a high-end personal stylist. Generate {batch_count} complete layered outfits for a male model wearing a solid-colored {model_type}.
            Ensure the outfit is layered (e.g., outer jacket/shacket, mid-layer button down or knitwear, t-shirt, jeans/chinos, shoes, and accessories like sunglasses).
            Source Mode: {source_mode}.
            Provide specific descriptions for top, bottom, shoes, and turban/headgear color recommendations. 
            Include mock Amazon search terms/links for buying if source mode is Online Shopping.
            """
            
            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt
            )
            
            st.session_state["generated_outfits"] = response.text.split("\n\n")
            st.success(f"Generated {batch_count} outfit concepts!")

# 3. DISPLAY GENERATED OUTFITS & PREVIEW CONTROLS
st.header("👔 Curated Outfits Gallery")

if st.session_state["generated_outfits"]:
    for idx, outfit_text in enumerate(st.session_state["generated_outfits"]):
        if outfit_text.strip():
            with st.expander(f"Outfit Concept #{idx + 1}", expanded=True):
                st.write(outfit_text)
                
                col1, col2, col3 = st.columns([1, 1, 2])
                
                # Preview Button (Virtual Try-On Render)
                with col1:
                    if st.button(f"👁️ Preview Outfit #{idx + 1}", key=f"prev_{idx}"):
                        if uploaded_model and client:
                            with st.spinner("Editing model image to put outfit on you..."):
                                # Load model image bytes
                                model_bytes = uploaded_model.getvalue()
                                
                                try_on_prompt = f"""
                                Keep the person's exact face structure, body frame, posture, and headgear shape ({model_type}) completely identical to the uploaded image.
                                Change the clothing items to match this exact outfit: {outfit_text}.
                                Ensure realistic fit, texture, and natural lighting.
                                """
                                
                                render_res = client.models.generate_images(
                                    model='imagen-3.0-generate-002',
                                    prompt=try_on_prompt,
                                    config=types.GenerateImagesConfig(
                                        number_of_images=1,
                                        aspect_ratio="3:4"
                                    )
                                )
                                
                                for generated_image in render_res.generated_images:
                                    st.image(generated_image.image.image_bytes, caption=f"Virtual Try-On Preview #{idx+1}")
                        else:
                            st.warning("Upload model image and enter API key first.")

                # Save Button
                with col2:
                    if st.button(f"💾 Save Look", key=f"save_{idx}"):
                        if outfit_text not in st.session_state["saved_outfits"]:
                            st.session_state["saved_outfits"].append(outfit_text)
                            st.toast(f"Saved Outfit #{idx + 1} to your closet!")

                # Delete Button
                with col3:
                    if st.button(f"🗑️ Delete Option", key=f"del_{idx}"):
                        st.session_state["generated_outfits"].pop(idx)
                        st.rerun()

# 4. SAVED CLOSET SECTION
st.markdown("---")
st.header("🔒 Saved Outfits Closet")
if st.session_state["saved_outfits"]:
    for s_idx, saved_item in enumerate(st.session_state["saved_outfits"]):
        st.info(f"**Saved Look #{s_idx + 1}:**\n\n{saved_item}")
else:
    st.write("No saved outfits yet.")
