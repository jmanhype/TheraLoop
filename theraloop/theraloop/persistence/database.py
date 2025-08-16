"""
Database persistence layer for TheraLoop conversations and escalations.
Uses SQLite for simplicity, can be replaced with PostgreSQL in production.
"""

import sqlite3
import json
import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any
from contextlib import contextmanager
import logging

logger = logging.getLogger(__name__)

class ConversationDB:
    """Manages conversation and escalation persistence"""
    
    def __init__(self, db_path: str = "theraloop.db"):
        self.db_path = db_path
        self._configure_pragma()  # Set PRAGMA before creating tables
        self.init_database()
    
    @contextmanager
    def get_connection(self):
        """Context manager for database connections"""
        # Use check_same_thread=False for thread safety in FastAPI
        conn = sqlite3.connect(self.db_path, check_same_thread=False, timeout=30.0)
        conn.row_factory = sqlite3.Row  # Enable column access by name
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"Database error: {e}")
            raise
        finally:
            conn.close()
    
    def init_database(self):
        """Initialize database schema"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Conversations table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id TEXT PRIMARY KEY,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    metadata TEXT
                )
            """)
            
            # Messages table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id TEXT PRIMARY KEY,
                    conversation_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    confidence_score REAL,
                    token_logprobs TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (conversation_id) REFERENCES conversations(id)
                )
            """)
            
            # Escalations table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS escalations (
                    id TEXT PRIMARY KEY,
                    conversation_id TEXT NOT NULL,
                    user_text TEXT NOT NULL,
                    assistant_text TEXT,
                    confidence_score REAL,
                    policy_tag TEXT,
                    status TEXT DEFAULT 'pending',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    resolved_at TIMESTAMP,
                    resolution_notes TEXT,
                    FOREIGN KEY (conversation_id) REFERENCES conversations(id)
                )
            """)
            
            # Create indexes for performance
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_messages_conversation 
                ON messages(conversation_id)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_escalations_conversation 
                ON escalations(conversation_id)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_escalations_status 
                ON escalations(status)
            """)
            
            logger.info("Database initialized successfully")
    
    def _configure_pragma(self):
        """Configure database PRAGMA settings once at initialization"""
        # Use a raw connection without the context manager to set PRAGMAs
        # This must be done before any table creation for consistency
        conn = sqlite3.connect(self.db_path, check_same_thread=False, timeout=30.0)
        try:
            # Enable Write-Ahead Logging for better concurrency
            # WAL mode persists across connections once set
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            # Additional performance optimizations
            conn.execute("PRAGMA cache_size=10000")  # Increase cache size
            conn.execute("PRAGMA temp_store=MEMORY")  # Use memory for temp tables
            conn.commit()
            logger.info("Database PRAGMA settings configured")
        except Exception as e:
            logger.warning(f"Could not set PRAGMA settings: {e}")
            # Non-fatal - database will still work with defaults
        finally:
            conn.close()
    
    def create_conversation(self, metadata: Optional[Dict[str, Any]] = None) -> str:
        """Create a new conversation"""
        conversation_id = f"conv_{uuid.uuid4().hex[:12]}"
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO conversations (id, metadata)
                VALUES (?, ?)
            """, (conversation_id, json.dumps(metadata or {})))
        
        logger.info(f"Created conversation {conversation_id}")
        return conversation_id
    
    def add_message(
        self, 
        conversation_id: str,
        role: str,
        content: str,
        confidence_score: Optional[float] = None,
        token_logprobs: Optional[List[float]] = None
    ) -> str:
        """Add a message to a conversation"""
        message_id = f"msg_{uuid.uuid4().hex[:12]}"
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO messages (
                    id, conversation_id, role, content, 
                    confidence_score, token_logprobs
                )
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                message_id,
                conversation_id,
                role,
                content,
                confidence_score,
                json.dumps(token_logprobs) if token_logprobs else None
            ))
            
            # Update conversation timestamp
            cursor.execute("""
                UPDATE conversations 
                SET updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (conversation_id,))
        
        logger.debug(f"Added message {message_id} to conversation {conversation_id}")
        return message_id
    
    def create_escalation(
        self,
        conversation_id: str,
        user_text: str,
        assistant_text: Optional[str] = None,
        confidence_score: Optional[float] = None,
        policy_tag: Optional[str] = None
    ) -> str:
        """Create an escalation record"""
        escalation_id = f"esc_{uuid.uuid4().hex[:12]}"
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO escalations (
                    id, conversation_id, user_text, assistant_text,
                    confidence_score, policy_tag
                )
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                escalation_id,
                conversation_id,
                user_text,
                assistant_text,
                confidence_score,
                policy_tag
            ))
        
        logger.info(f"Created escalation {escalation_id} for conversation {conversation_id}")
        return escalation_id
    
    def conversation_exists(self, conversation_id: str) -> bool:
        """Check if a conversation exists"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT COUNT(*) FROM conversations WHERE id = ?
            """, (conversation_id,))
            return cursor.fetchone()[0] > 0
    
    def get_conversation_history(self, conversation_id: str) -> List[Dict[str, Any]]:
        """Get all messages in a conversation"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, role, content, confidence_score, 
                       token_logprobs, created_at
                FROM messages
                WHERE conversation_id = ?
                ORDER BY created_at ASC
            """, (conversation_id,))
            
            messages = []
            for row in cursor.fetchall():
                msg = dict(row)
                if msg['token_logprobs']:
                    msg['token_logprobs'] = json.loads(msg['token_logprobs'])
                messages.append(msg)
            
            return messages
    
    def get_pending_escalations(self) -> List[Dict[str, Any]]:
        """Get all pending escalations"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, conversation_id, user_text, assistant_text,
                       confidence_score, policy_tag, created_at
                FROM escalations
                WHERE status = 'pending'
                ORDER BY created_at ASC
            """)
            
            return [dict(row) for row in cursor.fetchall()]
    
    def resolve_escalation(
        self, 
        escalation_id: str, 
        resolution_notes: Optional[str] = None
    ):
        """Mark an escalation as resolved"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE escalations
                SET status = 'resolved',
                    resolved_at = CURRENT_TIMESTAMP,
                    resolution_notes = ?
                WHERE id = ?
            """, (resolution_notes, escalation_id))
        
        logger.info(f"Resolved escalation {escalation_id}")
    
    def get_conversation_stats(self) -> Dict[str, Any]:
        """Get database statistics"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Total conversations
            cursor.execute("SELECT COUNT(*) FROM conversations")
            total_conversations = cursor.fetchone()[0]
            
            # Total messages
            cursor.execute("SELECT COUNT(*) FROM messages")
            total_messages = cursor.fetchone()[0]
            
            # Total escalations
            cursor.execute("SELECT COUNT(*) FROM escalations")
            total_escalations = cursor.fetchone()[0]
            
            # Pending escalations
            cursor.execute("SELECT COUNT(*) FROM escalations WHERE status = 'pending'")
            pending_escalations = cursor.fetchone()[0]
            
            # Average confidence
            cursor.execute("SELECT AVG(confidence_score) FROM messages WHERE confidence_score IS NOT NULL")
            avg_confidence = cursor.fetchone()[0] or 0
            
            return {
                "total_conversations": total_conversations,
                "total_messages": total_messages,
                "total_escalations": total_escalations,
                "pending_escalations": pending_escalations,
                "average_confidence": avg_confidence
            }


# Singleton instance
_db_instance = None

def get_db(db_path: str = "theraloop.db") -> ConversationDB:
    """Get singleton database instance"""
    global _db_instance
    if _db_instance is None:
        _db_instance = ConversationDB(db_path)
    return _db_instance