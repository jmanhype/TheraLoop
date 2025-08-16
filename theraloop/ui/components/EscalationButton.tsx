
import React from "react";
export function EscalationButton({ onClick, escalate }:{ onClick:()=>void, escalate:boolean }){
  return <button onClick={onClick} disabled={!escalate} style={{padding:"6px 10px", borderRadius:8, background: escalate ? "#dc2626" : "#9ca3af", color:"#fff"}}>
    {escalate ? "Escalate to Human" : "No Escalation Needed"}
  </button>;
}
