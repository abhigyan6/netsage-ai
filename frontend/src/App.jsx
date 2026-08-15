import { useState } from "react";
import "./App.css";

function App() {
  const [caseId, setCaseId] = useState("CASE001");

  const [symptom, setSymptom] = useState(
    "PC0 can ping its gateway at 192.168.10.1 but cannot reach Server0 at 192.168.20.10."
  );

  const [topology, setTopology] = useState(
    "PC0 -> Switch0 -> Router0 -> Server0"
  );

  const [affectedNetwork, setAffectedNetwork] = useState("192.168.20.");

  const [showOutput, setShowOutput] = useState(`Interface              IP-Address      OK? Method Status                Protocol
GigabitEthernet0/0     192.168.10.1    YES manual up                    up
GigabitEthernet0/1     192.168.20.1    YES manual administratively down down
GigabitEthernet0/2     unassigned      YES unset  administratively down down
Vlan1                  unassigned      YES unset  administratively down down`);

  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const diagnoseNetwork = async () => {
    setLoading(true);
    setError("");
    setResult(null);

    const requestData = {
      case_id: caseId,
      symptom: symptom,
      topology: topology,
      show_ip_interface_brief: showOutput,
      affected_network: affectedNetwork,
    };

    try {
      const response = await fetch("http://127.0.0.1:8000/diagnose", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(requestData),
      });

      if (!response.ok) {
        throw new Error(`Backend returned HTTP ${response.status}`);
      }

      const data = await response.json();
      setResult(data);
    } catch (err) {
      setError(
        "Could not connect to NetSage backend. Make sure FastAPI is running on port 8000."
      );
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const getSeverityClass = (severity) => {
    if (!severity) return "";

    return severity.toLowerCase();
  };

  return (
    <div className="app">
      {/* HEADER */}
      <header className="header">
        <div>
          <h1>NetSage AI</h1>
          <p>AI-Powered Cisco Network Troubleshooting Assistant</p>
        </div>

        <div className="status">
          <span className="status-dot"></span>
          Backend Online
        </div>
      </header>

      <main className="container">

        {/* INPUT SECTION */}
        <section className="card">
          <div className="section-title">
            <h2>Network Troubleshooting Case</h2>
            <span>INPUT</span>
          </div>

          <div className="grid">
            <div className="field">
              <label>Case ID</label>
              <input
                value={caseId}
                onChange={(e) => setCaseId(e.target.value)}
              />
            </div>

            <div className="field">
              <label>Affected Network</label>
              <input
                value={affectedNetwork}
                onChange={(e) => setAffectedNetwork(e.target.value)}
              />
            </div>
          </div>

          <div className="field">
            <label>Symptom</label>
            <textarea
              rows="3"
              value={symptom}
              onChange={(e) => setSymptom(e.target.value)}
            />
          </div>

          <div className="field">
            <label>Topology</label>
            <input
              value={topology}
              onChange={(e) => setTopology(e.target.value)}
            />
          </div>

          <div className="field">
            <label>Cisco `show ip interface brief`</label>
            <textarea
              className="terminal-input"
              rows="8"
              value={showOutput}
              onChange={(e) => setShowOutput(e.target.value)}
            />
          </div>

          <button
            className="diagnose-button"
            onClick={diagnoseNetwork}
            disabled={loading}
          >
            {loading ? "Analyzing Network..." : "Analyze Network"}
          </button>
        </section>

        {/* ERROR */}
        {error && (
          <section className="error-box">
            <strong>Connection Error</strong>
            <p>{error}</p>
          </section>
        )}

        {/* RESULTS */}
        {result && (
          <>
            <section className="result-header">
              <div>
                <h2>Diagnosis Result</h2>
                <p>Case: {result.case_id}</p>
              </div>

              {result.rule_checker_result?.severity && (
                <span
                  className={`severity ${getSeverityClass(
                    result.rule_checker_result.severity
                  )}`}
                >
                  {result.rule_checker_result.severity}
                </span>
              )}
            </section>

            {/* RULE CHECKER */}
            <section className="card">
              <div className="section-title">
                <h2>Rule Checker</h2>
                <span>DETERMINISTIC</span>
              </div>

              <div className="rule-result">
                <div className="rule-type">
                  {result.rule_checker_result?.type}
                </div>

                <p>
                  {result.rule_checker_result?.message}
                </p>
              </div>

              {result.rule_checker_result?.interface && (
                <div className="details-grid">
                  <div>
                    <small>Interface</small>
                    <strong>
                      {result.rule_checker_result.interface}
                    </strong>
                  </div>

                  <div>
                    <small>IP Address</small>
                    <strong>
                      {result.rule_checker_result.ip_address}
                    </strong>
                  </div>

                  <div>
                    <small>Status</small>
                    <strong>
                      {result.rule_checker_result.status}
                    </strong>
                  </div>

                  {result.rule_checker_result.protocol && (
                    <div>
                      <small>Protocol</small>
                      <strong>
                        {result.rule_checker_result.protocol}
                      </strong>
                    </div>
                  )}
                </div>
              )}
            </section>

            {/* AI DIAGNOSIS */}
            <section className="card ai-card">
              <div className="section-title">
                <h2>NetSage AI Diagnosis</h2>
                <span>AI</span>
              </div>

              <div className="root-cause">
                <h3>Root Cause</h3>
                <p>
                  {result.ai_diagnosis?.root_cause}
                </p>
              </div>

              {/* CONFIDENCE */}
              <div className="confidence-section">
                <div className="confidence-header">
                  <span>AI Confidence</span>
                  <strong>
                    {Math.round(
                      (result.ai_diagnosis?.confidence || 0) * 100
                    )}
                    %
                  </strong>
                </div>

                <div className="confidence-bar">
                  <div
                    className="confidence-fill"
                    style={{
                      width: `${
                        (result.ai_diagnosis?.confidence || 0) * 100
                      }%`,
                    }}
                  ></div>
                </div>
              </div>

              {/* EVIDENCE */}
              <div className="subsection">
                <h3>Evidence</h3>

                <div className="evidence-list">
                  {result.ai_diagnosis?.evidence?.map(
                    (item, index) => (
                      <div className="evidence-item" key={index}>
                        {typeof item === "string" ? (
                          <p>{item}</p>
                        ) : (
                          <pre>
                            {JSON.stringify(item, null, 2)}
                          </pre>
                        )}
                      </div>
                    )
                  )}
                </div>
              </div>

              {/* NEXT COMMAND */}
              <div className="subsection">
                <h3>Recommended Next Command</h3>

                <div className="command">
                  <span>$</span>
                  {result.ai_diagnosis?.next_command}
                </div>
              </div>

              {/* FIX */}
              <div className="subsection">
                <h3>Recommended Fix</h3>

                {result.ai_diagnosis?.fix_steps?.length > 0 ? (
                  <div className="fix-box">
                    {result.ai_diagnosis.fix_steps.map(
                      (step, index) => (
                        <div className="fix-step" key={index}>
                          <span>{index + 1}</span>
                          <code>{step}</code>
                        </div>
                      )
                    )}
                  </div>
                ) : (
                  <div className="no-fix">
                    No automatic fix is recommended.
                  </div>
                )}
              </div>

              {/* HUMAN APPROVAL */}
              {result.ai_diagnosis?.fix_steps?.length > 0 && (
                <div className="approval-warning">
                  <strong>Human Approval Required</strong>
                  <p>
                    NetSage AI only recommends the configuration
                    change. It does not execute the Cisco commands
                    automatically.
                  </p>
                </div>
              )}
            </section>
          </>
        )}
      </main>

      <footer>
        <p>
          NetSage AI • Cisco Network Troubleshooting • Human-in-the-Loop
        </p>
      </footer>
    </div>
  );
}

export default App;