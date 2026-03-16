import React from "react";

export default function JsonEditor({ label, value, onChange }) {
  return (
    <div style={{ marginBottom: 16 }}>
      <h3>{label}</h3>
      <textarea
        style={{ width: "100%", minHeight: 220, fontFamily: "monospace" }}
        value={value}
        onChange={(e) => onChange(e.target.value)}
      />
    </div>
  );
}
