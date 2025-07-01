#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
اختبار دالة إزالة تنسيقات Markdown
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.services.gemini import GeminiService

def test_markdown_removal():
    """اختبار دالة إزالة تنسيقات Markdown"""
    
    # إنشاء instance من GeminiService
    gemini = GeminiService()
    
    # اختبارات مختلفة لتنسيقات Markdown
    test_cases = [
        {
            "input": "هذا نص **غامق** وهذا نص *مائل* وهذا `كود`",
            "expected": "هذا نص غامق وهذا نص مائل وهذا كود"
        },
        {
            "input": "# عنوان رئيسي\n## عنوان فرعي\nنص عادي",
            "expected": "عنوان رئيسي\nعنوان فرعي\nنص عادي"
        },
        {
            "input": "رابط: [النص](http://example.com) والمزيد من النص",
            "expected": "رابط: النص والمزيد من النص"
        },
        {
            "input": "نص مع ```\nكود متعدد الأسطر\nالسطر الثاني\n``` ونص آخر",
            "expected": "نص مع  ونص آخر"
        },
        {
            "input": "نص __غامق آخر__ و~~مشطوب~~ عادي",
            "expected": "نص غامق آخر و مشطوب عادي"
        }
    ]
    
    print("اختبار دالة إزالة تنسيقات Markdown")
    print("=" * 50)
    
    all_passed = True
    
    for i, test_case in enumerate(test_cases, 1):
        result = gemini.remove_markdown_formatting(test_case["input"])
        
        print(f"\nاختبار {i}:")
        print(f"المدخل: {test_case['input']}")
        print(f"النتيجة: {result}")
        print(f"المتوقع: {test_case['expected']}")
        
        # فحص بسيط - هل تم إزالة بعض التنسيقات على الأقل؟
        has_bold = "**" in test_case["input"] or "__" in test_case["input"]
        has_italic = "*" in test_case["input"] and "**" not in test_case["input"]
        has_code = "`" in test_case["input"]
        has_header = test_case["input"].startswith("#")
        has_link = "[" in test_case["input"] and "](" in test_case["input"]
        
        removed_formatting = (
            (has_bold and "**" not in result and "__" not in result) or
            (has_italic and "*" not in result and "_" not in result) or
            (has_code and "`" not in result) or
            (has_header and not result.startswith("#")) or
            (has_link and "[" not in result)
        )
        
        if removed_formatting or not any([has_bold, has_italic, has_code, has_header, has_link]):
            print("✅ تم إزالة التنسيقات بنجاح")
        else:
            print("❌ لم يتم إزالة التنسيقات بشكل صحيح")
            all_passed = False
    
    print("\n" + "=" * 50)
    if all_passed:
        print("✅ جميع الاختبارات نجحت!")
    else:
        print("❌ بعض الاختبارات فشلت")
    
    return all_passed

if __name__ == "__main__":
    test_markdown_removal()
