import os
import Streamlit as st
from PIL import Image

# Robust import check for Google GenAI library
try:
    From google import genai
    From google.genai import types
    NEW_SDK = True
except ImportError:
    Import google.generativeai as genai
    NEW_SDK = False

st.set_page_config(page_title="AI Outfit Stylist", layout="wide")

If "saved_outfits" not in st.session_state:
    St.session_state["saved_outfits"] = []
If "generated_outfits" not in st.session_state:
    St.session_state["generated_outfits"] = []

st.title("👗 AI Fashion Stylist & Virtual Try-On")

# Sidebar Configuration
st.sidebar.header("1. Model Configuration")
Model_type = st.sidebar.radio("Headgear Style:", ["Turban", "Cap", "Beanie"])

Uploaded_model = st.sidebar.file_uploader(
    F"Upload base photo with {model_type}:", 
    Type=["jpg", "jpeg", "png"]
)

st.sidebar.markdown("---")
st.sidebar.header("2. Outfit Options")
Source_mode = st.sidebar.radio("Outfit Source:", ["Online Shopping (Amazon/Web)", "My Wardrobe"])
Batch_count = st.sidebar.radio("Number of Outfits:", [5, 10])

Api_key = st.sidebar.text_input("Google AI Studio API Key:", type="password")

# Generate Outfits Action
If st.sidebar.button("✨ Generate Outfits", type="primary"):
    If not api_key:
        St.error("Please enter your Google AI Studio API Key.")
    Elif not uploaded_model:
        St.error(f"Please upload a photo wearing your {model_type}.")
    Else:
        With st.spinner(f"Curating {batch_count} outfits..."):
            Prompt = f"""
            Act as a personal fashion stylist. Generate {batch_count} complete outfits for a male model wearing a solid {model_type}.
            Outfit source mode: {source_mode}.
            Provide itemized breakdown (Top, Bottom, Shoes, Accessories, Headgear color matching). Include online buy search keywords if shopping mode.
            """
            
            If NEW_SDK:
                Client = genai.Client(api_key=api_key)
                Response = client.models.generate_content(
                    Model='gemini-2.5-flash',
                    Contents=prompt
                )
                Outfits_text = response.text
            Else:
                Genai.configure(api_key=api_key)
                Model = genai.GenerativeModel('gemini-1.5-flash')
                Response = model.generate_content(prompt)
                Outfits_text = response.text
                
            St.session_state["generated_outfits"] = [o.strip() for o in outfits_text.split("\n\n") if o.strip()]
            St.success("Outfits generated!")

# Gallery & Interactions
St.header("👔 Curated Outfits")

If st.session_state["generated_outfits"]:
    For idx, outfit_text in enumerate(st.session_state["generated_outfits"]):
        With st.expander(f"Outfit Concept #{idx + 1}", expanded=True):
            St.write(outfit_text)
            
            Col1, col2, col3 = st.columns([1, 1, 2])
            
            With col1:
                If st.button(f"👁️ Preview #{idx + 1}", key=f"prev_{idx}"):
                    St.info("Rendering preview on model...")
                    # Display uploaded base image preview
                    Image = Image.open(uploaded_model)
                    St.image(image, caption=f"Model Try-On Preview #{idx + 1}")

            With col2:
                If st.button(f"💾 Save", key=f"save_{idx}"):
                    If outfit_text not in st.session_state["saved_outfits"]:
                        St.session_state["saved_outfits"].append(outfit_text)
                        St.toast(f"Saved Outfit #{idx + 1}!")

            With col3:
                If st.button(f"🗑️ Delete", key=f"del_{idx}"):
                    St.session_state["generated_outfits"].pop(idx)
                    St.rerun()

# Saved Closet
St.markdown("---")
St.header("🔒 Saved Closet")
If st.session_state["saved_outfits"]:
    For s_idx, item in enumerate(st.session_state["saved_outfits"]):
        St.info(f"**Saved Look #{s_idx + 1}:**\n\n{item}")
Else:
    St.write("No saved outfits yet.")
