/**
 * Session Management for TheraLoop
 * Handles conversation persistence, session tracking, and cleanup
 */

import React from 'react';

export interface ConversationMessage {
  id: string;
  role: 'user' | 'assistant';
  text: string;
  timestamp: number;
  token_logprob_sum?: number;
  escalate?: boolean;
}

export interface SessionData {
  sessionId: string;
  userId?: string;
  createdAt: number;
  lastActivity: number;
  messages: ConversationMessage[];
  metadata: {
    userAgent?: string;
    ipAddress?: string;
    escalationCount: number;
    riskLevel: 'low' | 'medium' | 'high';
  };
}

export interface SessionConfig {
  maxMessages: number;
  sessionTimeoutMs: number;
  storageKey: string;
  enablePersistence: boolean;
}

export class SessionManager {
  private config: SessionConfig;
  private currentSession: SessionData | null = null;
  
  constructor(config: Partial<SessionConfig> = {}) {
    this.config = {
      maxMessages: 100,
      sessionTimeoutMs: 30 * 60 * 1000, // 30 minutes
      storageKey: 'theraloop_session',
      enablePersistence: true,
      ...config
    };
    
    this.loadSession();
  }

  /**
   * Get or create the current session
   */
  getSession(): SessionData {
    if (!this.currentSession || this.isSessionExpired()) {
      this.createNewSession();
    }
    
    this.updateLastActivity();
    return this.currentSession!;
  }

  /**
   * Create a new session
   */
  private createNewSession(): void {
    this.currentSession = {
      sessionId: this.generateSessionId(),
      createdAt: Date.now(),
      lastActivity: Date.now(),
      messages: [],
      metadata: {
        userAgent: typeof window !== 'undefined' ? window.navigator.userAgent : undefined,
        escalationCount: 0,
        riskLevel: 'low'
      }
    };
    
    if (this.config.enablePersistence) {
      this.saveSession();
    }
  }

  /**
   * Add a message to the current session
   */
  addMessage(message: Omit<ConversationMessage, 'id' | 'timestamp'>): ConversationMessage {
    const session = this.getSession();
    
    const fullMessage: ConversationMessage = {
      ...message,
      id: this.generateMessageId(),
      timestamp: Date.now()
    };
    
    session.messages.push(fullMessage);
    
    // Update risk level based on escalations
    if (message.escalate) {
      session.metadata.escalationCount++;
      this.updateRiskLevel();
    }
    
    // Trim old messages if exceeding limit
    if (session.messages.length > this.config.maxMessages) {
      session.messages = session.messages.slice(-this.config.maxMessages);
    }
    
    this.updateLastActivity();
    
    if (this.config.enablePersistence) {
      this.saveSession();
    }
    
    return fullMessage;
  }

  /**
   * Get conversation history
   */
  getMessages(): ConversationMessage[] {
    return this.getSession().messages;
  }

  /**
   * Get session metadata
   */
  getMetadata(): SessionData['metadata'] {
    return this.getSession().metadata;
  }

  /**
   * Clear the current session
   */
  clearSession(): void {
    this.currentSession = null;
    
    if (typeof window !== 'undefined') {
      localStorage.removeItem(this.config.storageKey);
      // Note: We only use localStorage, not sessionStorage
    }
  }

  /**
   * Export session data for backup/audit
   */
  exportSession(): string {
    const session = this.getSession();
    return JSON.stringify({
      ...session,
      exportedAt: new Date().toISOString(),
      version: '1.0'
    }, null, 2);
  }

  /**
   * Update risk level based on conversation content
   */
  private updateRiskLevel(): void {
    if (!this.currentSession) return;
    
    const { escalationCount } = this.currentSession.metadata;
    const recentMessages = this.currentSession.messages.slice(-10);
    
    // Check for crisis keywords in recent messages
    const crisisKeywords = ['suicide', 'kill myself', 'end my life', 'hurt myself', 'self-harm'];
    const hasCrisisContent = recentMessages.some(msg => 
      msg.role === 'user' && 
      crisisKeywords.some(keyword => msg.text.toLowerCase().includes(keyword))
    );
    
    if (hasCrisisContent || escalationCount >= 3) {
      this.currentSession.metadata.riskLevel = 'high';
    } else if (escalationCount >= 1 || this.hasDepressiveContent(recentMessages)) {
      this.currentSession.metadata.riskLevel = 'medium';
    } else {
      this.currentSession.metadata.riskLevel = 'low';
    }
  }

  /**
   * Check for depressive content patterns
   */
  private hasDepressiveContent(messages: ConversationMessage[]): boolean {
    const depressiveKeywords = ['depressed', 'hopeless', 'worthless', 'alone', 'empty', 'sad'];
    const userMessages = messages.filter(msg => msg.role === 'user');
    
    return userMessages.some(msg => 
      depressiveKeywords.some(keyword => msg.text.toLowerCase().includes(keyword))
    );
  }

  /**
   * Check if session is expired
   */
  private isSessionExpired(): boolean {
    if (!this.currentSession) return true;
    
    const now = Date.now();
    const elapsed = now - this.currentSession.lastActivity;
    
    return elapsed > this.config.sessionTimeoutMs;
  }

  /**
   * Update last activity timestamp
   */
  private updateLastActivity(): void {
    if (this.currentSession) {
      this.currentSession.lastActivity = Date.now();
    }
  }

  /**
   * Load session from storage
   */
  private loadSession(): void {
    if (!this.config.enablePersistence || typeof window === 'undefined') {
      return;
    }
    
    try {
      const stored = localStorage.getItem(this.config.storageKey);
      if (stored) {
        const session = JSON.parse(stored) as SessionData;
        
        // Validate session structure first
        if (this.isValidSession(session)) {
          // Check if the loaded session is expired by examining its timestamp
          const now = Date.now();
          const elapsed = now - session.lastActivity;
          
          if (elapsed <= this.config.sessionTimeoutMs) {
            // Session is still valid, use it
            this.currentSession = session;
          } else {
            // Session is expired, don't load it and clean up storage
            localStorage.removeItem(this.config.storageKey);
          }
        }
      }
    } catch (err: unknown) {
      console.warn('Failed to load session:', err);
      // Clear corrupted session data
      localStorage.removeItem(this.config.storageKey);
    }
  }

  /**
   * Save session to storage
   */
  private saveSession(): void {
    if (!this.config.enablePersistence || typeof window === 'undefined' || !this.currentSession) {
      return;
    }
    
    try {
      localStorage.setItem(this.config.storageKey, JSON.stringify(this.currentSession));
    } catch (err: unknown) {
      console.warn('Failed to save session:', err);
    }
  }

  /**
   * Validate session data structure
   */
  private isValidSession(session: any): session is SessionData {
    return (
      session &&
      typeof session.sessionId === 'string' &&
      typeof session.createdAt === 'number' &&
      typeof session.lastActivity === 'number' &&
      Array.isArray(session.messages) &&
      session.metadata &&
      typeof session.metadata.escalationCount === 'number'
    );
  }

  /**
   * Generate unique session ID
   */
  private generateSessionId(): string {
    const timestamp = Date.now().toString(36);
    const randomPart = Math.random().toString(36).substring(2);
    return `session_${timestamp}_${randomPart}`;
  }

  /**
   * Generate unique message ID
   */
  private generateMessageId(): string {
    const timestamp = Date.now().toString(36);
    const randomPart = Math.random().toString(36).substring(2);
    return `msg_${timestamp}_${randomPart}`;
  }

  /**
   * Get session analytics
   */
  getAnalytics(): {
    sessionDuration: number;
    messageCount: number;
    escalationCount: number;
    riskLevel: string;
    avgResponseTime?: number;
  } {
    const session = this.getSession();
    const now = Date.now();
    
    // Calculate average response time (time between user message and assistant response)
    let totalResponseTime = 0;
    let responseCount = 0;
    
    for (let i = 0; i < session.messages.length - 1; i++) {
      const current = session.messages[i];
      const next = session.messages[i + 1];
      
      if (current.role === 'user' && next.role === 'assistant') {
        // Validate timestamps are numbers and positive
        const timeDiff = next.timestamp - current.timestamp;
        if (typeof timeDiff === 'number' && timeDiff > 0 && timeDiff < 300000) { // Max 5 minutes
          totalResponseTime += timeDiff;
          responseCount++;
        }
      }
    }
    
    return {
      sessionDuration: now - session.createdAt,
      messageCount: session.messages.length,
      escalationCount: session.metadata.escalationCount,
      riskLevel: session.metadata.riskLevel,
      avgResponseTime: responseCount > 0 ? totalResponseTime / responseCount : undefined
    };
  }
}

// Create global session manager instance
export const sessionManager = new SessionManager();

// React hook for session management
export function useSession() {
  const [session, setSession] = React.useState(() => sessionManager.getSession());
  
  const addMessage = React.useCallback((message: Omit<ConversationMessage, 'id' | 'timestamp'>) => {
    const newMessage = sessionManager.addMessage(message);
    setSession(sessionManager.getSession());
    return newMessage;
  }, []);
  
  const clearSession = React.useCallback(() => {
    sessionManager.clearSession();
    setSession(sessionManager.getSession());
  }, []);
  
  const getAnalytics = React.useCallback(() => {
    return sessionManager.getAnalytics();
  }, []);
  
  return {
    session,
    messages: session.messages,
    metadata: session.metadata,
    addMessage,
    clearSession,
    getAnalytics
  };
}