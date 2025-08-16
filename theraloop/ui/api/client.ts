
import axios from "axios";
import { 
  validateAnswerResponse, 
  validateChatInput, 
  retryApiCall,
  type AnswerResponse 
} from "../utils/apiValidation";
import { 
  chatRateLimiter, 
  escalationRateLimiter, 
  withRateLimit 
} from "../utils/rateLimiter";

export const api = axios.create({
  baseURL: process.env.NEXT_PUBLIC_THERALOOP_API || "http://localhost:8000",
  headers: { "Content-Type": "application/json" },
  withCredentials: false, // we use Bearer (demo). Consider httpOnly cookies in prod.
});

// Simple token store (demo): localStorage
export const setToken = (t: string | null) => {
  if (typeof window === "undefined") return;
  
  if (!t) {
    localStorage.removeItem("jwt");
  } else {
    localStorage.setItem("jwt", t);
  }
};

export const getToken = (): string | null => 
  typeof window !== "undefined" ? localStorage.getItem("jwt") : null;

api.interceptors.request.use((cfg) => {
  const tok = getToken();
  if (tok) cfg.headers = { ...cfg.headers, Authorization: `Bearer ${tok}` };
  return cfg;
});

// Session management for conversation continuity (per-tab isolation)
const CONVERSATION_KEY = "theraloop_conversation_id";

function getCurrentConversationId(): string | null {
  if (typeof window === "undefined") return null;
  return sessionStorage.getItem(CONVERSATION_KEY);
}

function setCurrentConversationId(id: string | null): void {
  if (typeof window === "undefined") return;
  if (id) {
    sessionStorage.setItem(CONVERSATION_KEY, id);
  } else {
    sessionStorage.removeItem(CONVERSATION_KEY);
  }
}

export function clearConversation(): void {
  setCurrentConversationId(null);
}

export async function ask(question: string): Promise<AnswerResponse & { conversation_id?: string }> {
  // Validate and sanitize input
  const sanitizedQuestion = validateChatInput(question);
  
  // Apply rate limiting and API call with retry logic
  return withRateLimit(chatRateLimiter, () => 
    retryApiCall(async () => {
      const payload: { question: string; conversation_id?: string } = { 
        question: sanitizedQuestion 
      };
      
      // Include conversation_id if we have one for session continuity
      const currentId = getCurrentConversationId();
      if (currentId) {
        payload.conversation_id = currentId;
      }
      
      const res = await api.post("/answer", payload);
      
      // Store conversation_id for future messages
      if (res.data.conversation_id) {
        setCurrentConversationId(res.data.conversation_id);
      }
      
      // Map backend response to expected format
      const mappedResponse = {
        text: res.data.answer || res.data.text,
        token_logprob_sum: res.data.confidence_logprob_sum ?? res.data.token_logprob_sum,
        escalate: res.data.escalate,
        conversation_id: res.data.conversation_id
      };
      
      // Validate response structure
      return validateAnswerResponse(mappedResponse);
    })
  );
}

// Add proper types for escalation
export interface EscalationPayload {
  conversation_id: string;
  user_text: string;
  assistant_text?: string;
  token_logprob_sum?: number;
  policy_tag?: string;
}

export async function escalate(payload: EscalationPayload): Promise<{ok: boolean; id: string}> {
  return withRateLimit(escalationRateLimiter, () =>
    retryApiCall(async () => {
      const res = await api.post("/escalate", payload);
      
      // Validate escalation response
      if (!res.data || typeof res.data !== 'object') {
        throw new Error('Invalid escalation response');
      }
      
      if (typeof res.data.ok !== 'boolean' || typeof res.data.id !== 'string') {
        throw new Error('Escalation response missing required fields');
      }
      
      return res.data;
    }), 
    "Too many escalations"
  );
}
