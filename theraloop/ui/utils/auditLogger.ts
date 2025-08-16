/**
 * Audit Logging System for TheraLoop
 * Tracks all user interactions, escalations, and system events for compliance
 */

import React from 'react';

export interface AuditEvent {
  id: string;
  timestamp: number;
  sessionId: string;
  userId?: string;
  eventType: AuditEventType;
  details: Record<string, any>;
  severity: 'low' | 'medium' | 'high' | 'critical';
  metadata: {
    userAgent?: string;
    ipAddress?: string;
    url?: string;
    version: string;
  };
}

export type AuditEventType = 
  | 'session_start'
  | 'session_end'
  | 'message_sent'
  | 'message_received'
  | 'escalation_triggered'
  | 'escalation_completed'
  | 'crisis_detected'
  | 'error_occurred'
  | 'rate_limit_hit'
  | 'validation_failed'
  | 'auth_attempt'
  | 'data_export'
  | 'session_timeout';

export interface AuditConfig {
  enableConsoleLogging: boolean;
  enableLocalStorage: boolean;
  enableRemoteLogging: boolean;
  remoteEndpoint?: string;
  maxLocalEvents: number;
  retentionDays: number;
}

export class AuditLogger {
  private config: AuditConfig;
  private eventQueue: AuditEvent[] = [];
  private sessionId: string;
  private isLoggingError = false; // Recursion guard

  constructor(config: Partial<AuditConfig> = {}) {
    this.config = {
      enableConsoleLogging: true,
      enableLocalStorage: true,
      enableRemoteLogging: false,
      maxLocalEvents: 1000,
      retentionDays: 30,
      ...config
    };
    
    this.sessionId = this.generateSessionId();
    this.loadStoredEvents();
    this.setupCleanup();
  }

  /**
   * Log an audit event
   */
  logEvent(
    eventType: AuditEventType,
    details: Record<string, any> = {},
    severity: AuditEvent['severity'] = 'low'
  ): void {
    const event: AuditEvent = {
      id: this.generateEventId(),
      timestamp: Date.now(),
      sessionId: this.sessionId,
      eventType,
      details: this.sanitizeDetails(details),
      severity,
      metadata: {
        userAgent: typeof window !== 'undefined' ? window.navigator.userAgent : undefined,
        url: typeof window !== 'undefined' ? window.location.href : undefined,
        version: '1.0.0'
      }
    };

    // Add to queue
    this.eventQueue.push(event);

    // Console logging
    if (this.config.enableConsoleLogging) {
      this.logToConsole(event);
    }

    // Local storage
    if (this.config.enableLocalStorage) {
      this.saveToLocalStorage();
    }

    // Remote logging
    if (this.config.enableRemoteLogging && this.config.remoteEndpoint) {
      this.sendToRemote(event);
    }

    // Trim queue if too large
    if (this.eventQueue.length > this.config.maxLocalEvents) {
      this.eventQueue = this.eventQueue.slice(-this.config.maxLocalEvents);
    }
  }

  /**
   * Log session start
   */
  logSessionStart(userId?: string): void {
    this.logEvent('session_start', {
      userId,
      timestamp: new Date().toISOString()
    }, 'low');
  }

  /**
   * Log session end
   */
  logSessionEnd(analytics?: Record<string, any>): void {
    this.logEvent('session_end', {
      analytics,
      duration: Date.now() - this.getSessionStartTime(),
      timestamp: new Date().toISOString()
    }, 'low');
  }

  /**
   * Log message interaction
   */
  logMessage(role: 'user' | 'assistant', content: string, metadata?: Record<string, any>): void {
    const eventType = role === 'user' ? 'message_sent' : 'message_received';
    
    this.logEvent(eventType, {
      role,
      contentLength: content.length,
      contentPreview: content.substring(0, 100),
      ...metadata
    }, 'low');
  }

  /**
   * Log escalation event
   */
  logEscalation(
    type: 'triggered' | 'completed',
    details: {
      reason?: string;
      messageId?: string;
      confidence?: number;
      escalationId?: string;
    }
  ): void {
    const eventType = type === 'triggered' ? 'escalation_triggered' : 'escalation_completed';
    
    this.logEvent(eventType, details, 'high');
  }

  /**
   * Log crisis detection
   */
  logCrisisDetection(details: {
    messageContent: string;
    detectedKeywords: string[];
    confidence: number;
    responseGenerated: string;
  }): void {
    this.logEvent('crisis_detected', {
      ...details,
      messageContent: details.messageContent.substring(0, 200) // Truncate for privacy
    }, 'critical');
  }

  /**
   * Log error events with recursion protection
   */
  logError(error: Error, context?: Record<string, any>): void {
    // Prevent recursion if error occurs during error logging
    if (this.isLoggingError) {
      console.error('Error during error logging (recursion prevented):', error);
      return;
    }
    
    this.isLoggingError = true;
    try {
      this.logEvent('error_occurred', {
        errorName: error.name,
        errorMessage: error.message,
        errorStack: error.stack,
        context
      }, 'medium');
    } finally {
      this.isLoggingError = false;
    }
  }

  /**
   * Log rate limiting events
   */
  logRateLimit(endpoint: string, retryAfter: number): void {
    this.logEvent('rate_limit_hit', {
      endpoint,
      retryAfter,
      timestamp: new Date().toISOString()
    }, 'medium');
  }

  /**
   * Log validation failures
   */
  logValidationFailure(field: string, expected: string, received: any): void {
    this.logEvent('validation_failed', {
      field,
      expected,
      received: typeof received,
      timestamp: new Date().toISOString()
    }, 'medium');
  }

  /**
   * Get audit trail for a session
   */
  getSessionAuditTrail(sessionId?: string): AuditEvent[] {
    const targetSessionId = sessionId || this.sessionId;
    return this.eventQueue.filter(event => event.sessionId === targetSessionId);
  }

  /**
   * Export audit logs
   */
  exportAuditLogs(format: 'json' | 'csv' = 'json'): string {
    this.logEvent('data_export', { format, exportedAt: new Date().toISOString() }, 'medium');
    
    if (format === 'csv') {
      return this.exportAsCSV();
    }
    
    return JSON.stringify({
      exportedAt: new Date().toISOString(),
      events: this.eventQueue,
      metadata: {
        totalEvents: this.eventQueue.length,
        sessionId: this.sessionId,
        version: '1.0.0'
      }
    }, null, 2);
  }

  /**
   * Clear old audit logs
   */
  clearOldLogs(): number {
    const cutoffTime = Date.now() - (this.config.retentionDays * 24 * 60 * 60 * 1000);
    const initialCount = this.eventQueue.length;
    
    this.eventQueue = this.eventQueue.filter(event => event.timestamp > cutoffTime);
    
    const removedCount = initialCount - this.eventQueue.length;
    
    if (removedCount > 0) {
      this.logEvent('data_cleanup', { 
        removedEvents: removedCount,
        retentionDays: this.config.retentionDays 
      }, 'low');
    }
    
    return removedCount;
  }

  /**
   * Get audit statistics
   */
  getAuditStats(): {
    totalEvents: number;
    eventsByType: Record<string, number>;
    eventsBySeverity: Record<string, number>;
    sessionDuration: number;
    lastEventTime: number;
  } {
    const eventsByType: Record<string, number> = {};
    const eventsBySeverity: Record<string, number> = {};
    
    this.eventQueue.forEach(event => {
      eventsByType[event.eventType] = (eventsByType[event.eventType] || 0) + 1;
      eventsBySeverity[event.severity] = (eventsBySeverity[event.severity] || 0) + 1;
    });
    
    return {
      totalEvents: this.eventQueue.length,
      eventsByType,
      eventsBySeverity,
      sessionDuration: Date.now() - this.getSessionStartTime(),
      lastEventTime: this.eventQueue.length > 0 ? this.eventQueue[this.eventQueue.length - 1].timestamp : 0
    };
  }

  /**
   * Sanitize sensitive details
   */
  private sanitizeDetails(details: Record<string, any>): Record<string, any> {
    const sanitized = { ...details };
    
    // Remove or mask sensitive fields
    const sensitiveFields = ['password', 'token', 'jwt', 'secret', 'key'];
    
    sensitiveFields.forEach(field => {
      if (sanitized[field]) {
        sanitized[field] = '[REDACTED]';
      }
    });
    
    // Truncate long strings
    Object.keys(sanitized).forEach(key => {
      if (typeof sanitized[key] === 'string' && sanitized[key].length > 1000) {
        sanitized[key] = sanitized[key].substring(0, 1000) + '... [TRUNCATED]';
      }
    });
    
    return sanitized;
  }

  /**
   * Log to console with appropriate level
   */
  private logToConsole(event: AuditEvent): void {
    const logMessage = `[AUDIT] ${event.eventType} (${event.severity})`;
    
    switch (event.severity) {
      case 'critical':
        console.error(logMessage, event);
        break;
      case 'high':
        console.warn(logMessage, event);
        break;
      case 'medium':
        console.info(logMessage, event);
        break;
      default:
        console.log(logMessage, event);
    }
  }

  /**
   * Save events to local storage with quota handling
   */
  private saveToLocalStorage(): void {
    if (typeof window === 'undefined' || this.isLoggingError) return;
    
    try {
      const data = JSON.stringify(this.eventQueue);
      localStorage.setItem('theraloop_audit_logs', data);
    } catch (error) {
      // Handle quota exceeded or other storage errors
      if (error instanceof Error && error.name === 'QuotaExceededError') {
        // Try to clear old logs and retry once
        try {
          const halfQueue = this.eventQueue.slice(-Math.floor(this.eventQueue.length / 2));
          localStorage.setItem('theraloop_audit_logs', JSON.stringify(halfQueue));
          this.eventQueue = halfQueue;
        } catch {
          console.warn('Failed to save audit logs even after cleanup');
        }
      } else {
        console.warn('Failed to save audit logs to localStorage:', error);
      }
    }
  }

  /**
   * Load events from local storage
   */
  private loadStoredEvents(): void {
    if (typeof window === 'undefined' || !this.config.enableLocalStorage) return;
    
    try {
      const stored = localStorage.getItem('theraloop_audit_logs');
      if (stored) {
        const events = JSON.parse(stored) as AuditEvent[];
        if (Array.isArray(events)) {
          this.eventQueue = events;
          this.clearOldLogs(); // Clean up old events on load
        }
      }
    } catch (error) {
      console.warn('Failed to load stored audit logs:', error);
    }
  }

  /**
   * Send event to remote logging service
   */
  private async sendToRemote(event: AuditEvent): Promise<void> {
    if (!this.config.remoteEndpoint) return;
    
    try {
      await fetch(this.config.remoteEndpoint, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(event)
      });
    } catch (error) {
      console.warn('Failed to send audit event to remote service:', error);
    }
  }

  /**
   * Export as CSV format
   */
  private exportAsCSV(): string {
    const headers = ['timestamp', 'sessionId', 'eventType', 'severity', 'details'];
    const rows = this.eventQueue.map(event => [
      new Date(event.timestamp).toISOString(),
      event.sessionId,
      event.eventType,
      event.severity,
      JSON.stringify(event.details)
    ]);
    
    return [headers, ...rows]
      .map(row => row.map(cell => `"${cell}"`).join(','))
      .join('\n');
  }

  /**
   * Setup automatic cleanup
   */
  private setupCleanup(): void {
    if (typeof window === 'undefined') return;
    
    // Clean up old logs every hour
    setInterval(() => {
      this.clearOldLogs();
    }, 60 * 60 * 1000);
  }

  /**
   * Generate unique event ID
   */
  private generateEventId(): string {
    return `audit_${Date.now()}_${Math.random().toString(36).substring(2)}`;
  }

  /**
   * Generate session ID
   */
  private generateSessionId(): string {
    return `session_${Date.now()}_${Math.random().toString(36).substring(2)}`;
  }

  /**
   * Get session start time
   */
  private getSessionStartTime(): number {
    const sessionStartEvent = this.eventQueue.find(event => event.eventType === 'session_start');
    return sessionStartEvent?.timestamp || Date.now();
  }
}

// Create global audit logger instance
export const auditLogger = new AuditLogger();

// React hook for audit logging
export function useAuditLogger() {
  const logEvent = React.useCallback((
    eventType: AuditEventType,
    details?: Record<string, any>,
    severity?: AuditEvent['severity']
  ) => {
    auditLogger.logEvent(eventType, details, severity);
  }, []);

  const getStats = React.useCallback(() => {
    return auditLogger.getAuditStats();
  }, []);

  return {
    logEvent,
    logMessage: auditLogger.logMessage.bind(auditLogger),
    logEscalation: auditLogger.logEscalation.bind(auditLogger),
    logError: auditLogger.logError.bind(auditLogger),
    getStats,
    exportLogs: auditLogger.exportAuditLogs.bind(auditLogger)
  };
}