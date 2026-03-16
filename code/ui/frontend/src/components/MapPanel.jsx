import React, { useMemo } from "react";
import { CircleMarker, MapContainer, Polyline, Popup, TileLayer, useMap } from "react-leaflet";

function isValidLocation(item) {
  return (
    item &&
    item.location &&
    typeof item.location.lat === "number" &&
    typeof item.location.lng === "number"
  );
}

function AutoFitBounds({ points }) {
  const map = useMap();
  React.useEffect(() => {
    if (!points || points.length === 0) return;
    const latMin = Math.min(...points.map((p) => p[0]));
    const latMax = Math.max(...points.map((p) => p[0]));
    const lngMin = Math.min(...points.map((p) => p[1]));
    const lngMax = Math.max(...points.map((p) => p[1]));
    if (latMin === latMax && lngMin === lngMax) {
      map.setView([latMin, lngMin], 13);
      return;
    }
    map.fitBounds(
      [
        [latMin, lngMin],
        [latMax, lngMax],
      ],
      { padding: [40, 40] }
    );
  }, [map, points]);
  return null;
}

export default function MapPanel({ technicians, jobs, assignments, highlightedAssignment }) {
  const { center, lines, points } = useMemo(() => {
    const coords = [];
    technicians.forEach((t) => {
      if (isValidLocation(t)) coords.push([t.location.lat, t.location.lng]);
    });
    jobs.forEach((j) => {
      if (isValidLocation(j)) coords.push([j.location.lat, j.location.lng]);
    });

    const centerPoint = coords.length
      ? [
          coords.reduce((s, c) => s + c[0], 0) / coords.length,
          coords.reduce((s, c) => s + c[1], 0) / coords.length,
        ]
      : [37.7, -122.4];

    const techById = Object.fromEntries(technicians.map((t) => [t.id, t]));
    const jobById = Object.fromEntries(jobs.map((j) => [j.id, j]));
    const assignmentLines = (assignments || [])
      .map((a) => {
        const t = techById[a.technician_id];
        const j = jobById[a.request_id];
        if (!isValidLocation(t) || !isValidLocation(j)) return null;
        return {
          id: `${a.technician_id}-${a.request_id}`,
          technicianId: a.technician_id,
          requestId: a.request_id,
          isHighlighted:
            highlightedAssignment &&
            highlightedAssignment.technicianId === a.technician_id &&
            highlightedAssignment.requestId === a.request_id,
          points: [
            [t.location.lat, t.location.lng],
            [j.location.lat, j.location.lng],
          ],
        };
      })
      .filter(Boolean);

    return { center: centerPoint, lines: assignmentLines, points: coords };
  }, [technicians, jobs, assignments, highlightedAssignment]);

  const linePalette = ["#14b8a6", "#6366f1", "#22c55e", "#0ea5e9", "#f59e0b", "#ec4899"];

  return (
    <div style={{ marginTop: 16 }}>
      <h3>Map View (Technicians, Jobs, Assignments)</h3>
      <small style={{ color: "#2b4b84", display: "block", marginBottom: 8 }}>
        This map shows assignments for one method at a time: the currently selected method in the Method Comparison table.
      </small>
      <small style={{ color: "#2b4b84", display: "block", marginBottom: 8 }}>
        Tip: click a row in Method Comparison or Assignments by Method to change/highlight what is shown here.
      </small>
      <div
        style={{
          height: 460,
          border: "1px solid #d7e3ff",
          borderRadius: 12,
          overflow: "hidden",
          boxShadow: "0 6px 24px rgba(22, 54, 118, 0.12)",
        }}
      >
        <MapContainer center={center} zoom={11} style={{ height: "100%", width: "100%" }}>
          <AutoFitBounds points={points} />
          <TileLayer
            attribution='&copy; OpenStreetMap contributors &copy; CARTO'
            url="https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png"
          />

          {/* Technicians in deep blue */}
          {technicians.map((t) =>
            isValidLocation(t) ? (
              <CircleMarker
                key={`tech-${t.id}`}
                center={[t.location.lat, t.location.lng]}
                radius={8}
                pathOptions={{ color: "#1d4ed8", fillColor: "#3b82f6", fillOpacity: 0.9, weight: 2 }}
              >
                <Popup>
                  <b>Technician:</b> {t.id}
                  <br />
                  Lat/Lng: {t.location.lat.toFixed(4)}, {t.location.lng.toFixed(4)}
                </Popup>
              </CircleMarker>
            ) : null
          )}

          {/* Jobs in warm red */}
          {jobs.map((j) =>
            isValidLocation(j) ? (
              <CircleMarker
                key={`job-${j.id}`}
                center={[j.location.lat, j.location.lng]}
                radius={7}
                pathOptions={{ color: "#b91c1c", fillColor: "#ef4444", fillOpacity: 0.9, weight: 2 }}
              >
                <Popup>
                  <b>Job:</b> {j.id}
                  <br />
                  Lat/Lng: {j.location.lat.toFixed(4)}, {j.location.lng.toFixed(4)}
                </Popup>
              </CircleMarker>
            ) : null
          )}

          {/* Assignment links with varied palette for readability */}
          {lines.map((line, idx) => {
            const color = linePalette[idx % linePalette.length];
            return (
              <Polyline
                key={line.id}
                positions={line.points}
                pathOptions={
                  line.isHighlighted
                    ? { color: "#111827", weight: 6, opacity: 0.95, dashArray: "" }
                    : { color, weight: 3, opacity: 0.8, dashArray: "6 6" }
                }
              >
                <Popup>
                  <b>Assignment</b>
                  <br />
                  {line.technicianId} {"->"} {line.requestId}
                </Popup>
              </Polyline>
            );
          })}
        </MapContainer>
      </div>
      <small style={{ color: "#2b4b84" }}>
        Legend: Blue circles = technicians, Red circles = jobs, Colored dashed lines = current selected method assignments.
      </small>
    </div>
  );
}
