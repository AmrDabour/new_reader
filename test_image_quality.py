import requests
import json
from pathlib import Path

# Configuration
API_URL = "https://new-reader-benk.onrender.com"  # أو استخدم localhost للاختبار المحلي
# API_URL = "http://localhost:8000"

def test_image_quality_check(image_path):
    """
    Test the new image quality check endpoint (now with automatic language detection)
    """
    print(f"\n=== Testing Image Quality Check (Auto Language Detection) ===")
    print(f"Image: {image_path}")
    
    try:
        # Check if image file exists
        if not Path(image_path).exists():
            print(f"Error: Image file not found at {image_path}")
            return None
            
        with open(image_path, 'rb') as f:
            files = {'image': ('test_form.jpg', f, 'image/jpeg')}
            # No need to send language parameter anymore!
            
            response = requests.post(
                f"{API_URL}/form/check-quality", 
                files=files
            )
            
            if response.status_code == 200:
                result = response.json()
                print("✅ Quality check successful!")
                print(f"Is suitable: {result['is_suitable']}")
                print(f"Feedback: {result['feedback']}")
                print(f"Status: {result['status']}")
                return result
            else:
                print(f"❌ Error: {response.status_code}")
                print(f"Response: {response.text}")
                return None
                
    except Exception as e:
        print(f"❌ Exception occurred: {str(e)}")
        return None

def test_form_analysis(image_path):
    """
    Test the form analysis endpoint (now with automatic language detection)
    """
    print(f"\n=== Testing Form Analysis (Auto Language Detection) ===")
    print(f"Image: {image_path}")
    
    try:
        with open(image_path, 'rb') as f:
            files = {'image': ('test_form.jpg', f, 'image/jpeg')}
            # No need to send language parameter anymore!
            
            response = requests.post(
                f"{API_URL}/form/analyze", 
                files=files
            )
            
            if response.status_code == 200:
                result = response.json()
                print("✅ Form analysis successful!")
                print(f"Auto-detected language direction: {result['language_direction']}")
                print(f"Fields found: {len(result['fields'])}")
                print(f"Form explanation: {result['form_explanation'][:100]}...")
                return result
            else:
                print(f"❌ Form analysis failed: {response.status_code}")
                print(f"Response: {response.text}")
                return None
                
    except Exception as e:
        print(f"❌ Exception in form analysis: {str(e)}")
        return None

def test_workflow(image_path):
    """
    Test the complete workflow: quality check first, then analysis if suitable
    (Both endpoints now auto-detect language)
    """
    print(f"\n=== Testing Complete Workflow (Full Auto-Detection) ===")
    
    # Step 1: Check image quality (auto-detects language for feedback)
    quality_result = test_image_quality_check(image_path)
    
    if not quality_result:
        print("❌ Quality check failed, stopping workflow")
        return
    
    # Step 2: If image is suitable, proceed with analysis (auto-detects language)
    if quality_result['is_suitable']:
        print("\n✅ Image is suitable, proceeding with form analysis...")
        analysis_result = test_form_analysis(image_path)
        
        if analysis_result:
            print(f"\n🎯 Workflow completed successfully!")
            print(f"   - Quality check: ✅ Suitable")
            print(f"   - Language detected: {analysis_result['language_direction']}")
            print(f"   - Fields found: {len(analysis_result['fields'])}")
        
    else:
        print("❌ Image is not suitable for analysis")
        print("User should follow the feedback and retake the photo")

def main():
    # Test with different images
    test_images = [
        # Add your test image paths here
        r"c:\Users\moham\OneDrive\Desktop\169599791_913406986138219_4555978638757445093_n.jpg",
        # You can add more test images here
    ]
    
    for image_path in test_images:
        if Path(image_path).exists():
            # Test complete workflow (both endpoints auto-detect language)
            test_workflow(image_path)
            
            # Test individual endpoints
            test_image_quality_check(image_path)
            test_form_analysis(image_path)
            
        else:
            print(f"⚠️  Skipping {image_path} - file not found")

if __name__ == "__main__":
    main() 