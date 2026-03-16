import React, { useEffect, useState } from "react";
import { agentChat, allocate, generateScenario, getMethods } from "./api";
import MapPanel from "./components/MapPanel";

const METHOD_META = {
  greedy: {
    label: "Greedy Sequential Assignment",
    summary: "Fast method that assigns jobs one-by-one by priority using the best current feasible technician.",
    optimizationAim: "Speed and reasonable local decisions",
  },
  hungarian: {
    label: "Hungarian Batch Optimizer",
    summary: "Global batch matching that finds a best one-to-one assignment for the current batch.",
    optimizationAim: "Global batch matching quality",
  },
  min_cost_flow: {
    label: "Min-Cost Flow Scheduler",
    summary: "Network-flow based assignment that minimizes assignment cost over feasible request-technician edges.",
    optimizationAim: "Structured cost minimization over a flow network",
  },
  milp: {
    label: "Mixed Integer Linear Programming",
    summary: "Mathematical optimization model with binary assignment decisions and explicit constraints.",
    optimizationAim: "Exact/near-exact optimization under constraints",
  },
};

function skillsToText(skillsObj) {
  if (!skillsObj || typeof skillsObj !== "object") return "";
  return Object.entries(skillsObj)
    .map(([k, v]) => `${k}:${v}`)
    .join(", ");
}

function textToSkills(skillsText) {
  const out = {};
  const trimmed = (skillsText || "").trim();
  if (!trimmed) return out;
  const parts = trimmed.split(",").map((p) => p.trim()).filter(Boolean);
  for (const part of parts) {
    const [skill, level] = part.split(":").map((x) => (x || "").trim());
    if (!skill || !level) throw new Error(`Invalid skill format '${part}'. Use Skill:Level.`);
    const n = Number(level);
    if (!Number.isFinite(n) || n < 1 || n > 10) {
      throw new Error(`Skill level for '${skill}' must be a number in [1,10].`);
    }
    out[skill] = Math.round(n);
  }
  return out;
}

function technicianToRow(t) {
  const firstWindow = (t.availability && t.availability[0]) || { start: "", end: "" };
  return {
    id: t.id || "",
    lat: String(t.location?.lat ?? ""),
    lng: String(t.location?.lng ?? ""),
    skillsText: skillsToText(t.skills),
    availableStart: firstWindow.start || "",
    availableEnd: firstWindow.end || "",
    availableHoursPerWeek: String(t.available_hours_per_week ?? 40),
    maxTravelDistance: String(t.max_travel_distance ?? 0.5),
  };
}

function jobToRow(j) {
  return {
    id: j.id || "",
    lat: String(j.location?.lat ?? ""),
    lng: String(j.location?.lng ?? ""),
    requiredSkillsText: skillsToText(j.required_skills),
    timeWindowStart: j.time_window?.start || "",
    timeWindowEnd: j.time_window?.end || "",
    priority: String(j.priority ?? 3),
    estimatedDuration: String(j.estimated_duration ?? 60),
    serviceFee: String(j.service_fee ?? 150),
  };
}

export default function App() {
  const [methods, setMethods] = useState(["greedy", "hungarian", "min_cost_flow", "milp"]);
  const [method, setMethod] = useState("greedy");
  const [technicianRows, setTechnicianRows] = useState([]);
  const [jobRows, setJobRows] = useState([]);
  const [result, setResult] = useState(null);
  const [comparison, setComparison] = useState([]);
  const [comparisonResults, setComparisonResults] = useState({});
  const [selectedComparisonMethod, setSelectedComparisonMethod] = useState("");
  const [selectedAssignment, setSelectedAssignment] = useState(null);
  const [validationErrors, setValidationErrors] = useState([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [scenarioTechCount, setScenarioTechCount] = useState(12);
  const [scenarioJobCount, setScenarioJobCount] = useState(10);
  const [chatInput, setChatInput] = useState("");
  const [chatMessages, setChatMessages] = useState([]);
  const [agentSessionId, setAgentSessionId] = useState(null);
  const [useChatMode, setUseChatMode] = useState(false);
  const [llmApiKey, setLlmApiKey] = useState("");
  const [llmModel, setLlmModel] = useState("gpt-4o-mini");

  function buildComparisonRowsFromResults(resultsByMethod) {
    // Keep rows in dropdown method order for predictable display.
    return methods
      .filter((m) => Boolean(resultsByMethod[m]))
      .map((m) => {
        const data = resultsByMethod[m];
        return {
          method: m,
          assigned: data.assignments?.length || 0,
          unassigned: data.unassigned_job_ids?.length || 0,
        };
      });
  }

  function upsertComparisonRow(rowSummary, fullResult) {
    // Source of truth: full results map. Summary rows are derived from it.
    setComparisonResults((prev) => {
      const next = {
        ...prev,
        [rowSummary.method]: fullResult,
      };
      setComparison(buildComparisonRowsFromResults(next));
      return next;
    });
  }

  function resetAgentSession() {
    setAgentSessionId(null);
  }

  function buildAgentStateFromUi() {
    // Lenient conversion for chat: skip malformed rows instead of blocking.
    const technicians = technicianRows
      .map((row) => {
        const lat = Number(row.lat);
        const lng = Number(row.lng);
        if (!row.id || !Number.isFinite(lat) || !Number.isFinite(lng)) return null;
        let skills = {};
        try {
          skills = textToSkills(row.skillsText);
        } catch (_e) {
          skills = {};
        }
        return {
          id: row.id,
          location: { lat, lng },
          skills,
          availability: [{ start: row.availableStart, end: row.availableEnd }],
          available_hours_per_week: Number(row.availableHoursPerWeek) || 40,
          max_travel_distance: Number(row.maxTravelDistance) || 0.5,
        };
      })
      .filter(Boolean);

    const jobs = jobRows
      .map((row) => {
        const lat = Number(row.lat);
        const lng = Number(row.lng);
        if (!row.id || !Number.isFinite(lat) || !Number.isFinite(lng)) return null;
        let requiredSkills = {};
        try {
          requiredSkills = textToSkills(row.requiredSkillsText);
        } catch (_e) {
          requiredSkills = {};
        }
        return {
          id: row.id,
          location: { lat, lng },
          required_skills: requiredSkills,
          time_window: { start: row.timeWindowStart, end: row.timeWindowEnd },
          priority: Number(row.priority) || 3,
          estimated_duration: Number(row.estimatedDuration) || 60,
          service_fee: Number(row.serviceFee) || 150,
        };
      })
      .filter(Boolean);

    return {
      method,
      technicians,
      jobs,
      comparison_results: comparisonResults,
      selected_method: selectedComparisonMethod || null,
    };
  }

  useEffect(() => {
    getMethods()
      .then((data) => setMethods(data.methods || methods))
      .catch(() => {});
  }, []);

  async function handleGenerate() {
    if (useChatMode) {
      setError("These controls are disabled when using agent chat mode.");
      return;
    }
    setLoading(true);
    setError("");
    try {
      resetAgentSession();
      const scenario = await generateScenario({
        technician_count: Math.max(1, Number(scenarioTechCount) || 1),
        job_count: Math.max(1, Number(scenarioJobCount) || 1),
        technician_seed: null,
        job_seed: null,
      });
      setTechnicianRows((scenario.technicians || []).map(technicianToRow));
      setJobRows((scenario.jobs || []).map(jobToRow));
      setResult(null);
      setComparison([]);
      setComparisonResults({});
      setSelectedComparisonMethod("");
      setSelectedAssignment(null);
      setValidationErrors([]);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }

  function validateAndBuildPayload() {
    const errors = [];
    const technicians = technicianRows.map((row, idx) => {
      const lat = Number(row.lat);
      const lng = Number(row.lng);
      const availableHours = Number(row.availableHoursPerWeek);
      const maxTravelDistance = Number(row.maxTravelDistance);
      const start = new Date(row.availableStart);
      const end = new Date(row.availableEnd);
      if (!row.id) errors.push(`Technician row ${idx + 1}: id is required.`);
      if (!Number.isFinite(lat) || !Number.isFinite(lng)) {
        errors.push(`Technician ${row.id || idx + 1}: lat/lng must be valid numbers.`);
      }
      if (!Number.isFinite(availableHours)) {
        errors.push(`Technician ${row.id || idx + 1}: available hours must be a number.`);
      }
      if (!Number.isFinite(maxTravelDistance)) {
        errors.push(`Technician ${row.id || idx + 1}: max travel distance must be a number.`);
      }
      if (!(start instanceof Date) || Number.isNaN(start.getTime()) || !(end instanceof Date) || Number.isNaN(end.getTime())) {
        errors.push(`Technician ${row.id || idx + 1}: availability start/end must be valid datetime strings.`);
      } else if (start >= end) {
        errors.push(`Technician ${row.id || idx + 1}: availability start must be before end.`);
      }
      let skills = {};
      try {
        skills = textToSkills(row.skillsText);
      } catch (e) {
        errors.push(`Technician ${row.id || idx + 1}: ${String(e.message || e)}`);
      }
      return {
        id: row.id,
        location: { lat, lng },
        skills,
        availability: [{ start: row.availableStart, end: row.availableEnd }],
        available_hours_per_week: availableHours,
        max_travel_distance: maxTravelDistance,
      };
    });

    const jobs = jobRows.map((row, idx) => {
      const lat = Number(row.lat);
      const lng = Number(row.lng);
      const priority = Number(row.priority);
      const estimatedDuration = Number(row.estimatedDuration);
      const serviceFee = Number(row.serviceFee);
      const start = new Date(row.timeWindowStart);
      const end = new Date(row.timeWindowEnd);
      if (!row.id) errors.push(`Job row ${idx + 1}: id is required.`);
      if (!Number.isFinite(lat) || !Number.isFinite(lng)) {
        errors.push(`Job ${row.id || idx + 1}: lat/lng must be valid numbers.`);
      }
      if (!Number.isFinite(priority) || priority < 1 || priority > 5) {
        errors.push(`Job ${row.id || idx + 1}: priority must be between 1 and 5.`);
      }
      if (!Number.isFinite(estimatedDuration) || estimatedDuration <= 0) {
        errors.push(`Job ${row.id || idx + 1}: estimated duration must be > 0.`);
      }
      if (!Number.isFinite(serviceFee) || serviceFee < 0) {
        errors.push(`Job ${row.id || idx + 1}: service fee must be >= 0.`);
      }
      if (!(start instanceof Date) || Number.isNaN(start.getTime()) || !(end instanceof Date) || Number.isNaN(end.getTime())) {
        errors.push(`Job ${row.id || idx + 1}: time window start/end must be valid datetime strings.`);
      } else if (start >= end) {
        errors.push(`Job ${row.id || idx + 1}: time window start must be before end.`);
      }
      let requiredSkills = {};
      try {
        requiredSkills = textToSkills(row.requiredSkillsText);
      } catch (e) {
        errors.push(`Job ${row.id || idx + 1}: ${String(e.message || e)}`);
      }
      return {
        id: row.id,
        location: { lat, lng },
        required_skills: requiredSkills,
        time_window: { start: row.timeWindowStart, end: row.timeWindowEnd },
        priority: Math.round(priority),
        estimated_duration: estimatedDuration,
        service_fee: serviceFee,
      };
    });

    setValidationErrors(errors);
    if (errors.length > 0) throw new Error("Validation failed. See validation errors section.");
    return { technicians, jobs };
  }

  async function handleRun() {
    if (useChatMode) {
      setError("These controls are disabled when using agent chat mode.");
      return;
    }
    setLoading(true);
    setError("");
    try {
      resetAgentSession();
      const { technicians, jobs } = validateAndBuildPayload();
      const data = await allocate({ method, technicians, jobs });
      setResult(data);
      setSelectedComparisonMethod(method);
      setSelectedAssignment(null);
      upsertComparisonRow(
        {
          method,
          assigned: data.assignments?.length || 0,
          unassigned: data.unassigned_job_ids?.length || 0,
        },
        data
      );
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }

  async function handleRunAll() {
    if (useChatMode) {
      setError("These controls are disabled when using agent chat mode.");
      return;
    }
    setLoading(true);
    setError("");
    try {
      resetAgentSession();
      const { technicians, jobs } = validateAndBuildPayload();
      const promises = methods.map(async (m) => {
        const data = await allocate({ method: m, technicians, jobs });
        return {
          fullResult: data,
          method: m,
          assigned: data.assignments?.length || 0,
          unassigned: data.unassigned_job_ids?.length || 0,
        };
      });
      const rows = await Promise.all(promises);
      const fullByMethod = {};
      rows.forEach((row) => {
        fullByMethod[row.method] = row.fullResult;
      });
      setComparison(buildComparisonRowsFromResults(fullByMethod));
      setComparisonResults(fullByMethod);
      const firstMethod = methods.find((m) => Boolean(fullByMethod[m]));
      if (firstMethod) {
        const initialMethod = firstMethod;
        setSelectedComparisonMethod(initialMethod);
        setResult(fullByMethod[initialMethod]);
        setSelectedAssignment(null);
      }
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }

  const technicians = technicianRows.map((row) => ({
    id: row.id,
    location: { lat: Number(row.lat), lng: Number(row.lng) },
  }));
  const jobs = jobRows.map((row) => ({
    id: row.id,
    location: { lat: Number(row.lat), lng: Number(row.lng) },
  }));

  function handleSelectComparisonMethod(methodName) {
    const selected = comparisonResults[methodName];
    if (!selected) return;
    setSelectedComparisonMethod(methodName);
    setResult(selected);
    setMethod(methodName);
    setSelectedAssignment(null);
  }

  function handleSelectAssignment(methodName, assignment) {
    if (!assignment) return;
    handleSelectComparisonMethod(methodName);
    setSelectedAssignment({
      method: methodName,
      requestId: assignment.request_id,
      technicianId: assignment.technician_id,
    });
  }

  function addTechnicianRow() {
    resetAgentSession();
    setTechnicianRows((prev) => [
      ...prev,
      {
        id: `T${String(prev.length + 1).padStart(3, "0")}`,
        lat: "37.70",
        lng: "-122.40",
        skillsText: "HVAC:5, Electrical:4",
        availableStart: "2026-03-14T08:00:00",
        availableEnd: "2026-03-14T12:00:00",
        availableHoursPerWeek: "40",
        maxTravelDistance: "0.5",
      },
    ]);
  }

  function addJobRow() {
    resetAgentSession();
    setJobRows((prev) => [
      ...prev,
      {
        id: `R${String(prev.length + 1).padStart(3, "0")}`,
        lat: "37.72",
        lng: "-122.38",
        requiredSkillsText: "HVAC:3",
        timeWindowStart: "2026-03-14T08:30:00",
        timeWindowEnd: "2026-03-14T11:30:00",
        priority: "3",
        estimatedDuration: "60",
        serviceFee: "180",
      },
    ]);
  }

  function updateTechnicianRow(index, key, value) {
    resetAgentSession();
    setTechnicianRows((prev) => prev.map((r, i) => (i === index ? { ...r, [key]: value } : r)));
  }

  function updateJobRow(index, key, value) {
    resetAgentSession();
    setJobRows((prev) => prev.map((r, i) => (i === index ? { ...r, [key]: value } : r)));
  }

  function deleteTechnicianRow(index) {
    resetAgentSession();
    setTechnicianRows((prev) => prev.filter((_r, i) => i !== index));
  }

  function deleteJobRow(index) {
    resetAgentSession();
    setJobRows((prev) => prev.filter((_r, i) => i !== index));
  }

  async function handleSendChat() {
    if (!useChatMode) {
      setError("Enable 'Use chat interface mode' before sending chat requests.");
      return;
    }
    if (!llmApiKey.trim()) {
      setError("OpenAI API key is required for chat interface mode.");
      return;
    }
    if (!llmModel.trim()) {
      setError("Model name is required for chat interface mode.");
      return;
    }
    const msg = chatInput.trim();
    if (!msg) return;
    setChatMessages((prev) => [...prev, { role: "user", text: msg }]);
    setChatInput("");
    setLoading(true);
    setError("");
    try {
      const requestPayload = {
        message: msg,
        session_id: agentSessionId || undefined,
        llm_api_key: llmApiKey.trim() || undefined,
        llm_model: llmModel.trim() || undefined,
      };
      // If no session exists, seed agent memory from current UI.
      if (!agentSessionId) {
        requestPayload.state = buildAgentStateFromUi();
      }
      const response = await agentChat(requestPayload);
      setAgentSessionId(response.session_id || null);
      const newState = response.state;
      setMethod(newState.method || method);
      setTechnicianRows((newState.technicians || []).map(technicianToRow));
      setJobRows((newState.jobs || []).map(jobToRow));
      const nextComparisonResults = newState.comparison_results || {};
      setComparisonResults(nextComparisonResults);
      setComparison(buildComparisonRowsFromResults(nextComparisonResults));
      const selected = newState.selected_method || newState.method || "";
      setSelectedComparisonMethod(selected);
      if (selected && nextComparisonResults[selected]) {
        setResult(nextComparisonResults[selected]);
      } else {
        setResult(null);
      }
      setChatMessages((prev) => [
        ...prev,
        { role: "assistant", text: response.assistant_message || "Done." },
      ]);
    } catch (e) {
      const text = String(e);
      setError(text);
      setChatMessages((prev) => [...prev, { role: "assistant", text: `Error: ${text}` }]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="page">
      <h1>Field Service Allocation Assistant</h1>
      <p className="subtitle">
        Test optimization methods, compare outcomes, and visualize assignments on map.
      </p>

      <section className="card">
        <h2>What Constraints Are Applied?</h2>
        <p>
          <b>Hard constraints</b> (must be satisfied): skill-level requirement match, availability/time-window feasibility,
          no overlapping booking, technician max travel distance, minimum available weekly hours.
        </p>
        <p>
          <b>Soft constraints</b> (used for ranking): prefer higher service fee, lower travel distance, and stronger skill fit.
        </p>
      </section>

      <section className="card">
        <h2>Optimization Methods (High-Level)</h2>
        {methods.map((methodId) => (
          <div key={methodId} style={{ marginBottom: 10 }}>
            <b>{METHOD_META[methodId]?.label || methodId}</b>
            <div>{METHOD_META[methodId]?.summary || "Optimization method"}</div>
            <small>
              Target: {METHOD_META[methodId]?.optimizationAim || "Method-specific optimization"}
            </small>
          </div>
        ))}
      </section>

      <section className="card">
        <h2>Agent Chat</h2>
        <p>Choose a mode: chat interface (agent-driven) or manual controls.</p>
        <div className="toolbar">
          <label style={{ alignSelf: "center", fontWeight: 600, color: "#33425b" }}>
            <input
              type="checkbox"
              checked={useChatMode}
              onChange={(e) => setUseChatMode(e.target.checked)}
              style={{ marginRight: 8 }}
            />
            Use chat interface mode
          </label>
          <small style={{ alignSelf: "center", color: useChatMode ? "#8b2f2f" : "#2b4b84" }}>
            {useChatMode ? "Chat mode active: manual run controls are disabled." : "Manual mode active."}
          </small>
        </div>
        <div className="toolbar">
          <input
            value={llmModel}
            onChange={(e) => setLlmModel(e.target.value)}
            placeholder="LLM model (e.g. gpt-4o-mini)"
            style={{ width: 220 }}
            disabled={!useChatMode}
          />
          <input
            value={llmApiKey}
            onChange={(e) => setLlmApiKey(e.target.value)}
            placeholder="OpenAI API key (required for chat mode)"
            type="password"
            style={{ flex: 1 }}
            disabled={!useChatMode}
          />
        </div>
        <small style={{ color: "#2b4b84" }}>
          Session memory: {agentSessionId ? `active (${agentSessionId.slice(0, 8)}...)` : "not initialized yet"}
        </small>
        <div className="chatBox">
          {chatMessages.map((m, idx) => (
            <div key={idx} className={`chatMessage ${m.role === "user" ? "chatUser" : "chatAssistant"}`}>
              {m.text}
            </div>
          ))}
        </div>
        <div className="toolbar">
          <input
            value={chatInput}
            onChange={(e) => setChatInput(e.target.value)}
            placeholder="Type a request for the agent..."
            style={{ flex: 1 }}
          />
          <button onClick={handleSendChat} disabled={loading || !useChatMode}>
            Send
          </button>
        </div>
      </section>

      <h2 style={{ marginTop: 0 }}>Manual Controls</h2>
      <fieldset className="manualControlsFieldset" disabled={useChatMode}>
        <div className="toolbar">
          <label style={{ alignSelf: "center", color: "#33425b", fontWeight: 600 }}>Workers</label>
          <input
            type="number"
            min={1}
            max={500}
            value={scenarioTechCount}
            onChange={(e) => setScenarioTechCount(Number(e.target.value))}
            style={{ width: 90 }}
            disabled={useChatMode}
          />
          <label style={{ alignSelf: "center", color: "#33425b", fontWeight: 600 }}>Jobs</label>
          <input
            type="number"
            min={1}
            max={1000}
            value={scenarioJobCount}
            onChange={(e) => setScenarioJobCount(Number(e.target.value))}
            style={{ width: 90 }}
            disabled={useChatMode}
          />
          <button onClick={handleGenerate} disabled={loading || useChatMode}>
            Generate Random Scenario
          </button>
          <button onClick={handleRunAll} disabled={loading || useChatMode}>
            Run All Methods
          </button>
        </div>

        <div className="toolbar">
          <span style={{ alignSelf: "center", fontWeight: 600, color: "#33425b" }}>Optional single-method run:</span>
          <select value={method} onChange={(e) => setMethod(e.target.value)} disabled={useChatMode}>
            {methods.map((m) => (
              <option key={m} value={m}>
                {METHOD_META[m]?.label || m}
              </option>
            ))}
          </select>
          <button onClick={handleRun} disabled={loading || useChatMode}>
            Run Allocation
          </button>
        </div>
      </fieldset>
      <small style={{ color: useChatMode ? "#8b2f2f" : "#4a5f86", display: "block", marginBottom: 10 }}>
        These controls are disabled when using agent chat mode.
      </small>

      {error ? <pre style={{ color: "crimson" }}>{error}</pre> : null}
      {validationErrors.length > 0 ? (
        <section className="card">
          <h3>Validation Errors</h3>
          <ul>
            {validationErrors.map((err, idx) => (
              <li key={idx}>{err}</li>
            ))}
          </ul>
        </section>
      ) : null}

      <section className="card">
        <h2>Data Entry Guide</h2>
        <p>
          Skills format: <code>Skill:Level, Skill:Level</code> (example: <code>HVAC:5, Electrical:4</code>).
        </p>
        <p>
          Datetime format: ISO string (example: <code>2026-03-14T08:00:00</code>).
        </p>
      </section>

      <section className="card">
        <div className="tableHeader">
          <h2>Technicians</h2>
          <button onClick={addTechnicianRow}>Add Technician</button>
        </div>
        <div className="tableWrap">
          <table className="grid">
            <thead>
              <tr>
                <th>ID</th><th>Lat</th><th>Lng</th><th>Skills (Skill:Level)</th>
                <th>Available Start</th><th>Available End</th><th>Hours/Week</th><th>Max Distance</th><th />
              </tr>
            </thead>
            <tbody>
              {technicianRows.map((row, idx) => (
                <tr key={`${row.id}-${idx}`}>
                  <td><input value={row.id} onChange={(e) => updateTechnicianRow(idx, "id", e.target.value)} /></td>
                  <td><input value={row.lat} onChange={(e) => updateTechnicianRow(idx, "lat", e.target.value)} /></td>
                  <td><input value={row.lng} onChange={(e) => updateTechnicianRow(idx, "lng", e.target.value)} /></td>
                  <td><input value={row.skillsText} onChange={(e) => updateTechnicianRow(idx, "skillsText", e.target.value)} /></td>
                  <td><input value={row.availableStart} onChange={(e) => updateTechnicianRow(idx, "availableStart", e.target.value)} /></td>
                  <td><input value={row.availableEnd} onChange={(e) => updateTechnicianRow(idx, "availableEnd", e.target.value)} /></td>
                  <td><input value={row.availableHoursPerWeek} onChange={(e) => updateTechnicianRow(idx, "availableHoursPerWeek", e.target.value)} /></td>
                  <td><input value={row.maxTravelDistance} onChange={(e) => updateTechnicianRow(idx, "maxTravelDistance", e.target.value)} /></td>
                  <td><button onClick={() => deleteTechnicianRow(idx)}>Delete</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="card">
        <div className="tableHeader">
          <h2>Jobs</h2>
          <button onClick={addJobRow}>Add Job</button>
        </div>
        <div className="tableWrap">
          <table className="grid">
            <thead>
              <tr>
                <th>ID</th><th>Lat</th><th>Lng</th><th>Required Skills (Skill:Level)</th>
                <th>Window Start</th><th>Window End</th><th>Priority (1-5)</th><th>Duration (min)</th><th>Service Fee</th><th />
              </tr>
            </thead>
            <tbody>
              {jobRows.map((row, idx) => (
                <tr key={`${row.id}-${idx}`}>
                  <td><input value={row.id} onChange={(e) => updateJobRow(idx, "id", e.target.value)} /></td>
                  <td><input value={row.lat} onChange={(e) => updateJobRow(idx, "lat", e.target.value)} /></td>
                  <td><input value={row.lng} onChange={(e) => updateJobRow(idx, "lng", e.target.value)} /></td>
                  <td><input value={row.requiredSkillsText} onChange={(e) => updateJobRow(idx, "requiredSkillsText", e.target.value)} /></td>
                  <td><input value={row.timeWindowStart} onChange={(e) => updateJobRow(idx, "timeWindowStart", e.target.value)} /></td>
                  <td><input value={row.timeWindowEnd} onChange={(e) => updateJobRow(idx, "timeWindowEnd", e.target.value)} /></td>
                  <td><input value={row.priority} onChange={(e) => updateJobRow(idx, "priority", e.target.value)} /></td>
                  <td><input value={row.estimatedDuration} onChange={(e) => updateJobRow(idx, "estimatedDuration", e.target.value)} /></td>
                  <td><input value={row.serviceFee} onChange={(e) => updateJobRow(idx, "serviceFee", e.target.value)} /></td>
                  <td><button onClick={() => deleteJobRow(idx)}>Delete</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {comparison.length > 0 ? (
        <div className="card">
          <h2>Method Comparison</h2>
          <table style={{ borderCollapse: "collapse", width: "100%" }}>
            <thead>
              <tr>
                <th style={{ borderBottom: "1px solid #ddd", textAlign: "left", padding: 8 }}>Method</th>
                <th style={{ borderBottom: "1px solid #ddd", textAlign: "right", padding: 8 }}>Assigned</th>
                <th style={{ borderBottom: "1px solid #ddd", textAlign: "right", padding: 8 }}>Unassigned</th>
              </tr>
            </thead>
            <tbody>
              {comparison.map((row) => (
                <tr
                  key={row.method}
                  onClick={() => handleSelectComparisonMethod(row.method)}
                  style={{
                    cursor: "pointer",
                    backgroundColor: selectedComparisonMethod === row.method ? "#eef6ff" : "transparent",
                  }}
                >
                  <td style={{ borderBottom: "1px solid #eee", padding: 8 }}>{METHOD_META[row.method]?.label || row.method}</td>
                  <td style={{ borderBottom: "1px solid #eee", textAlign: "right", padding: 8 }}>{row.assigned}</td>
                  <td style={{ borderBottom: "1px solid #eee", textAlign: "right", padding: 8 }}>{row.unassigned}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}

      {comparison.length > 0 ? (
        <section className="card">
          <h2>Assignments by Method</h2>
          <p style={{ color: "#42506a", marginTop: 0 }}>
            Technician-job pairs for every method that has been run.
          </p>
          <small style={{ color: "#2b4b84", display: "block", marginBottom: 10 }}>
            Click a row to highlight that assignment on the map.
          </small>
          {methods
            .filter((m) => Boolean(comparisonResults[m]))
            .map((methodId) => {
              const data = comparisonResults[methodId] || {};
              const assignments = data.assignments || [];
              return (
                <div key={`assignments-${methodId}`} style={{ marginBottom: 14 }}>
                  <h3 style={{ marginBottom: 8 }}>{METHOD_META[methodId]?.label || methodId}</h3>
                  {assignments.length === 0 ? (
                    <small style={{ color: "#4a5f86" }}>No assignments yet for this method.</small>
                  ) : (
                    <div className="tableWrap">
                      <table className="grid assignmentGrid">
                        <thead>
                          <tr>
                            <th>Job ID</th>
                            <th>Worker ID</th>
                          </tr>
                        </thead>
                        <tbody>
                          {assignments.map((a, idx) => (
                            <tr
                              key={`${methodId}-${a.request_id}-${a.technician_id}-${idx}`}
                              onClick={() => handleSelectAssignment(methodId, a)}
                              className={
                                selectedAssignment &&
                                selectedAssignment.method === methodId &&
                                selectedAssignment.requestId === a.request_id &&
                                selectedAssignment.technicianId === a.technician_id
                                  ? "assignmentRow assignmentRowActive"
                                  : "assignmentRow"
                              }
                            >
                              <td>{a.request_id}</td>
                              <td>{a.technician_id}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              );
            })}
        </section>
      ) : null}

      <MapPanel
        technicians={technicians}
        jobs={jobs}
        assignments={result?.assignments || []}
        highlightedAssignment={selectedAssignment}
      />
    </div>
  );
}
