#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
تهيئة خط عربي للنصوص العربية (بدون الاعتماد على Amiri)
Arabic font setup for Arabic text without relying on Amiri.
"""

from PIL import ImageFont
import arabic_reshaper
from bidi.algorithm import get_display
from typing import Optional
import os

class AmiriFontManager:
    """مدير خطوط عربية: يعتمد مباشرة على خط متوفر (بدون البحث عن Amiri)."""

    # نعتمد مباشرة على خط متوفر في معظم توزيعات لينكس
    PREFERRED_ARABIC_FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    
    # قائمة احتياطية بسيطة عند الحاجة
    ARABIC_FALLBACK_FONTS = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/noto/NotoSansArabic-Regular.ttf",
        "/usr/share/fonts/opentype/noto/NotoSansArabic-Regular.ttf",
        "/usr/share/fonts/truetype/fonts-arabic/Scheherazade-Regular.ttf",
    ]
    
    def __init__(self):
        self._font_cache = {}
        self._best_arabic_font_path = None
        self._init_best_font_path()
    
    def is_amiri_available(self) -> bool:
        """يحافظ على التوافيق: لا نعتمد على Amiri إطلاقاً."""
        return False

    def _init_best_font_path(self) -> None:
        """تعيين أفضل مسار للخط العربي المتاح بصمت (بدون طباعة)."""
        candidates = [self.PREFERRED_ARABIC_FONT] + [p for p in self.ARABIC_FALLBACK_FONTS if p != self.PREFERRED_ARABIC_FONT]
        for font_path in candidates:
            try:
                ImageFont.truetype(font_path, 16)
                self._best_arabic_font_path = font_path
                return
            except (IOError, OSError):
                continue
        # كحل أخير: اترك المسار None وسيتم استخدام الخط الافتراضي لاحقاً
    
    def get_arabic_font(self, size: int = 16) -> ImageFont.FreeTypeFont:
        """الحصول على خط عربي (Amiri أو بديل) بحجم محدد"""
        
        # التحقق من الذاكرة المؤقتة أولاً
        cache_key = f"{size}"
        if cache_key in self._font_cache:
            return self._font_cache[cache_key]

        if self._best_arabic_font_path is None:
            return ImageFont.load_default()

        try:
            font = ImageFont.truetype(self._best_arabic_font_path, size)
            self._font_cache[cache_key] = font
            return font
        except (IOError, OSError):
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
            
            return reshaped_text
            
        except Exception as e:
            return text
    
    def get_font_info(self) -> dict:
        """الحصول على معلومات الخط المستخدم"""
        return {
            "amiri_available": False,
            "best_font_path": self._best_arabic_font_path,
            "font_name": "Arabic Fallback",
            "cached_sizes": list(self._font_cache.keys())
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
    # اختبار سريع (صامت)
    manager = AmiriFontManager()
    info = manager.get_font_info()
    print(info)
