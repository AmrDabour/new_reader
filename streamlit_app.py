import streamlit as st
import requests
import os
import base64
import json

# Assuming your FastAPI app is running on http://localhost:8000
FASTAPI_BASE_URL = "http://localhost:8000"

st.set_page_config(layout="wide")
st.title("Form Analyzer")

st.markdown("---")

st.header("Upload Document")
uploaded_file = st.file_uploader("Choose an image or PDF file", type=["png", "jpg", "jpeg", "pdf"])

if uploaded_file is not None:
    st.write("File uploaded successfully!")
    
    # Display file details
    st.write(f"File Name: {uploaded_file.name}")
    st.write(f"File Type: {uploaded_file.type}")
    st.write(f"File Size: {uploaded_file.size} bytes")

    # Prepare file for FastAPI
    files = {"file": (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type)}

    st.subheader("Checking File Quality...")
    try:
        response = requests.post(f"{FASTAPI_BASE_URL}/form/check-file", files=files)
        
        if response.status_code == 200:
            result = response.json()
            st.success("File quality check successful!")
            st.json(result)
            
            session_id = result.get("session_id")
            if session_id:
                st.session_state["session_id"] = session_id
                st.session_state["language_direction"] = result.get("language_direction")
                st.session_state["form_explanation"] = result.get("form_explanation")
                st.session_state["image_width"] = result.get("image_width")
                st.session_state["image_height"] = result.get("image_height")
                
                st.subheader("Form Explanation:")
                st.info(st.session_state["form_explanation"])
                
                if st.button("Analyze Form"):
                    st.session_state["analyze_form_clicked"] = True
            else:
                st.error("Session ID not received from backend.")
        else:
            st.error(f"Error checking file quality: {response.status_code} - {response.text}")
    except requests.exceptions.ConnectionError:
        st.error("Could not connect to the FastAPI backend. Please ensure it is running at "
                 f"{FASTAPI_BASE_URL}. You might need to run 'uvicorn main:app --reload' in your terminal "
                 "from the 'app' directory.")
    except Exception as e:
        st.error(f"An unexpected error occurred: {e}")

if "analyze_form_clicked" in st.session_state and st.session_state["analyze_form_clicked"]:
    st.subheader("Analyzing Form...")
    session_id = st.session_state.get("session_id")
    language_direction = st.session_state.get("language_direction")

    if session_id:
        try:
            analyze_data = {
                "session_id": session_id,
                "language_direction": language_direction
            }
            response = requests.post(f"{FASTAPI_BASE_URL}/form/analyze-form", data=analyze_data)

            if response.status_code == 200:
                analysis_result = response.json()
                st.success("Form analysis successful!")
                st.json(analysis_result)
                
                fields = analysis_result.get("fields", [])
                st.session_state["analyzed_fields"] = fields

                # Fetch and display the corrected image
                st.subheader("Original Image (Corrected):")
                image_response = requests.get(f"{FASTAPI_BASE_URL}/form/preview-analyze-image?session_id={session_id}&stage=corrected")
                if image_response.status_code == 200:
                    st.image(image_response.content, caption="Corrected Image", use_column_width=True)
                    st.session_state["original_image_b64"] = base64.b64encode(image_response.content).decode("utf-8")
                else:
                    st.warning(f"Could not retrieve corrected image: {image_response.status_code} - {image_response.text}")

                if fields:
                    st.subheader("Detected Fields:")
                    st.write("Enter values for the detected fields below:")
                    
                    # Initialize texts_dict if not already present
                    if "texts_dict" not in st.session_state:
                        st.session_state["texts_dict"] = {}

                    # Create input fields for each detected field
                    for i, field in enumerate(fields):
                        field_label = field.get('label', f'Field {i+1}')
                        field_box_id = field.get('box_id', f'box_{i}')
                        field_type = field.get('type', 'text') # Default to text if type is missing
                        
                        # Use a unique key for each input widget
                        widget_key = f"input_{field_box_id}"

                        if field_type == 'checkbox':
                            # For checkboxes, use st.checkbox
                            # Initialize with False if not already set
                            if field_box_id not in st.session_state["texts_dict"]:
                                st.session_state["texts_dict"][field_box_id] = False
                            
                            st.session_state["texts_dict"][field_box_id] = st.checkbox(
                                label=field_label,
                                value=st.session_state["texts_dict"].get(field_box_id),
                                key=widget_key
                            )
                        else:
                            # For other types (e.g., text, textbox), use st.text_input
                            st.session_state["texts_dict"][field_box_id] = st.text_input(
                                label=field_label,
                                value=st.session_state["texts_dict"].get(field_box_id, ""),
                                key=widget_key
                            )
                    
                    st.markdown("---")
                    st.subheader("Annotate Image")
                    if st.button("Generate Annotated Image"):
                        st.session_state["annotate_image_clicked"] = True

                else:
                    st.info("No fields detected in the form.")
            else:
                st.error(f"Error analyzing form: {response.status_code} - {response.text}")
        except requests.exceptions.ConnectionError:
            st.error("Could not connect to the FastAPI backend for analysis. Please ensure it is running.")
        except Exception as e:
            st.error(f"An unexpected error occurred during analysis: {e}")
    else:
        st.warning("No session ID found. Please upload a file first.")

if "annotate_image_clicked" in st.session_state and st.session_state["annotate_image_clicked"]:
    st.subheader("Generating Annotated Image...")
    session_id = st.session_state.get("session_id")
    original_image_b64 = st.session_state.get("original_image_b64")
    texts_dict = st.session_state.get("texts_dict", {})
    analyzed_fields = st.session_state.get("analyzed_fields", [])

    if session_id and original_image_b64 and texts_dict is not None and analyzed_fields:
        try:
            # The annotate-image endpoint expects ui_fields in a specific format.
            # We need to reconstruct it from analyzed_fields.
            ui_fields = []
            for field in analyzed_fields:
                ui_fields.append({
                    "box_id": field.get("box_id"),
                    "label": field.get("label"),
                    "type": field.get("type"),
                    "box": field.get("coordinates") # Assuming 'coordinates' from analysis maps to 'box' for annotation
                })

            annotate_data = {
                "original_image_b64": original_image_b64,
                "texts_dict": texts_dict,
                "ui_fields": ui_fields,
                "signature_image_b64": None, # Not implemented yet
                "signature_field_id": None   # Not implemented yet
            }
            
            # Send data as JSON in the request body
            response = requests.post(f"{FASTAPI_BASE_URL}/form/annotate-image", json=annotate_data)

            if response.status_code == 200:
                st.success("Annotated image generated successfully!")
                st.image(response.content, caption="Annotated Image", use_column_width=True)
            else:
                st.error(f"Error generating annotated image: {response.status_code} - {response.text}")
                st.write(response.text)
        except requests.exceptions.ConnectionError:
            st.error("Could not connect to the FastAPI backend for annotation. Please ensure it is running.")
        except Exception as e:
            st.error(f"An unexpected error occurred during annotation: {e}")
    else:
        st.warning("Missing data for annotation. Please ensure you have uploaded a file and analyzed the form.")