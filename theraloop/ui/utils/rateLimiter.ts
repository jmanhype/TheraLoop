/**
 * Client-side rate limiting for TheraLoop
 * Prevents API abuse and provides better UX
 */

import React from 'react';

interface RateLimitConfig {
  windowMs: number;  // Time window in milliseconds
  maxRequests: number;  // Maximum requests per window
  keyGenerator?: () => string;  // Function to generate unique keys
}

interface RateLimitEntry {
  requests: number[];  // Timestamps of requests
}

export class RateLimiter {
  private storage = new Map<string, RateLimitEntry>();
  private config: Required<RateLimitConfig>;

  constructor(config: RateLimitConfig) {
    this.config = {
      windowMs: config.windowMs,
      maxRequests: config.maxRequests,
      keyGenerator: config.keyGenerator || (() => 'default')
    };
  }

  /**
   * Check if a request should be allowed
   */
  isAllowed(): { allowed: boolean; retryAfter?: number; remaining: number } {
    const now = Date.now();
    const key = this.config.keyGenerator();
    
    // Get or create rate limit entry
    let entry = this.storage.get(key);
    if (!entry) {
      entry = { requests: [] };
      this.storage.set(key, entry);
    }

    // Clean up old requests outside the window
    const windowStart = now - this.config.windowMs;
    entry.requests = entry.requests.filter(timestamp => timestamp > windowStart);

    // Check if limit exceeded
    if (entry.requests.length >= this.config.maxRequests) {
      const oldestRequest = entry.requests.length > 0 
        ? Math.min(...entry.requests)
        : now;
      const retryAfter = Math.ceil((oldestRequest + this.config.windowMs - now) / 1000);
      
      return {
        allowed: false,
        retryAfter: Math.max(retryAfter, 1),
        remaining: 0
      };
    }

    // Allow the request
    entry.requests.push(now);
    
    return {
      allowed: true,
      remaining: this.config.maxRequests - entry.requests.length
    };
  }

  /**
   * Reset rate limit for a specific key
   */
  reset(key?: string): void {
    if (key) {
      this.storage.delete(key);
    } else {
      this.storage.clear();
    }
  }

  /**
   * Get current status without making a request
   */
  getStatus(): { remaining: number; resetTime: number } {
    const key = this.config.keyGenerator();
    const entry = this.storage.get(key);
    
    if (!entry) {
      return {
        remaining: this.config.maxRequests,
        resetTime: Date.now() + this.config.windowMs
      };
    }

    const now = Date.now();
    const windowStart = now - this.config.windowMs;
    const validRequests = entry.requests.filter(timestamp => timestamp > windowStart);
    
    return {
      remaining: this.config.maxRequests - validRequests.length,
      resetTime: validRequests.length > 0 
        ? Math.min(...validRequests) + this.config.windowMs
        : now + this.config.windowMs
    };
  }
}

// Rate limiters for different endpoints
export const chatRateLimiter = new RateLimiter({
  windowMs: 60 * 1000, // 1 minute
  maxRequests: 30,      // 30 messages per minute
  keyGenerator: () => `chat_${getSessionId()}`
});

export const escalationRateLimiter = new RateLimiter({
  windowMs: 60 * 1000, // 1 minute  
  maxRequests: 5,       // 5 escalations per minute
  keyGenerator: () => `escalation_${getSessionId()}`
});

/**
 * Get or create a session ID for rate limiting
 */
function getSessionId(): string {
  if (typeof window === 'undefined') return 'server';
  
  let sessionId = sessionStorage.getItem('theraloop_session_id');
  if (!sessionId) {
    sessionId = generateSessionId();
    sessionStorage.setItem('theraloop_session_id', sessionId);
  }
  
  return sessionId;
}

/**
 * Generate a unique session ID
 */
function generateSessionId(): string {
  const timestamp = Date.now().toString(36);
  const randomPart = Math.random().toString(36).substring(2);
  return `${timestamp}_${randomPart}`;
}

/**
 * Rate limit error class
 */
export class RateLimitError extends Error {
  public readonly retryAfter: number;
  public readonly remaining: number;

  constructor(message: string, retryAfter: number, remaining: number = 0) {
    super(message);
    this.name = 'RateLimitError';
    this.retryAfter = retryAfter;
    this.remaining = remaining;
  }
}

/**
 * Wrapper for API calls with rate limiting
 */
export async function withRateLimit<T>(
  rateLimiter: RateLimiter,
  apiCall: () => Promise<T>,
  errorMessage = 'Rate limit exceeded'
): Promise<T> {
  const result = rateLimiter.isAllowed();
  
  if (!result.allowed) {
    throw new RateLimitError(
      `${errorMessage}. Please wait ${result.retryAfter} seconds before trying again.`,
      result.retryAfter!,
      result.remaining
    );
  }
  
  return apiCall();
}

/**
 * React hook for rate limit status
 */
export function useRateLimit(rateLimiter: RateLimiter) {
  const rateLimiterRef = React.useRef(rateLimiter);
  const [status, setStatus] = React.useState(() => rateLimiterRef.current.getStatus());
  
  React.useEffect(() => {
    // Update ref if rateLimiter changes
    rateLimiterRef.current = rateLimiter;
  }, [rateLimiter]);
  
  React.useEffect(() => {
    const interval = setInterval(() => {
      setStatus(rateLimiterRef.current.getStatus());
    }, 1000);
    
    return () => clearInterval(interval);
  }, []); // Empty dependency array to prevent recreating interval
  
  return status;
}