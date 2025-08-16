
import React from "react";
export default function Metrics(){
  return <div style={{maxWidth:960, margin:"40px auto", fontFamily:"ui-sans-serif"}}>
    <h1>Metrics</h1>
    <ul>
      <li>Prometheus at <code>/metrics</code></li>
      <li>MLflow artifacts: Pareto fronts, Δ-surprise, router CM</li>
    </ul>
  </div>;
}
