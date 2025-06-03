import streamlit as st
from document_parser import extract_fields_from_image
from text_to_speech import speak_field
from speech_to_text import get_user_input
from word_generator import generate_word_document
from image_utils import extract_field_positions_with_vision, write_text_on_image, prepare_image_for_word
import tempfile
import os
import json
try:
    from PIL import Image
except ImportError:
    st.error("PIL (Pillow) is required. Please install it with: pip install Pillow")
    st.stop()

# Page config
st.set_page_config(
    page_title="Document Voice Filler",
    page_icon="📝",
    layout="wide"
)

# Session state initialization
if 'fields' not in st.session_state:
    st.session_state.fields = None
if 'responses' not in st.session_state:
    st.session_state.responses = {}
if 'filled_image' not in st.session_state:
    st.session_state.filled_image = None
if 'step' not in st.session_state:
    st.session_state.step = 1

# Header
st.title("📝 Document Voice Filler")
st.markdown("Upload a form image/PDF, speak your answers, and get a filled Word document!")

# Progress bar
progress_steps = ["Upload Document", "Extract Fields", "Voice Input", "Review & Verify", "Generate Document"]
current_step = st.session_state.step
progress = current_step / len(progress_steps)
st.progress(progress)
st.write(f"**Step {current_step}:** {progress_steps[current_step-1]}")

# Step 1: Upload Document
if st.session_state.step == 1:
    st.header("1. Upload Your Document")
    uploaded_file = st.file_uploader(
        "Choose a photo or PDF of a form",
        type=["pdf", "jpg", "jpeg", "png"],
        help="Upload a clear image of your form. The app can handle images taken at any angle."
    )

    if uploaded_file:
        # Save uploaded file temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(uploaded_file.name)[-1]) as tmp:
            tmp.write(uploaded_file.read())
            st.session_state.tmp_path = tmp.name

        # Display uploaded image
        if uploaded_file.type.startswith('image'):
            st.image(uploaded_file, caption="Uploaded Document", use_column_width=True)

        if st.button("Analyze Document", type="primary"):
            st.session_state.step = 2
            st.rerun()

# Step 2: Extract Fields
elif st.session_state.step == 2:
    st.header("2. Extracting Form Fields")
    
    with st.spinner("🔍 Analyzing document and detecting form fields..."):
        try:
            # Extract fields with positions using Google Cloud Vision
            field_data = extract_field_positions_with_vision(st.session_state.tmp_path)
            
            if field_data and len(field_data) > 0:
                st.session_state.fields = field_data
                st.success(f"✅ Found {len(field_data)} form fields!")
                
                # Display detected fields
                st.subheader("Detected Fields:")
                for i, field in enumerate(field_data, 1):
                    st.write(f"{i}. {field['label']}")
                
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("Start Voice Input", type="primary"):
                        st.session_state.step = 3
                        st.rerun()
                with col2:
                    if st.button("Back to Upload"):
                        st.session_state.step = 1
                        st.rerun()
            else:
                st.error("❌ No form fields detected. Please try with a clearer image.")
                if st.button("Try Again"):
                    st.session_state.step = 1
                    st.rerun()
        except Exception as e:
            st.error(f"Error analyzing document: {str(e)}")
            if st.button("Try Again"):
                st.session_state.step = 1
                st.rerun()

# Step 3: Voice Input
elif st.session_state.step == 3:
    st.header("3. Voice Input for Form Fields")
    
    if st.session_state.fields:
        st.info("🎤 Click 'Start Recording' for each field and speak your answer clearly.")
        
        # Display fields and collect responses
        for i, field_data in enumerate(st.session_state.fields):
            field_name = field_data['label']
            
            with st.expander(f"Field {i+1}: {field_name}", expanded=True):
                col1, col2, col3 = st.columns([2, 1, 1])
                
                with col1:
                    # Show current response if exists
                    current_response = st.session_state.responses.get(field_name, "")
                    if current_response:
                        st.write(f"**Current answer:** {current_response}")
                    else:
                        st.write("*No answer recorded yet*")
                
                with col2:
                    if st.button(f"🎤 Record", key=f"record_{i}"):
                        with st.spinner(f"🔊 Speaking field name: {field_name}"):
                            # Speak the field name
                            speak_field(field_name)
                        
                        with st.spinner("🎤 Recording your answer..."):
                            try:
                                # Get voice input
                                response = get_user_input()
                                if response:
                                    st.session_state.responses[field_name] = response
                                    st.success(f"✅ Recorded: {response}")
                                    st.rerun()
                                else:
                                    st.warning("No speech detected. Please try again.")
                            except Exception as e:
                                st.error(f"Recording error: {str(e)}")
                
                with col3:
                    if field_name in st.session_state.responses:
                        if st.button(f"🗑️ Clear", key=f"clear_{i}"):
                            del st.session_state.responses[field_name]
                            st.rerun()
        
        # Navigation buttons
        st.divider()
        col1, col2, col3 = st.columns([1, 1, 1])
        
        with col1:
            if st.button("⬅️ Back"):
                st.session_state.step = 2
                st.rerun()
        
        with col2:
            filled_count = len(st.session_state.responses)
            total_count = len(st.session_state.fields)
            st.write(f"**Progress:** {filled_count}/{total_count} fields filled")
        
        with col3:
            if len(st.session_state.responses) > 0:
                if st.button("Review Answers ➡️", type="primary"):
                    st.session_state.step = 4
                    st.rerun()

# Step 4: Review & Verify
elif st.session_state.step == 4:
    st.header("4. Review & Verify Your Answers")
    
    st.info("🔍 Review your answers. You can re-record any field if needed.")
    
    # Create filled image for preview
    if not st.session_state.filled_image:
        with st.spinner("📝 Creating preview of filled form..."):
            try:
                # Load original image
                original_image = Image.open(st.session_state.tmp_path)
                
                # Write text on image
                filled_image = write_text_on_image(
                    original_image, 
                    st.session_state.fields, 
                    st.session_state.responses
                )
                st.session_state.filled_image = filled_image
            except Exception as e:
                st.error(f"Error creating preview: {str(e)}")
    
    # Display filled image preview
    if st.session_state.filled_image:
        st.subheader("📋 Filled Form Preview")
        st.image(st.session_state.filled_image, caption="Preview of Filled Form", use_column_width=True)
    
    # Review answers with playback option
    st.subheader("🔊 Review Your Answers")
    
    for i, field_data in enumerate(st.session_state.fields):
        field_name = field_data['label']
        response = st.session_state.responses.get(field_name, "Not filled")
        
        with st.expander(f"Field {i+1}: {field_name}", expanded=False):
            col1, col2, col3 = st.columns([3, 1, 1])
            
            with col1:
                st.write(f"**Answer:** {response}")
            
            with col2:
                if response != "Not filled":
                    if st.button(f"🔊 Play", key=f"play_{i}"):
                        with st.spinner("🔊 Playing answer..."):
                            speak_field(f"{field_name}: {response}")
            
            with col3:
                if st.button(f"🎤 Re-record", key=f"rerecord_{i}"):
                    with st.spinner("🎤 Recording new answer..."):
                        try:
                            new_response = get_user_input()
                            if new_response:
                                st.session_state.responses[field_name] = new_response
                                # Reset filled image to regenerate
                                st.session_state.filled_image = None
                                st.success(f"✅ Updated: {new_response}")
                                st.rerun()
                        except Exception as e:
                            st.error(f"Recording error: {str(e)}")
    
    # Navigation buttons
    st.divider()
    col1, col2, col3 = st.columns([1, 1, 1])
    
    with col1:
        if st.button("⬅️ Back to Voice Input"):
            st.session_state.step = 3
            st.rerun()
    
    with col2:
        if st.button("🔄 Regenerate Preview"):
            st.session_state.filled_image = None
            st.rerun()
    
    with col3:
        if st.button("Generate Document ➡️", type="primary"):
            st.session_state.step = 5
            st.rerun()

# Step 5: Generate Document
elif st.session_state.step == 5:
    st.header("5. Generate Word Document")
    
    with st.spinner("📄 Generating your filled Word document..."):
        try:
            # Prepare image for Word document
            if st.session_state.filled_image:
                # Save filled image temporarily
                temp_image_path = tempfile.mktemp(suffix='.png')
                optimized_image = prepare_image_for_word(st.session_state.filled_image)
                optimized_image.save(temp_image_path, 'PNG', quality=95)
                
                # Generate Word document with filled image
                output_path = tempfile.mktemp(suffix='.docx')
                generate_word_document(st.session_state.responses, output_path, temp_image_path)
                
                st.success("✅ Document generated successfully!")
                
                # Display final preview
                col1, col2 = st.columns(2)
                
                with col1:
                    st.subheader("📋 Final Filled Form")
                    st.image(st.session_state.filled_image, caption="Final Filled Form")
                
                with col2:
                    st.subheader("📥 Download Options")
                    
                    # Download Word document
                    with open(output_path, "rb") as f:
                        st.download_button(
                            "📄 Download Word Document",
                            f.read(),
                            file_name="filled_document.docx",
                            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                        )
                    
                    # Download filled image
                    import io
                    img_buffer = io.BytesIO()
                    st.session_state.filled_image.save(img_buffer, format='PNG')
                    st.download_button(
                        "🖼️ Download Filled Image",
                        img_buffer.getvalue(),
                        file_name="filled_form.png",
                        mime="image/png"
                    )
                
                # Summary
                st.subheader("📊 Summary")
                st.write(f"**Total fields filled:** {len(st.session_state.responses)}")
                st.write(f"**Document type:** Form Document")
                
                # Clean up temp files
                try:
                    os.unlink(temp_image_path)
                    os.unlink(output_path)
                    if hasattr(st.session_state, 'tmp_path'):
                        os.unlink(st.session_state.tmp_path)
                except:
                    pass
                
        except Exception as e:
            st.error(f"❌ Error generating document: {str(e)}")
    
    # Start over button
    st.divider()
    if st.button("🔄 Start Over", type="primary"):
        # Reset session state
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()

# Sidebar with instructions
with st.sidebar:
    st.header("📖 How to Use")
    st.markdown("""
    1. **Upload** a photo or PDF of your form
    2. **Wait** for automatic field detection
    3. **Speak** your answers for each field
    4. **Review** and verify all answers
    5. **Download** your filled Word document
    
    ### 💡 Tips:
    - Speak clearly and at normal pace
    - You can re-record any field during review
    - The app works with images taken at any angle
    - Supported formats: JPG, PNG, PDF
    """)
    
    st.header("⚙️ Settings")
    st.info("Voice settings are automatically optimized for best results.")
    
    if st.button("🗑️ Clear All Data"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()
