import os
import streamlit as st
from PIL import Image

# Import standard library safely
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
st.set_page_config(page_title="AI Outfit Stylist", layout="wide")

if "saved_outfits" not in st.session_state:
    st.session_state["saved_outfits"] = []
if "generated_outfits" not in st.session_state:
    st.session_state["generated_outfits"] = []

st.title("👗 AI Fashion Stylist & Virtual Try-On")

# Sidebar Controls
st.sidebar.header("1. Model Configuration")
model_type = st.sidebar.radio("Headgear Style:", ["Turban", "Cap", "Beanie"])

uploaded_model = st.sidebar.file_uploader(
    f"Upload base photo with {model_type}:", 
    type=["jpg", "jpeg", "png"]
)

st.sidebar.markdown("---")
st.sidebar.header("2. Outfit Options")
source_mode = st.sidebar.radio("Outfit Source:", ["Online Shopping (Amazon/Web)", "My Wardrobe"])
batch_count = st.sidebar.radio("Number of Outfits:", [5, 10])

api_key = st.sidebar.text_input("Google AI Studio API Key:", type="password")

# Generation Logic
if st.sidebar.button("✨ Generate Outfits", type="primary"):
    if not api_key:
        st.error("Please enter your Google AI Studio API Key.")
    elif not uploaded_model:
        st.error(f"Please upload a photo wearing your {model_type}.")
    else:
        with st.spinner(f"Curating {batch_count} outfits..."):
            prompt = f"""
            Act as a personal fashion stylist. Generate {batch_count} complete outfits for a male model wearing a solid {model_type}.
            Outfit source mode: {source_mode}.
            Provide itemized breakdown (Top, Bottom, Shoes, Accessories, Headgear color matching). Include online buy search keywords if shopping mode.
            """
            
            try:
                if NEW_SDK:
                    client = genai.Client(api_key=api_key)
                    response = client.models.generate_content(
                        model='gemini-2.5-flash',
                        contents=prompt
                    )
                    outfits_text = response.text
                else:
                    genai.configure(api_key=api_key)
                    model = genai.GenerativeModel('gemini-1.5-flash')
                    response = model.generate_content(prompt)
                    outfits_text = response.text
                    
                st.session_state["generated_outfits"] = [o.strip() for o in outfits_text.split("\n\n") if o.strip()]
                st.success("Outfits generated successfully!")
            except Exception as e:
                st.error(f"Error generating outfits: {str(e)}")

# Display Curated Outfits
st.header("👔 Curated Outfits")

if st.session_state["generated_outfits"]:
    for idx, outfit_text in enumerate(st.session_state["generated_outfits"]):
        with st.expander(f"Outfit Concept #{idx + 1}", expanded=True):
            st.write(outfit_text)
            
            col1, col2, col3 = st.columns([1, 1, 2])
            
            with col1:
                if st.button(f"👁️ Preview #{idx + 1}", key=f"prev_{idx}"):
                    st.info("Rendering preview on model...")
                    image = Image.open(uploaded_model)
                    st.image(image, caption=f"Model Try-On Preview #{idx + 1}")

            with col2:
                if st.button(f"💾 Save", key=f"save_{idx}"):
                    if outfit_text not in st.session_state["saved_outfits"]:
                        st.session_state["saved_outfits"].append(outfit_text)
                        st.toast(f"Saved Outfit #{idx + 1}!")

            with col3:
                if st.button(f"🗑️ Delete", key=f"del_{idx}"):
                    st.session_state["generated_outfits"].pop(idx)
                    st.rerun()

# Saved Outfits Gallery
st.markdown("---")
st.header("🔒 Saved Closet")
if st.session_state["saved_outfits"]:
    for s_idx, item in enumerate(st.session_state["saved_outfits"]):
        st.info(f"**Saved Look #{s_idx + 1}:**\n\n{item}")
else:
    st.write("No saved outfits yet.")
