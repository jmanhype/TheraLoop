import React from "react";

export function ConfidenceBadge({ lpSum }:{ lpSum:number }){
  let label = "High";
  if (lpSum < -40) label = "Low";      // Adjusted for backend values like -45.2
  else if (lpSum < -20) label = "Medium"; // Adjusted for backend values like -25.8
  
  const color = label==="High"?"#16a34a":label==="Medium"?"#f59e0b":"#dc2626";
  
  return (
    <span 
      style={{padding:"4px 8px", borderRadius:8, background:color, color:"#fff", fontSize:12}}
      title={`Confidence: ${label} (Score: ${lpSum.toFixed(1)})`}
    >
      {label}
    </span>
  );
}