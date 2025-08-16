import React from "react";
import { ask, escalate, clearConversation } from "../api/client";
import { ConfidenceBadge } from "./ConfidenceBadge";
import { EscalationButton } from "./EscalationButton";

type Msg = { role:"user"|"assistant", text:string, lp?:number, escalate?:boolean, conversation_id?:string };

export default function ChatWindow(){
  const [q, setQ] = React.useState("");
  const [msgs, setMsgs] = React.useState<Msg[]>([]);
  const [busy, setBusy] = React.useState(false);
  const [escalatingIndex, setEscalatingIndex] = React.useState<number | null>(null);
  const [error, setError] = React.useState<string | null>(null);

  const handleEscalation = async (message: Msg, index: number) => {
    if (escalatingIndex !== null) return; // Prevent double-clicks
    
    try {
      setError(null);
      setEscalatingIndex(index);
      
      // Validate we have a valid conversation_id before escalating
      if (!message.conversation_id) {
        throw new Error("Cannot escalate: Missing conversation ID. Please refresh and try again.");
      }
      
      // Use the typed escalate function with validation and rate limiting
      await escalate({
        conversation_id: message.conversation_id,
        user_text: "User escalated from chat interface", 
        assistant_text: message.text,
        token_logprob_sum: message.lp || 0
      });
      
      const successMsg: Msg = {
        role: "assistant",
        text: "✅ Your request has been escalated to a human reviewer. You will be contacted soon."
      };
      setMsgs(m => [...m, successMsg]);
    } catch (err: unknown) {
      const error = err as Error;
      console.error("Escalation failed:", error);
      
      // Check if it's a rate limit error
      const isRateLimit = error.message?.includes('Rate limit') || error.message?.includes('too many');
      const errorMsg: Msg = {
        role: "assistant", 
        text: isRateLimit 
          ? "⚠️ Too many escalation requests. Please wait a moment before trying again."
          : "⚠️ Escalation failed. Please try again or contact support directly."
      };
      setMsgs(m => [...m, errorMsg]);
    } finally {
      setEscalatingIndex(null);
    }
  };

  const validateInput = (text: string): string | null => {
    if (text.length > 2000) return "Message too long (max 2000 characters)";
    
    // Comprehensive XSS prevention
    const dangerousPatterns = [
      /<script/i,
      /<iframe/i,
      /javascript:/i,
      /on\w+\s*=/i,
      /<embed/i,
      /<object/i,
      /eval\(/i,
      /expression\(/i
    ];
    
    if (dangerousPatterns.some(pattern => pattern.test(text))) {
      return "Invalid input detected";
    }
    
    return null;
  };

  const send = async () => {
    // Prevent double-clicks/Enter presses and sending during escalation
    if (busy || escalatingIndex !== null) return;
    
    const trimmed = q.trim();
    const validationError = validateInput(q); // Validate original input for length check
    
    if (validationError) {
      setError(validationError);
      return;
    }
    
    if (!trimmed) {
      setError("Please enter a message");
      return;
    }

    setError(null);
    setBusy(true); // Set busy IMMEDIATELY to prevent race condition
    const user: Msg = { role:"user", text: trimmed };
    setMsgs(m => [...m, user]); 
    setQ("");

    try {
      const res = await ask(trimmed);
      
      if (!res || typeof res !== 'object') {
        throw new Error('Invalid response from server');
      }

      const assistantMsg: Msg = { 
        role: "assistant", 
        text: res.text || "I apologize, but I couldn't generate a response. Please try again.",
        lp: typeof res.token_logprob_sum === 'number' ? res.token_logprob_sum : 0,
        escalate: !!res.escalate,
        conversation_id: res.conversation_id
      };
      
      setMsgs(m => [...m, assistantMsg]);
    } catch (err: unknown) {
      const error = err as Error;
      console.error("Chat error:", error);
      
      const errorMsg: Msg = {
        role: "assistant",
        text: `❌ ${error instanceof Error ? error.message : 'Failed to connect to server'}. Please try again or refresh the page.`
      };
      setMsgs(m => [...m, errorMsg]);
    } finally {
      setBusy(false);
    }
  };

  const handleKeyDown = async (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      if (!busy && escalatingIndex === null) { // Check both busy and escalation state
        await send();
      }
    }
  };

  const handleNewConversation = () => {
    clearConversation();
    setMsgs([]);
    setQ("");
    setError(null);
    setEscalatingIndex(null);
  };

  return (
    <div style={{maxWidth:720, margin:"40px auto", fontFamily:"ui-sans-serif"}}>
      <div style={{display:"flex", justifyContent:"space-between", alignItems:"center", marginBottom:16}}>
        <h1 style={{margin:0}}>TheraLoop Chat</h1>
        <button 
          onClick={handleNewConversation}
          disabled={busy || escalatingIndex !== null}
          style={{
            padding:"8px 12px",
            borderRadius:6,
            background:"#f3f4f6",
            border:"1px solid #d1d5db",
            color:"#374151",
            cursor: busy || escalatingIndex !== null ? "not-allowed" : "pointer",
            fontSize:14
          }}
        >
          New Conversation
        </button>
      </div>
      
      {error && (
        <div style={{
          background: "#fef2f2", 
          border: "1px solid #fecaca", 
          color: "#dc2626", 
          padding: "8px 12px", 
          borderRadius: 8, 
          marginBottom: 12
        }}>
          {error}
        </div>
      )}

      <div 
        style={{border:"1px solid #e5e7eb", borderRadius:12, padding:16, minHeight:240}}
        role="log"
        aria-live="assertive"
        aria-label="Chat conversation"
      >
        {msgs.length === 0 && (
          <div style={{color: "#6b7280", fontStyle: "italic", textAlign: "center", marginTop: 80}}>
            Start a conversation...
          </div>
        )}
        
        {msgs.map((m,i)=>(
          <div key={i} style={{margin:"8px 0", textAlign: m.role==="user"?"right":"left"}}>
            <div style={{
              display:"inline-block", 
              padding:10, 
              background:m.role==="user"?"#e0f2fe":"#f3f4f6", 
              borderRadius:10,
              maxWidth: "80%"
            }}>
              <div>{m.text}</div>
              {m.role==="assistant" && (
                <div style={{marginTop:6, display:"flex", gap:8, alignItems:"center", flexWrap:"wrap"}}>
                  <ConfidenceBadge lpSum={m.lp ?? 0} />
                  <EscalationButton 
                    onClick={() => handleEscalation(m, i)} 
                    escalate={!!m.escalate && escalatingIndex === null && !busy} 
                  />
                </div>
              )}
            </div>
          </div>
        ))}
      </div>

      <div style={{display:"flex", gap:8, marginTop:12}}>
        <input 
          value={q} 
          onChange={e => {
            setQ(e.target.value);
            if (error) setError(null); // Clear error when user starts typing
          }}
          onKeyDown={handleKeyDown}
          placeholder="Type your question... (Press Enter to send)"
          maxLength={2000}
          disabled={busy || escalatingIndex !== null}
          aria-label="Chat message input"
          style={{
            flex:1, 
            padding:10, 
            borderRadius:8, 
            border: error ? "1px solid #dc2626" : "1px solid #d1d5db",
            outline: "none"
          }}
        />
        <button 
          onClick={() => { send().catch(console.error); }} 
          disabled={busy || !q.trim() || escalatingIndex !== null} 
          aria-label={busy ? "Sending message" : escalatingIndex !== null ? "Escalation in progress" : "Send message"}
          style={{
            padding:"10px 14px", 
            borderRadius:8, 
            background: busy || !q.trim() || escalatingIndex !== null ? "#9ca3af" : "#2563eb", 
            color:"#fff",
            cursor: busy || !q.trim() || escalatingIndex !== null ? "not-allowed" : "pointer",
            border: "none"
          }}
        >
          {busy ? "..." : escalatingIndex !== null ? "⏳" : "Send"}
        </button>
      </div>
      
      <div 
        style={{
          fontSize: 12, 
          color: q.length > 1800 ? "#dc2626" : q.length > 1500 ? "#f59e0b" : "#6b7280", 
          marginTop: 8,
          fontWeight: q.length > 1800 ? "bold" : "normal"
        }}
        role="status"
        aria-live="polite"
        aria-label={`Character count: ${q.length} of 2000 maximum${q.length > 1800 ? ', approaching limit' : ''}`}
      >
        Characters: {q.length}/2000
        {q.length > 1800 && " ⚠️ Approaching limit"}
        {q.length > 1500 && q.length <= 1800 && " ⚡ Getting close"}
      </div>
    </div>
  );
}