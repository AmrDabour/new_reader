import asyncio
import aiohttp
import logging
import os
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

class KeepAliveService:
    def __init__(self):
        self.is_running = False
        self.last_heartbeat: Optional[datetime] = None
        # تعديل الفاصل الزمني ليكون أقصر في CodeSpaces
        self.heartbeat_interval = 30 if os.getenv("CODESPACES") == "true" else 60  # seconds
        self.service_url = None
        self._task = None
        self._retry_count = 0
        self.max_retries = 3
    
    async def start(self, service_url: str):
        """بدء خدمة الـ keep-alive"""
        if self.is_running:
            return
        
        self.service_url = service_url
        self.is_running = True
        self._task = asyncio.create_task(self._heartbeat_loop())
        logger.info(f"تم بدء خدمة Keep-Alive (الفاصل الزمني: {self.heartbeat_interval} ثانية)")
    
    async def stop(self):
        """إيقاف خدمة الـ keep-alive"""
        if not self.is_running:
            return
        
        self.is_running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("تم إيقاف خدمة Keep-Alive")
    
    async def _heartbeat_loop(self):
        """حلقة إرسال نبضات القلب الدورية"""
        timeout = aiohttp.ClientTimeout(total=10)  # 10 seconds timeout
        
        while self.is_running:
            try:
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.get(self.service_url) as response:
                        if response.status == 200:
                            self.last_heartbeat = datetime.now()
                            self._retry_count = 0  # إعادة تعيين عداد المحاولات
                            logger.debug(f"Heartbeat successful at {self.last_heartbeat}")
                        else:
                            logger.warning(f"Heartbeat failed with status {response.status}")
                            await self._handle_failure()
            except Exception as e:
                logger.error(f"فشل في إرسال نبضة القلب: {str(e)}")
                await self._handle_failure()
            
            await asyncio.sleep(self.heartbeat_interval)
    
    async def _handle_failure(self):
        """التعامل مع فشل نبضة القلب"""
        self._retry_count += 1
        if self._retry_count >= self.max_retries:
            logger.warning(f"فشل في الاتصال بعد {self._retry_count} محاولات. سيتم المحاولة مرة أخرى في الدورة التالية.")
            self._retry_count = 0  # إعادة تعيين العداد للدورة التالية
        else:
            # انتظار قصير قبل المحاولة التالية
            await asyncio.sleep(2)

# إنشاء نسخة واحدة من الخدمة للاستخدام في جميع أنحاء التطبيق
keep_alive_service = KeepAliveService() 