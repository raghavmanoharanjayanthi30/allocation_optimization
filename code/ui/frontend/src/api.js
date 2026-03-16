const BASE_URL = "http://localhost:8000";

export async function getMethods() {
  const res = await fetch(`${BASE_URL}/methods`);
  if (!res.ok) throw new Error("Failed to load methods");
  return res.json();
}

export async function generateScenario(payload) {
  const res = await fetch(`${BASE_URL}/generate-scenario`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function allocate(payload) {
  const res = await fetch(`${BASE_URL}/allocate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function agentChat(payload) {
  const res = await fetch(`${BASE_URL}/agent/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}
