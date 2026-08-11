/**
 * BizPilot AI Monitoring Dashboard JavaScript
 * Real-time Chart.js stats and live agent step stream updates.
 */

document.addEventListener("DOMContentLoaded", () => {
  let latencyChart = null;
  let statusChart = null;
  let memoryChart = null;

  function initCharts() {
    const ctxLatency = document.getElementById("latencyChart")?.getContext("2d");
    if (ctxLatency) {
      latencyChart = new Chart(ctxLatency, {
        type: "bar",
        data: {
          labels: [],
          datasets: [
            {
              label: "Avg Latency (ms)",
              data: [],
              backgroundColor: "rgba(59, 130, 246, 0.6)",
              borderColor: "rgba(59, 130, 246, 1)",
              borderWidth: 1,
              borderRadius: 6,
            },
          ],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: { legend: { display: false } },
          scales: { y: { beginAtZero: true } },
        },
      });
    }

    const ctxStatus = document.getElementById("statusChart")?.getContext("2d");
    if (ctxStatus) {
      statusChart = new Chart(ctxStatus, {
        type: "doughnut",
        data: {
          labels: ["Completed", "Failed", "Running / Pending"],
          datasets: [
            {
              data: [0, 0, 0],
              backgroundColor: ["#10b981", "#ef4444", "#3b82f6"],
            },
          ],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: { legend: { position: "bottom" } },
        },
      });
    }

    const ctxMemory = document.getElementById("memoryChart")?.getContext("2d");
    if (ctxMemory) {
      memoryChart = new Chart(ctxMemory, {
        type: "pie",
        data: {
          labels: [],
          datasets: [
            {
              data: [],
              backgroundColor: ["#8b5cf6", "#ec4899", "#f59e0b", "#06b6d4"],
            },
          ],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: { legend: { position: "bottom" } },
        },
      });
    }
  }

  async function fetchDashboardStats() {
    try {
      const response = await fetch("/api/dashboard/stats", {
        headers: { Accept: "application/json" },
      });

      if (!response.ok) return;
      const data = await response.json();
      if (!data.success) return;

      // 1. Update Metrics Cards
      document.getElementById("statTotalJobs").textContent = data.summary.total_jobs;
      document.getElementById("statSuccessRate").textContent = `${data.summary.success_rate}%`;
      document.getElementById("statRunningJobs").textContent = data.summary.running_jobs;
      document.getElementById("statFailedJobs").textContent = data.summary.failed_jobs;
      document.getElementById("statTotalMemories").textContent = data.summary.total_memories;

      // 2. Update Latency Chart
      const latencyLabels = [
        ...data.agent_latencies.map((a) => a.agent_name),
        ...data.tool_latencies.map((t) => t.tool_name),
      ];
      const latencyValues = [
        ...data.agent_latencies.map((a) => a.avg_latency_ms),
        ...data.tool_latencies.map((t) => t.avg_latency_ms),
      ];

      if (latencyChart) {
        latencyChart.data.labels = latencyLabels;
        latencyChart.data.datasets[0].data = latencyValues;
        latencyChart.update();
      }

      // 3. Update Status Chart
      if (statusChart) {
        statusChart.data.datasets[0].data = [
          data.summary.completed_jobs,
          data.summary.failed_jobs,
          data.summary.running_jobs,
        ];
        statusChart.update();
      }

      // 4. Update Memory Chart
      if (memoryChart && data.memory_stats) {
        memoryChart.data.labels = data.memory_stats.map((m) => m.memory_type);
        memoryChart.data.datasets[0].data = data.memory_stats.map((m) => m.count);
        memoryChart.update();
      }

      // 5. Update Recent Jobs Table
      const tableBody = document.getElementById("recentJobsTableBody");
      if (tableBody) {
        if (!data.recent_jobs || data.recent_jobs.length === 0) {
          tableBody.innerHTML = `<tr><td colspan="5" style="padding: 1rem; text-align: center; color: var(--text-muted);">No automated workflow jobs triggered yet.</td></tr>`;
        } else {
          tableBody.innerHTML = data.recent_jobs
            .map((job) => {
              const statusColor =
                job.status === "completed"
                  ? "#10b981"
                  : job.status === "failed"
                  ? "#ef4444"
                  : "#3b82f6";
              const duration = job.execution_time_ms ? `${job.execution_time_ms}ms` : "-";
              const summary = (job.decision_summary || "Automated run").substring(0, 60);

              return `<tr style="border-bottom: 1px solid var(--border-color, #e5e7eb);">
                <td style="padding: 0.5rem; font-family: monospace;">${job.job_id.substring(0, 8)}...</td>
                <td style="padding: 0.5rem;"><span class="badge">${job.trigger_source}</span></td>
                <td style="padding: 0.5rem;"><span style="color: ${statusColor}; font-weight: 600;">${job.status}</span></td>
                <td style="padding: 0.5rem;">${duration}</td>
                <td style="padding: 0.5rem; color: var(--text-muted);">${summary}</td>
              </tr>`;
            })
            .join("");
        }
      }

      // 6. Update Real-Time Live Feed
      const feedContainer = document.getElementById("liveStepFeed");
      if (feedContainer) {
        if (!data.latest_steps || data.latest_steps.length === 0) {
          feedContainer.innerHTML = `<div style="padding: 0.75rem; text-align: center; color: var(--text-muted);">No agent steps recorded recently.</div>`;
        } else {
          feedContainer.innerHTML = data.latest_steps
            .map((step) => {
              const statusBadge =
                step.status === "success"
                  ? `<span style="color: #10b981;">✓</span>`
                  : `<span style="color: #ef4444;">✗</span>`;

              return `<div style="padding: 0.75rem; border-radius: 8px; background: var(--bg-secondary, #f9fafb); border: 1px solid var(--border-color, #e5e7eb); font-size: 0.85rem;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.25rem;">
                  <strong>${step.agent_name} ${statusBadge}</strong>
                  <small style="color: var(--text-muted);">${step.created_at} (${step.execution_time_ms}ms)</small>
                </div>
                <div style="color: var(--text-muted); font-size: 0.8rem;">${step.summary}</div>
              </div>`;
            })
            .join("");
        }
      }
    } catch (err) {
      console.error("Failed to fetch dashboard stats:", err);
    }
  }

  initCharts();
  fetchDashboardStats();

  // Poll every 5 seconds for live real-time monitoring updates
  setInterval(fetchDashboardStats, 5000);

  document.getElementById("refreshDashboardBtn")?.addEventListener("click", fetchDashboardStats);
});
