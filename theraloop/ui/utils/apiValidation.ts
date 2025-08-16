/**
 * API Response Validation Utilities for TheraLoop
 * Provides type-safe validation for all API responses
 */

export interface AnswerResponse {
  text: string;
  token_logprob_sum: number;
  escalate: boolean;
  conversation_id?: string;
}

export interface EscalationResponse {
  ok: boolean;
  id: string;
}

export interface ValidationError {
  field: string;
  expected: string;
  received: unknown;
  message: string;
}

export class APIValidationError extends Error {
  public readonly validationErrors: ValidationError[];
  
  constructor(message: string, errors: ValidationError[]) {
    super(message);
    this.name = 'APIValidationError';
    this.validationErrors = errors;
  }
}

/**
 * Validates that a value is a string and meets criteria
 */
function validateString(value: unknown, fieldName: string, required = true, maxLength?: number): ValidationError[] {
  const errors: ValidationError[] = [];
  
  if (required && (value === null || value === undefined)) {
    errors.push({
      field: fieldName,
      expected: 'string',
      received: value,
      message: `${fieldName} is required`
    });
    return errors;
  }
  
  if (value !== null && value !== undefined && typeof value !== 'string') {
    errors.push({
      field: fieldName,
      expected: 'string',
      received: value,
      message: `${fieldName} must be a string`
    });
  }
  
  if (typeof value === 'string' && maxLength && value.length > maxLength) {
    errors.push({
      field: fieldName,
      expected: `string with max length ${maxLength}`,
      received: value,
      message: `${fieldName} exceeds maximum length of ${maxLength}`
    });
  }
  
  return errors;
}

/**
 * Validates that a value is a number within range
 */
function validateNumber(value: unknown, fieldName: string, required = true, min?: number, max?: number): ValidationError[] {
  const errors: ValidationError[] = [];
  
  if (required && (value === null || value === undefined)) {
    errors.push({
      field: fieldName,
      expected: 'number',
      received: value,
      message: `${fieldName} is required`
    });
    return errors;
  }
  
  if (value !== null && value !== undefined && typeof value !== 'number') {
    errors.push({
      field: fieldName,
      expected: 'number',
      received: value,
      message: `${fieldName} must be a number`
    });
    return errors;
  }
  
  const numValue = value as number;
  
  if (typeof numValue === 'number') {
    if (isNaN(numValue)) {
      errors.push({
        field: fieldName,
        expected: 'valid number',
        received: value,
        message: `${fieldName} is not a valid number`
      });
    }
    
    if (min !== undefined && numValue < min) {
      errors.push({
        field: fieldName,
        expected: `number >= ${min}`,
        received: value,
        message: `${fieldName} must be at least ${min}`
      });
    }
    
    if (max !== undefined && numValue > max) {
      errors.push({
        field: fieldName,
        expected: `number <= ${max}`,
        received: value,
        message: `${fieldName} must be at most ${max}`
      });
    }
  }
  
  return errors;
}

/**
 * Validates that a value is a boolean
 */
function validateBoolean(value: unknown, fieldName: string, required = true): ValidationError[] {
  const errors: ValidationError[] = [];
  
  if (required && (value === null || value === undefined)) {
    errors.push({
      field: fieldName,
      expected: 'boolean',
      received: value,
      message: `${fieldName} is required`
    });
    return errors;
  }
  
  if (value !== null && value !== undefined && typeof value !== 'boolean') {
    errors.push({
      field: fieldName,
      expected: 'boolean',
      received: value,
      message: `${fieldName} must be a boolean`
    });
  }
  
  return errors;
}

/**
 * Validates AnswerResponse from /v1/answer endpoint
 */
export function validateAnswerResponse(response: unknown): AnswerResponse {
  const errors: ValidationError[] = [];
  
  if (!response || typeof response !== 'object') {
    throw new APIValidationError('Response must be an object', [{
      field: 'response',
      expected: 'object',
      received: response,
      message: 'API response is not a valid object'
    }]);
  }
  
  const obj = response as Record<string, unknown>;
  
  // Validate required fields
  errors.push(...validateString(obj.text, 'text', true, 10000));
  errors.push(...validateNumber(obj.token_logprob_sum, 'token_logprob_sum', true, -1000, 0));
  errors.push(...validateBoolean(obj.escalate, 'escalate', true));
  
  // Validate optional conversation_id
  if (obj.conversation_id !== undefined) {
    errors.push(...validateString(obj.conversation_id, 'conversation_id', false, 100));
  }
  
  if (errors.length > 0) {
    throw new APIValidationError('Answer response validation failed', errors);
  }
  
  return {
    text: obj.text as string,
    token_logprob_sum: obj.token_logprob_sum as number,
    escalate: obj.escalate as boolean,
    conversation_id: obj.conversation_id as string | undefined
  };
}

/**
 * Validates EscalationResponse from /v1/escalate endpoint
 */
export function validateEscalationResponse(response: unknown): EscalationResponse {
  const errors: ValidationError[] = [];
  
  if (!response || typeof response !== 'object') {
    throw new APIValidationError('Response must be an object', [{
      field: 'response',
      expected: 'object',
      received: response,
      message: 'Escalation response is not a valid object'
    }]);
  }
  
  const obj = response as Record<string, unknown>;
  
  // Validate required fields
  errors.push(...validateBoolean(obj.ok, 'ok', true));
  errors.push(...validateString(obj.id, 'id', true, 100));
  
  if (errors.length > 0) {
    throw new APIValidationError('Escalation response validation failed', errors);
  }
  
  return {
    ok: obj.ok as boolean,
    id: obj.id as string
  };
}

/**
 * Sanitizes user input to prevent XSS and other injection attacks
 */
export function sanitizeUserInput(input: string): string {
  if (typeof input !== 'string') {
    throw new Error('Input must be a string');
  }
  
  // Remove potential script tags and event handlers
  const sanitized = input
    .replace(/<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>/gi, '')
    .replace(/javascript:/gi, '')
    .replace(/on\w+\s*=/gi, '')
    .replace(/style\s*=\s*[^>]*/gi, '')
    .trim();
  
  // Limit length
  if (sanitized.length > 2000) {
    throw new Error('Input exceeds maximum length of 2000 characters');
  }
  
  return sanitized;
}

/**
 * Validates and sanitizes chat message input
 */
export function validateChatInput(input: unknown): string {
  if (typeof input !== 'string') {
    throw new Error('Message must be a string');
  }
  
  const sanitized = sanitizeUserInput(input);
  
  if (!sanitized.trim()) {
    throw new Error('Message cannot be empty');
  }
  
  return sanitized;
}

/**
 * Creates a user-friendly error message from validation errors
 */
export function formatValidationErrors(errors: ValidationError[]): string {
  if (errors.length === 0) return 'Unknown validation error';
  
  if (errors.length === 1) {
    return errors[0].message;
  }
  
  return `Multiple validation errors:\n${errors.map(e => `• ${e.message}`).join('\n')}`;
}

/**
 * Retry wrapper for API calls with exponential backoff
 */
export async function retryApiCall<T>(
  apiCall: () => Promise<T>,
  maxRetries = 3,
  baseDelay = 1000
): Promise<T> {
  let lastError: Error;
  
  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    try {
      return await apiCall();
    } catch (error) {
      lastError = error instanceof Error ? error : new Error(String(error));
      
      // Don't retry validation errors
      if (error instanceof APIValidationError) {
        throw error;
      }
      
      // Don't retry on last attempt
      if (attempt === maxRetries) {
        break;
      }
      
      // Exponential backoff with jitter
      const delay = baseDelay * Math.pow(2, attempt) + Math.random() * 1000;
      await new Promise(resolve => setTimeout(resolve, delay));
    }
  }
  
  throw lastError!;
}