import uuid
import time
from typing import Dict, Any, Optional
from threading import Lock

class SessionService:
    def __init__(self, session_timeout: int = 3600):  # 1 hour timeout
        self.sessions: Dict[str, Dict[str, Any]] = {}
        self.session_timeout = session_timeout
        self.lock = Lock()
    
    def create_session(self) -> str:
        """Create a new session and return session ID"""
        with self.lock:
            session_id = str(uuid.uuid4())
            self.sessions[session_id] = {
                'created_at': time.time(),
                'last_access': time.time(),
                'data': {}
            }
            return session_id
    
    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session data by ID"""
        with self.lock:
            if session_id not in self.sessions:
                return None
            
            session = self.sessions[session_id]
            
            # Check if session expired
            if time.time() - session['last_access'] > self.session_timeout:
                del self.sessions[session_id]
                return None
            
            # Update last access time
            session['last_access'] = time.time()
            return session['data']
    
    def update_session(self, session_id: str, key: str, value: Any) -> bool:
        """Update session data"""
        with self.lock:
            if session_id not in self.sessions:
                return False
            
            session = self.sessions[session_id]
            
            # Check if session expired
            if time.time() - session['last_access'] > self.session_timeout:
                del self.sessions[session_id]
                return False
            
            # Update last access time and data
            session['last_access'] = time.time()
            session['data'][key] = value
            return True
    
    def delete_session(self, session_id: str) -> bool:
        """Delete a session"""
        with self.lock:
            if session_id in self.sessions:
                del self.sessions[session_id]
                return True
            return False
    
    def cleanup_expired_sessions(self):
        """Remove expired sessions"""
        with self.lock:
            current_time = time.time()
            expired_sessions = []
            
            for session_id, session in self.sessions.items():
                if current_time - session['last_access'] > self.session_timeout:
                    expired_sessions.append(session_id)
            
            for session_id in expired_sessions:
                del self.sessions[session_id]
    
    def get_session_count(self) -> int:
        """Get current number of active sessions"""
        with self.lock:
            return len(self.sessions) 