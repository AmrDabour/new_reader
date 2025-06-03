import google.generativeai as genai
import base64
import os
import json

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

def extract_fields_from_image(image_path):
    with open(image_path, "rb") as f:
        image_bytes = f.read()

    image_base64 = base64.b64encode(image_bytes).decode("utf-8")

    prompt = """
You are an AI assistant that extracts key form fields and their values from this image.
Return the results as a JSON object with field names as keys and extracted values as values.
"""

    model = genai.GenerativeModel("gemini-2.0-flash-lite")

    contents = [
        {
            "role": "user",
            "parts": [
                {"text": prompt}
            ]
        },
        {
            "role": "user",
            "parts": [
                {
                    "inline_data": {
                        "mime_type": "image/jpeg",
                        "data": image_base64
                    }
                }
            ]
        }
    ]

    response = model.generate_content(contents)
    # Extract the actual text from the Content object
    result_text = response.candidates[0].content.parts[0].text
    try:
        result_json = json.loads(result_text)
    except Exception:
        # If the model returns markdown or code block, try to extract JSON
        import re
        match = re.search(r"```(?:json)?\\s*(.*?)```", result_text, re.DOTALL)
        if match:
            json_str = match.group(1)
        else:
            # Fallback: extract substring between first '{' and last '}'
            start = result_text.find('{')
            end = result_text.rfind('}')
            if start != -1 and end != -1 and end > start:
                json_str = result_text[start:end+1]
            else:
                raise ValueError("Could not parse JSON from model response")
        result_json = json.loads(json_str)
    return result_json

if __name__ == "__main__":
    path = "path_to_your_form_image.jpg"
    fields = extract_fields_from_image(path)
    print(fields)
