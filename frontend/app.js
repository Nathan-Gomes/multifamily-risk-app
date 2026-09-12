const state = {
  dashboard: null,
  selectedPropertyId: null,
};

let controlFetchTimer = null;
let activeRequest = null;

const presets = {
  base: {
    label: "Base case",
    occupancy_shock: 0,
    expense_shock: 0,
    rate_shock_bps: 0,
    cap_rate_shock_bps: 0,
  },
  softness: {
    label: "Occupancy softness",
    occupancy_shock: -6,
    expense_shock: 3,
    rate_shock_bps: 0,
    cap_rate_shock_bps: 25,
  },
  refinance: {
    label: "Refinance shock",
    occupancy_shock: 0,
    expense_shock: 0,
    rate_shock_bps: 250,
    cap_rate_shock_bps: 50,
  },
  downside: {
    label: "Combined downside",
    occupancy_shock: -8,
    expense_shock: 12,
    rate_shock_bps: 250,
    cap_rate_shock_bps: 100,
  },
};

const money = (value) => {
  const number = Number(value || 0);
  if (Math.abs(number) >= 1_000_000) return `$${(number / 1_000_000).toFixed(1)}M`;
  return `$${(number / 1_000).toFixed(0)}k`;
};

const percent = (value, digits = 1) => `${(Number(value || 0) * 100).toFixed(digits)}%`;
const number = (value, digits = 1) => Number(value || 0).toFixed(digits);

function riskClass(band) {
  return `band band-${String(band || "").toLowerCase()}`;
}

function readControls() {
  const form = new FormData(document.querySelector("#controls"));
  return {
    occupancy_shock: Number(form.get("occupancy_shock")) / 100,
    expense_shock: Number(form.get("expense_shock")) / 100,
    rate_shock_bps: Number(form.get("rate_shock_bps")),
    cap_rate_shock_bps: Number(form.get("cap_rate_shock_bps")),
    capital_budget: Number(form.get("capital_budget")),
  };
}

function updateControlLabels() {
  const values = readControls();
  document.querySelector('[data-output="occupancy_shock"]').textContent = percent(values.occupancy_shock, 0);
  document.querySelector('[data-output="expense_shock"]').textContent = percent(values.expense_shock, 0);
  document.querySelector('[data-output="rate_shock_bps"]').textContent = `${values.rate_shock_bps} bps`;
  document.querySelector('[data-output="cap_rate_shock_bps"]').textContent = `${values.cap_rate_shock_bps} bps`;
  document.querySelector('[data-output="capital_budget"]').textContent = money(values.capital_budget);
  document.querySelector("#scenarioBadge").textContent = scenarioLabel(values);
  updatePresetButtons();
}

function scheduleDashboardFetch() {
  window.clearTimeout(controlFetchTimer);
  controlFetchTimer = window.setTimeout(() => {
    fetchDashboard().catch(handleDashboardError);
  }, 250);
}

async function fetchDashboard() {
  updateControlLabels();
  if (activeRequest) activeRequest.abort();
  activeRequest = new AbortController();
  const params = new URLSearchParams(readControls());
  const response = await fetch(`/api/dashboard?${params}`, { signal: activeRequest.signal });
  if (!response.ok) throw new Error("Dashboard request failed");
  state.dashboard = await response.json();
  if (!state.selectedPropertyId) {
    state.selectedPropertyId = state.dashboard.properties[0]?.property_id;
  }
  renderDashboard();
  renderPropertyDetail(state.selectedPropertyId);
}

function scenarioLabel(values) {
  const matchedPreset = Object.entries(presets).find(([, preset]) => (
    Number(preset.occupancy_shock) / 100 === values.occupancy_shock
    && Number(preset.expense_shock) / 100 === values.expense_shock
    && Number(preset.rate_shock_bps) === values.rate_shock_bps
    && Number(preset.cap_rate_shock_bps) === values.cap_rate_shock_bps
  ));
  return matchedPreset ? matchedPreset[1].label : "Custom scenario";
}

function updatePresetButtons() {
  const values = readControls();
  document.querySelectorAll("[data-preset]").forEach((button) => {
    const preset = presets[button.dataset.preset];
    const active = (
      Number(preset.occupancy_shock) / 100 === values.occupancy_shock
      && Number(preset.expense_shock) / 100 === values.expense_shock
      && Number(preset.rate_shock_bps) === values.rate_shock_bps
      && Number(preset.cap_rate_shock_bps) === values.cap_rate_shock_bps
    );
    button.classList.toggle("active", active);
  });
}

function applyPreset(name) {
  const preset = presets[name];
  if (!preset) return;
  Object.entries(preset).forEach(([key, value]) => {
    const input = document.querySelector(`[name="${key}"]`);
    if (input) input.value = value;
  });
  fetchDashboard().catch(handleDashboardError);
}

function metric(label, value, note) {
  return `<div class="metric-card"><span>${label}</span><strong>${value}</strong><small>${note}</small></div>`;
}

function renderMetrics(summary) {
  document.querySelector("#overview").innerHTML = [
    metric("Portfolio value", money(summary.portfolio_value), `${percent(summary.scenario_value_change_pct)} from base`),
    metric("Properties", summary.property_count, `${summary.unit_count.toLocaleString()} total units`),
    metric("Annual NOI", money(summary.annual_noi), `${percent(summary.scenario_noi_change_pct)} from base`),
    metric("Weighted DSCR", `${number(summary.weighted_dscr, 2)}x`, `${summary.elevated_or_high} elevated or high`),
    metric("CMHC-insured debt", percent(summary.cmhc_debt_share), money(summary.cmhc_debt)),
    metric("Selected capital", money(summary.selected_capital), `${summary.selected_projects} projects`)
  ].join("");
}

function renderRiskMatrix(properties) {
  const width = 900;
  const height = 500;
  const maxValue = Math.max(...properties.map((item) => item.property_value));
  const circles = properties.map((item) => {
    const x = 72 + Math.max(0, Math.min(1, (item.ltv - 0.45) / 0.40)) * 760;
    const y = 420 - Math.max(0, Math.min(1, (item.dscr - 0.80) / 1.10)) * 340;
    const radius = Math.max(7, Math.min(22, item.property_value / maxValue * 24));
    const color = {
      Low: "#8aa79d",
      Moderate: "#26715c",
      Elevated: "#b27a2d",
      High: "#a23a2c"
    }[item.risk_band] || "#26715c";
    return `<circle tabindex="0" role="button" data-property="${item.property_id}" cx="${x}" cy="${y}" r="${radius}" fill="${color}" opacity="0.86">
      <title>${item.property_name}: DSCR ${number(item.dscr, 2)}x, LTV ${percent(item.ltv)}, risk ${number(item.risk_score, 1)}</title>
    </circle>`;
  }).join("");

  document.querySelector("#riskMatrix").innerHTML = `
    <svg viewBox="0 0 ${width} ${height}" role="img" aria-label="Property risk matrix">
      <rect width="${width}" height="${height}" fill="#fbfcfb"></rect>
      <line x1="70" y1="420" x2="840" y2="420" stroke="#dfe4e1"></line>
      <line x1="70" y1="80" x2="70" y2="420" stroke="#dfe4e1"></line>
      <line x1="70" y1="327" x2="840" y2="327" stroke="#a23a2c" stroke-dasharray="5 6" opacity="0.55"></line>
      <line x1="358" y1="80" x2="358" y2="420" stroke="#a23a2c" stroke-dasharray="5 6" opacity="0.55"></line>
      <text x="455" y="468" text-anchor="middle" fill="#6d7479" font-size="17">Loan to value</text>
      <text x="24" y="250" text-anchor="middle" transform="rotate(-90 24 250)" fill="#6d7479" font-size="17">DSCR</text>
      <text x="70" y="448" text-anchor="middle" fill="#6d7479" font-size="13">45%</text>
      <text x="358" y="448" text-anchor="middle" fill="#6d7479" font-size="13">60%</text>
      <text x="840" y="448" text-anchor="middle" fill="#6d7479" font-size="13">85%</text>
      <text x="45" y="425" text-anchor="end" fill="#6d7479" font-size="13">0.8x</text>
      <text x="45" y="332" text-anchor="end" fill="#6d7479" font-size="13">1.1x</text>
      <text x="45" y="84" text-anchor="end" fill="#6d7479" font-size="13">1.9x</text>
      ${circles}
    </svg>
  `;

  document.querySelectorAll("#riskMatrix circle[data-property]").forEach((circle) => {
    circle.addEventListener("click", () => {
      state.selectedPropertyId = circle.dataset.property;
      document.querySelector("#propertySelect").value = state.selectedPropertyId;
      renderPropertyDetail(state.selectedPropertyId);
      document.querySelector("#properties").scrollIntoView({ behavior: "smooth", block: "start" });
    });
  });
}

function table(headers, rows) {
  return `
    <table>
      <thead><tr>${headers.map((header) => `<th>${header}</th>`).join("")}</tr></thead>
      <tbody>${rows.join("")}</tbody>
    </table>
  `;
}

function renderTopRisk(rows) {
  document.querySelector("#topRiskTable").innerHTML = table(
    ["Property", "Financing", "Risk", "DSCR", "LTV", "NOI YoY"],
    rows.map((item) => `
      <tr>
        <td>${item.property_name}<br><span class="${riskClass(item.risk_band)}">${item.risk_band}</span></td>
        <td>${item.loan_type}<br><small>${item.rate_type}</small></td>
        <td>${number(item.risk_score, 1)}</td>
        <td>${number(item.dscr, 2)}x</td>
        <td>${percent(item.ltv)}</td>
        <td class="${item.noi_yoy < 0 ? "negative" : "positive"}">${percent(item.noi_yoy)}</td>
      </tr>
    `)
  );
}

function renderCustomScenario(scenario) {
  document.querySelector("#customScenario").innerHTML = [
    ["Portfolio value", money(scenario.portfolio_value), percent(scenario.value_change_pct)],
    ["Annual NOI", money(scenario.annual_noi), percent(scenario.noi_change_pct)],
    ["DSCR under 1.10x", scenario.properties_below_1_10_dscr, "properties"],
    ["Highest watchlist", scenario.highest_risk[0]?.property_name || "None", scenario.highest_risk[0]?.risk_band || ""]
  ].map(([label, value, note]) => `
    <div class="scenario-card">
      <span>${label}</span>
      <strong>${value}</strong>
      <small>${note}</small>
    </div>
  `).join("");
}

function renderBars(selector, rows, labelKey, valueKey, formatter, limit = 8) {
  const slice = rows.slice(0, limit);
  const maxAbs = Math.max(...slice.map((item) => Math.abs(Number(item[valueKey] || 0))), 0.01);
  document.querySelector(selector).innerHTML = slice.map((item) => {
    const raw = Number(item[valueKey] || 0);
    const width = Math.max(2, Math.abs(raw) / maxAbs * 100);
    const negative = raw < 0;
    return `
      <div class="bar-row">
        <span>${item[labelKey]}</span>
        <div class="bar-track"><i class="bar-fill ${negative ? "negative" : ""}" style="width:${width}%"></i></div>
        <strong class="${negative ? "negative" : ""}">${formatter(raw)}</strong>
      </div>
    `;
  }).join("");
}

function renderCapitalPlan(rows) {
  document.querySelector("#capitalTable").innerHTML = table(
    ["Rank", "Property", "Project", "Capital", "NOI lift", "Value lift", "Return"],
    rows.map((item, index) => `
      <tr>
        <td>${index + 1}</td>
        <td>${item.property_name}</td>
        <td>${item.project_type}</td>
        <td>${money(item.capital_required)}</td>
        <td>${money(item.expected_noi_lift)}</td>
        <td>${money(item.expected_value_lift)}</td>
        <td>${percent(item.expected_return_on_capital)}</td>
      </tr>
    `)
  );
}

function renderPropertySelect(properties) {
  const select = document.querySelector("#propertySelect");
  const current = select.value || state.selectedPropertyId;
  select.innerHTML = properties
    .slice()
    .sort((a, b) => a.property_name.localeCompare(b.property_name))
    .map((item) => `<option value="${item.property_id}">${item.property_name}</option>`)
    .join("");
  select.value = current && properties.some((item) => item.property_id === current) ? current : properties[0]?.property_id;
  state.selectedPropertyId = select.value;
}

function renderPropertyDetail(propertyId) {
  if (!propertyId) return;
  const target = document.querySelector("#propertyDetail");
  const metrics = state.dashboard?.properties.find((item) => item.property_id === propertyId);
  if (!metrics) {
    target.innerHTML = '<div class="loading">Property detail could not be loaded.</div>';
    return;
  }
  target.innerHTML = `
    <div class="detail-grid">
      <div class="detail-item"><span>Risk band</span><strong><span class="${riskClass(metrics.risk_band)}">${metrics.risk_band}</span></strong></div>
      <div class="detail-item"><span>Risk score</span><strong>${number(metrics.risk_score, 1)}</strong></div>
      <div class="detail-item"><span>DSCR</span><strong>${number(metrics.dscr, 2)}x</strong></div>
      <div class="detail-item"><span>LTV</span><strong>${percent(metrics.ltv)}</strong></div>
      <div class="detail-item"><span>Scenario revenue</span><strong>${money(metrics.revenue)}</strong></div>
      <div class="detail-item"><span>Scenario NOI</span><strong>${money(metrics.noi)}</strong></div>
      <div class="detail-item"><span>Loan type</span><strong>${metrics.loan_type}</strong></div>
      <div class="detail-item"><span>Rate and maturity</span><strong>${percent(metrics.interest_rate)} / ${metrics.maturity_year}</strong></div>
      <div class="detail-item"><span>Loan balance</span><strong>${money(metrics.loan_balance)}</strong></div>
      <div class="detail-item"><span>Amortization</span><strong>${metrics.amortization_years} years</strong></div>
    </div>
  `;
}

function renderDashboard() {
  const data = state.dashboard;
  renderMetrics(data.summary);
  renderRiskMatrix(data.properties);
  renderTopRisk(data.top_risk);
  renderCustomScenario(data.custom_scenario);
  renderBars("#scenarioBars", data.scenarios, "scenario", "value_change_pct", percent, 5);
  renderCapitalPlan(data.capital_plan);
  renderBars("#marketBars", data.concentration.market, "market", "exposure_pct", percent, 6);
  renderBars("#loanTypeBars", data.concentration.loan_type, "loan_type", "exposure_pct", percent, 6);
  renderPropertySelect(data.properties);
  const investment = data.investment;
  const history = investment.history;
  document.querySelector('#investmentMetrics').innerHTML = [
    metric('Aggregate DSCR', `${number(investment.aggregate_dscr, 2)}x`, 'Total NOI / total debt service'),
    metric('Refinance equity gap', money(investment.refinance_gap), 'Existing balance less modeled capacity'),
    metric('Unlevered DCF value', money(investment.dcf_value), 'Before recurring capital expenditure'),
    metric('Cash after debt', money(investment.cash_after_debt), 'Annualized, before capital expenditure'),
  ].join('');
  document.querySelector('#creditTable').innerHTML = table(
    ['Property', 'Debt yield', 'Break-even occupancy', 'Refinance gap', 'Binding limit'],
    investment.credit.slice(0, 8).map(item => `<tr><td>${item.property_name}</td><td>${percent(item.debt_yield)}</td><td>${percent(item.break_even_occupancy)}</td><td>${money(item.refinance_gap)}</td><td>${item.binding_constraint}</td></tr>`)
  );
  document.querySelector('#historicalMetrics').innerHTML = [
    metric('Monthly NOI volatility', percent(history.monthly_noi_volatility), `${history.observations} aligned observations`),
    metric('95% historical NOI VaR', percent(history.historical_noi_var_95), 'Monthly change loss quantile'),
    metric('95% expected shortfall', percent(history.historical_noi_es_95), 'Average tail NOI decline'),
    metric('Effective asset count', number(history.effective_assets), `Value HHI ${number(history.value_hhi, 3)}`),
  ].join('');
  renderBars('#riskContribution', history.attribution, 'property', 'variance_share', percent);
  document.querySelector('#historicalMethod').textContent = history.method + ' Contributions sum to 100%; negative contributions indicate diversification.';
}

document.querySelectorAll("#controls input").forEach((input) => {
  input.addEventListener("input", () => {
    updateControlLabels();
    scheduleDashboardFetch();
  });
  input.addEventListener("change", fetchDashboard);
});

function handleDashboardError(error) {
  if (error.name === "AbortError") return;
  document.querySelector(".page").insertAdjacentHTML(
    "afterbegin",
    `<div class="panel" style="border-color:#a23a2c;color:#a23a2c;margin-bottom:18px">Could not load dashboard data: ${error.message}</div>`
  );
}

document.querySelector("#refreshButton").addEventListener("click", () => {
  fetchDashboard().catch(handleDashboardError);
});
document.querySelectorAll("[data-preset]").forEach((button) => {
  button.addEventListener("click", () => applyPreset(button.dataset.preset));
});
document.querySelector("#propertySelect").addEventListener("change", (event) => {
  state.selectedPropertyId = event.target.value;
  renderPropertyDetail(state.selectedPropertyId);
});

fetchDashboard().catch(handleDashboardError);
