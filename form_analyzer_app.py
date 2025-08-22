#!/usr/bin/env python3
"""
Form Analyzer Streamlit App
Comprehensive form analysis and filling application
"""

import streamlit as st
import sys
import io
import base64
import requests
from PIL import Image
from typing import Dict, List, Any

# Add the app directory to Python path
sys.path.append("app")

# Import our services
try:
    from app.services.image import ImageService
    from app.services.yolo import YOLOService
    from app.services.gemini import GeminiService
    from app.config import get_settings
except ImportError as e:
    st.error(f"❌ Error importing services: {e}")
    st.stop()

# Configure page
st.set_page_config(
    page_title="📋 Form Analyzer & Filler",
    page_icon="📋",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Initialize session state
if "analyzed_form" not in st.session_state:
    st.session_state.analyzed_form = None
if "form_fields" not in st.session_state:
    st.session_state.form_fields = []
if "field_values" not in st.session_state:
    st.session_state.field_values = {}
if "corrected_image" not in st.session_state:
    st.session_state.corrected_image = None


@st.cache_resource
def load_services():
    """Load and cache all services"""
    try:
        settings = get_settings()
        image_service = ImageService()
        yolo_service = YOLOService()
        gemini_service = GeminiService()
        return image_service, yolo_service, gemini_service, settings
    except Exception as e:
        st.error(f"Error loading services: {e}")
        return None, None, None, None


def analyze_form_with_api(image_data: bytes, language_direction: str = "auto") -> dict:
    """Analyze form using the existing API"""
    try:
        # Convert image to base64
        image_b64 = base64.b64encode(image_data).decode("utf-8")

        # Prepare API request for FastAPI endpoints
        files = {"file": ("form.png", image_data, "image/png")}
        data = {"language_direction": language_direction, "analyze_images": True}

        # Try to use the FastAPI backend first (two-step process)
        try:
            # Step 1: Upload image to check-file endpoint
            check_response = requests.post(
                "http://localhost:8000/form/check-file", files=files
            )

            if check_response.status_code == 200:
                check_result = check_response.json()
                session_id = check_result.get("session_id")

                if session_id:
                    # Step 2: Analyze form using session_id
                    analyze_data = {
                        "session_id": session_id,
                        "language_direction": language_direction,
                    }

                    analyze_response = requests.post(
                        "http://localhost:8000/form/analyze-form", data=analyze_data
                    )

                    if analyze_response.status_code == 200:
                        result = analyze_response.json()
                        return {
                            "success": True,
                            "corrected_image": result.get("corrected_image"),
                            "fields": result.get("fields", []),
                            "language_direction": result.get(
                                "language_direction", "ltr"
                            ),
                            "rotation_angle": result.get("rotation_angle", 0),
                            "scan_info": result.get("scan_info", {}),
                        }
                    else:
                        st.warning(
                            f"⚠️ Analysis API call failed with status {analyze_response.status_code}. Using direct services."
                        )
                else:
                    st.warning(
                        "⚠️ No session_id received from check-file. Using direct services."
                    )
            else:
                st.warning(
                    f"⚠️ Image upload failed with status {check_response.status_code}. Using direct services."
                )

        except requests.exceptions.ConnectionError:
            st.warning(
                "⚠️ FastAPI backend not running on port 8000. Using direct services."
            )
        except Exception as api_error:
            st.warning(f"⚠️ API error: {api_error}. Using direct services.")

        # Fallback to direct services
        image_service, yolo_service, gemini_service, settings = load_services()

        if not all([image_service, yolo_service, gemini_service]):
            raise Exception("Failed to load services")

        # Load image
        image = Image.open(io.BytesIO(image_data))

        # Correct image orientation
        corrected_image = image_service.correct_image_orientation(image)
        rotation_angle = 0  # Basic correction doesn't return angle
        scan_info = {"method": "basic_correction"}

        # Detect fields using YOLO
        if language_direction == "auto":
            fields_data, detected_lang = yolo_service.detect_fields(corrected_image)
        else:
            fields_data = yolo_service.detect_fields_with_language(
                corrected_image, language_direction
            )
            detected_lang = language_direction

        # Create annotated image for AI analysis
        annotated_image = image_service.create_annotated_image_for_gpt(
            corrected_image, fields_data
        )

        # Analyze with Gemini
        gpt_results = gemini_service.get_form_fields_only(
            annotated_image, detected_lang
        )

        # Merge results
        ui_fields = image_service.combine_yolo_and_gpt_results(fields_data, gpt_results)

        # Convert image to base64 for response
        img_buffer = io.BytesIO()
        corrected_image.save(img_buffer, format="PNG")
        corrected_image_b64 = base64.b64encode(img_buffer.getvalue()).decode("utf-8")

        return {
            "success": True,
            "corrected_image": corrected_image_b64,
            "fields": ui_fields,
            "language_direction": detected_lang,
            "rotation_angle": rotation_angle,
            "scan_info": scan_info,
        }

    except Exception as e:
        return {"success": False, "error": str(e)}


def create_filled_form(
    corrected_image_b64: str, ui_fields: List[dict], texts_dict: Dict[str, Any]
) -> str:
    """Create filled form image"""
    try:
        image_service, _, _, _ = load_services()
        if not image_service:
            raise Exception("Failed to load image service")

        # Decode base64 image
        image_bytes = base64.b64decode(corrected_image_b64)
        image = Image.open(io.BytesIO(image_bytes))

        # Create final annotated image
        filled_image = image_service.create_final_annotated_image(
            image, texts_dict, ui_fields
        )

        # Convert back to base64
        img_buffer = io.BytesIO()
        filled_image.save(img_buffer, format="PNG")
        return base64.b64encode(img_buffer.getvalue()).decode("utf-8")

    except Exception as e:
        st.error(f"Error creating filled form: {e}")
        return corrected_image_b64


def main():
    st.title("📋 Smart Form Analyzer & Filler")
    st.markdown("Upload a form image to automatically detect and fill fields")

    # Sidebar for settings
    with st.sidebar:
        st.header("⚙️ Settings")
        language_direction = st.selectbox(
            "Language Direction",
            ["auto", "ltr", "rtl"],
            help="auto = detect automatically, ltr = left-to-right, rtl = right-to-left",
        )

        st.markdown("---")
        st.subheader("📖 Instructions")
        st.markdown(
            """
        1. **Upload** your form image
        2. **Analyze** to detect fields
        3. **Fill** the detected fields
        4. **Download** the completed form
        """
        )

    # Main content area
    tab1, tab2, tab3 = st.tabs(["📤 Upload & Analyze", "✏️ Fill Form", "📥 Download"])

    with tab1:
        st.subheader("📤 Upload Form Image")

        uploaded_file = st.file_uploader(
            "Choose a form image",
            type=["png", "jpg", "jpeg", "bmp", "tiff"],
            help="Upload a clear image of the form you want to fill",
        )

        if uploaded_file is not None:
            # Display uploaded image
            col1, col2 = st.columns([1, 1])

            with col1:
                st.write("**📋 Original Form**")
                image = Image.open(uploaded_file)
                st.image(image, caption="Uploaded form", use_container_width=True)

            with col2:
                st.write("**🔍 Analysis Status**")

                if st.button(
                    "🚀 Analyze Form", type="primary", use_container_width=True
                ):
                    with st.spinner("🔄 Analyzing form... This may take a moment..."):
                        # Read image data
                        image_data = uploaded_file.getvalue()

                        # Analyze form
                        result = analyze_form_with_api(image_data, language_direction)

                        if result["success"]:
                            # Store results in session state
                            st.session_state.analyzed_form = result
                            st.session_state.corrected_image = result["corrected_image"]
                            st.session_state.form_fields = result["fields"]
                            st.session_state.field_values = {}

                            st.success("✅ Analysis complete!")
                            st.info(f"🌐 Language: {result['language_direction']}")
                            st.info(f"🔄 Rotation: {result['rotation_angle']}°")
                            st.info(f"📊 Found {len(result['fields'])} fields")

                            # Show corrected image
                            if result["corrected_image"]:
                                corrected_img_data = base64.b64decode(
                                    result["corrected_image"]
                                )
                                corrected_img = Image.open(
                                    io.BytesIO(corrected_img_data)
                                )
                                st.image(
                                    corrected_img,
                                    caption="Corrected & Processed",
                                    use_container_width=True,
                                )

                        else:
                            st.error(f"❌ Analysis failed: {result['error']}")

    with tab2:
        st.subheader("✏️ Fill Form Fields")

        if st.session_state.form_fields:
            st.success(f"📊 Found {len(st.session_state.form_fields)} fields to fill")

            # Create form for field values
            with st.form("field_values_form"):
                st.write("**📝 Enter values for detected fields:**")

                for i, field in enumerate(st.session_state.form_fields):
                    field_id = field.get("box_id", f"field_{i}")
                    field_label = field.get("label", f"Field {i+1}")
                    field_type = field.get("type", "textbox")

                    col1, col2, col3 = st.columns([2, 2, 1])

                    with col1:
                        st.write(f"**{field_label or 'Unlabeled Field'}**")
                        st.caption(f"Type: {field_type} | ID: {field_id}")

                    with col2:
                        if field_type == "checkbox":
                            # Checkbox field
                            value = st.checkbox(
                                "Mark as checked",
                                key=f"field_{field_id}",
                                value=st.session_state.field_values.get(
                                    field_id, False
                                ),
                            )
                            st.session_state.field_values[field_id] = value

                        else:
                            # Text field
                            value = st.text_input(
                                f"Value for {field_label or 'field'}",
                                key=f"field_{field_id}",
                                value=st.session_state.field_values.get(field_id, ""),
                                placeholder="Enter text here...",
                            )
                            if value.strip():
                                st.session_state.field_values[field_id] = value
                            elif field_id in st.session_state.field_values:
                                del st.session_state.field_values[field_id]

                    with col3:
                        # Preview the field location (simplified)
                        field_box = field.get("box", [0, 0, 50, 20])
                        st.caption(f"📍 Position: ({field_box[0]}, {field_box[1]})")

                submitted = st.form_submit_button(
                    "💾 Update Field Values", type="primary"
                )

                if submitted:
                    st.success("✅ Field values updated!")

            # Show current values summary
            if st.session_state.field_values:
                st.subheader("📝 Current Values Summary")
                for field_id, value in st.session_state.field_values.items():
                    # Find field info
                    field_info = next(
                        (
                            f
                            for f in st.session_state.form_fields
                            if f.get("box_id") == field_id
                        ),
                        {},
                    )
                    field_label = field_info.get("label", field_id)
                    field_type = field_info.get("type", "text")

                    if field_type == "checkbox":
                        status = "☑️ Checked" if value else "☐ Unchecked"
                        st.write(f"**{field_label}**: {status}")
                    else:
                        st.write(f"**{field_label}**: {value}")
        else:
            st.info("👆 Please analyze a form first in the 'Upload & Analyze' tab")

    with tab3:
        st.subheader("📥 Download Filled Form")

        # Check if we have analyzed form and detected fields
        has_analyzed_form = (
            st.session_state.analyzed_form
            and st.session_state.form_fields
            and len(st.session_state.form_fields) > 0
        )

        # Debug info (can be removed later)
        if st.checkbox("🔍 Debug Session State", value=False):
            st.write("**Debug Info:**")
            st.write(f"- analyzed_form exists: {bool(st.session_state.analyzed_form)}")
            st.write(f"- form_fields exists: {bool(st.session_state.form_fields)}")
            st.write(
                f"- form_fields count: {len(st.session_state.form_fields) if st.session_state.form_fields else 0}"
            )
            st.write(
                f"- corrected_image exists: {bool(st.session_state.corrected_image)}"
            )
            st.write(
                f"- field_values count: {len(st.session_state.field_values) if st.session_state.field_values else 0}"
            )
            st.write(f"- has_analyzed_form: {has_analyzed_form}")

        if has_analyzed_form:

            col1, col2 = st.columns([1, 1])

            with col1:
                st.write("**📋 Preview**")
                if st.button(
                    "🎨 Generate Filled Form", type="primary", use_container_width=True
                ):
                    with st.spinner("🖍️ Creating filled form..."):
                        # Get corrected image from session state or analyzed form
                        corrected_img_b64 = (
                            st.session_state.corrected_image
                            or st.session_state.analyzed_form.get("corrected_image")
                        )

                        filled_image_b64 = create_filled_form(
                            corrected_img_b64,
                            st.session_state.form_fields,
                            st.session_state.field_values,
                        )

                        # Display filled form
                        filled_img_data = base64.b64decode(filled_image_b64)
                        filled_img = Image.open(io.BytesIO(filled_img_data))
                        st.image(
                            filled_img, caption="Filled Form", use_container_width=True
                        )

                        # Download button
                        st.download_button(
                            label="📥 Download Filled Form",
                            data=filled_img_data,
                            file_name="filled_form.png",
                            mime="image/png",
                            use_container_width=True,
                        )

            with col2:
                st.write("**📊 Fill Summary**")
                total_fields = len(st.session_state.form_fields)
                filled_fields = len(st.session_state.field_values)

                st.metric("Total Fields", total_fields)
                st.metric("Filled Fields", filled_fields)
                st.metric(
                    "Completion",
                    f"{(filled_fields/total_fields*100) if total_fields > 0 else 0:.1f}%",
                )

                if st.session_state.field_values:
                    st.write("**✅ Filled Fields:**")
                    for field_id, value in st.session_state.field_values.items():
                        field_info = next(
                            (
                                f
                                for f in st.session_state.form_fields
                                if f.get("box_id") == field_id
                            ),
                            {},
                        )
                        field_label = field_info.get("label", field_id)
                        field_type = field_info.get("type", "text")

                        if field_type == "checkbox":
                            icon = "☑️" if value else "☐"
                            st.write(f"{icon} {field_label}")
                        else:
                            st.write(f"📝 {field_label}: {value[:20]}...")
        else:
            st.info("👆 Please analyze a form and fill some fields first")

    # Footer
    st.markdown("---")
    st.markdown("**🔧 System Status**")
    col1, col2, col3 = st.columns(3)

    with col1:
        if st.session_state.analyzed_form:
            st.success("✅ Form Analyzed")
        else:
            st.info("⏳ No Form Analyzed")

    with col2:
        if st.session_state.form_fields:
            st.success(f"✅ {len(st.session_state.form_fields)} Fields Detected")
        else:
            st.info("⏳ No Fields Detected")

    with col3:
        if st.session_state.field_values:
            st.success(f"✅ {len(st.session_state.field_values)} Fields Filled")
        else:
            st.info("⏳ No Fields Filled")


if __name__ == "__main__":
    main()
