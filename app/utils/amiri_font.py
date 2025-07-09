#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
تكوين خط Amiri للنصوص العربية
Amiri font configuration for Arabic text
"""

from PIL import ImageFont
import arabic_reshaper
from bidi.algorithm import get_display
from typing import Optional

class AmiriFontManager:
    """مدير خط Amiri للنصوص العربية"""
    
    # مسارات خط Amiri المحتملة (حسب تثبيت fonts-amiri في Docker)
    AMIRI_FONT_PATHS = [
        "/usr/share/fonts/truetype/amiri/amiri-regular.ttf",
        "/usr/share/fonts/truetype/amiri/Amiri-Regular.ttf",
        "/usr/share/fonts/opentype/amiri/Amiri-Regular.otf", 
        "/usr/share/fonts/TTF/Amiri-Regular.ttf",
        "/usr/share/fonts/opentype/amiri/amiri-regular.otf"
    ]
    
    # خطوط احتياطية للنصوص العربية
    ARABIC_FALLBACK_FONTS = [
        "/usr/share/fonts/truetype/noto/NotoSansArabic-Regular.ttf",
        "/usr/share/fonts/opentype/noto/NotoSansArabic-Regular.ttf",
        "/usr/share/fonts/truetype/fonts-arabic/Scheherazade-Regular.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    ]
    
    def __init__(self):
        self._amiri_font_cache = {}
        self._fallback_font_cache = {}
        self._amiri_available = None
        self._best_arabic_font_path = None
    
    def is_amiri_available(self) -> bool:
        """التحقق من توفر خط Amiri"""
        if self._amiri_available is not None:
            return self._amiri_available
            
        for font_path in self.AMIRI_FONT_PATHS:
            try:
                ImageFont.truetype(font_path, 16)
                self._amiri_available = True
                self._best_arabic_font_path = font_path
                print(f"🎯 تم العثور على خط Amiri: {font_path}")
                return True
            except (IOError, OSError):
                continue
        
        self._amiri_available = False
        print("⚠️ خط Amiri غير متوفر، سيتم البحث عن خط عربي بديل")
        
        # البحث عن خط عربي بديل
        for font_path in self.ARABIC_FALLBACK_FONTS:
            try:
                ImageFont.truetype(font_path, 16)
                self._best_arabic_font_path = font_path
                print(f"✅ تم العثور على خط عربي بديل: {font_path}")
                break
            except (IOError, OSError):
                continue
        
        return False
    
    def get_arabic_font(self, size: int = 16) -> ImageFont.FreeTypeFont:
        """الحصول على خط عربي (Amiri أو بديل) بحجم محدد"""
        
        # التحقق من الذاكرة المؤقتة أولاً
        cache_key = f"{size}"
        if cache_key in self._amiri_font_cache:
            return self._amiri_font_cache[cache_key]
        
        if not self.is_amiri_available() and self._best_arabic_font_path is None:
            print("⚠️ لا توجد خطوط عربية متوفرة، سيتم استخدام الخط الافتراضي")
            return ImageFont.load_default()
        
        try:
            font = ImageFont.truetype(self._best_arabic_font_path, size)
            self._amiri_font_cache[cache_key] = font
            return font
        except (IOError, OSError):
            print(f"❌ فشل في تحميل الخط: {self._best_arabic_font_path}")
            return ImageFont.load_default()
    
    def process_arabic_text(self, text: str) -> str:
        """معالجة النص العربي للعرض الصحيح"""
        try:
            # تنظيف النص
            cleaned_text = text.strip()
            
            # لا نطبق get_display لأننا نريد النص كما هو (من اليمين لليسار)
            # نطبق فقط إعادة تشكيل الحروف لمعالجة أشكال الحروف
            reshaped_text = arabic_reshaper.reshape(cleaned_text)
            
            # استخدم get_display فقط إذا كنا نريد عرض النص في بيئة تدعم LTR فقط
            # لكن في حالتنا نحتاج النص العربي بشكله الطبيعي RTL
            # display_text = reshaped_text  # نستخدم النص بعد إعادة التشكيل فقط
            
            # للتجربة: استخدم get_display مع تحديد اتجاه من اليمين إلى اليسار صراحةً
            display_text = reshaped_text  # بدون get_display
            
            print(f"📝 معالجة النص العربي: '{text}' -> '{reshaped_text}'")
            return reshaped_text
            
        except Exception as e:
            print(f"⚠️ فشل في معالجة النص العربي: {e}")
            return text
    
    def get_font_info(self) -> dict:
        """الحصول على معلومات الخط المستخدم"""
        return {
            "amiri_available": self.is_amiri_available(),
            "best_font_path": self._best_arabic_font_path,
            "font_name": "Amiri" if self._amiri_available else "Arabic Fallback",
            "cached_sizes": list(self._amiri_font_cache.keys())
        }

# إنشاء مثيل عام للاستخدام في التطبيق
amiri_manager = AmiriFontManager()

def get_amiri_font(size: int = 16) -> ImageFont.FreeTypeFont:
    """دالة مساعدة للحصول على خط Amiri"""
    return amiri_manager.get_arabic_font(size)

def process_arabic_text_for_display(text: str) -> str:
    """دالة مساعدة لمعالجة النص العربي"""
    # استخدام الدالة المحسنة من ملف arabic.py بدلاً من الدالة القديمة
    from app.utils.arabic import reshape_arabic_text
    return reshape_arabic_text(text, for_display=False)

def is_amiri_font_available() -> bool:
    """دالة مساعدة للتحقق من توفر خط Amiri"""
    return amiri_manager.is_amiri_available()

if __name__ == "__main__":
    # اختبار سريع
    print("🧪 اختبار مدير خط Amiri")
    print("=" * 40)
    
    manager = AmiriFontManager()
    info = manager.get_font_info()
    
    print(f"معلومات الخط:")
    print(f"  - متوفر Amiri: {info['amiri_available']}")
    print(f"  - أفضل خط: {info['best_font_path']}")
    print(f"  - اسم الخط: {info['font_name']}")
    
    # اختبار معالجة نص
    test_text = "مرحباً بكم في خط أميري الجميل"
    processed = manager.process_arabic_text(test_text)
    print(f"\nاختبار النص:")
    print(f"  - الأصلي: {test_text}")
    print(f"  - المعالج: {processed}")
    
    # اختبار تحميل خط
    font = manager.get_arabic_font(24)
    print(f"  - تم تحميل خط بحجم 24: {type(font)}")
