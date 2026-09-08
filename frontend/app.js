/**
 * RetailIQ - Frontend Dashboard Application
 * Connects to FastAPI backend APIs and renders deterministic retail analytics
 */

const API_BASE = ""; // Relative path to FastAPI backend

// State
let currentStore = "";
let currentTimeframe = 30;

document.addEventListener("DOMContentLoaded", () => {
  initEventListeners();
  loadAllDashboardData();
});

function initEventListeners() {
  const storeSelect = document.getElementById("store-select");
  const timeframeSelect = document.getElementById("timeframe-select");

  // Store filter
  if (storeSelect) {
    storeSelect.addEventListener("change", (e) => {
      currentStore = e.target.value;
      loadAllDashboardData();
    });
  }

  // Timeframe filter
  if (timeframeSelect) {
    timeframeSelect.addEventListener("change", (e) => {
      currentTimeframe = parseInt(e.target.value, 10);
      loadAllDashboardData();
    });
  }

  // Copilot input
  const copilotInput = document.getElementById("copilot-input");

  if (copilotInput) {
    copilotInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        e.preventDefault();
        handleCopilotSubmit();
      }
    });
  }

  // ---------------------------------------------------------
  // Suggested Copilot Question Buttons
  // ---------------------------------------------------------
  const promptChips = document.querySelectorAll(".prompt-chips .chip");

  promptChips.forEach((chip) => {
    chip.addEventListener("click", () => {
      const promptText = chip.dataset.prompt;

      if (promptText) {
        selectPrompt(promptText);
      }
    });
  });

  // ---------------------------------------------------------
  // Delegated click listener for Evidence buttons
  // ---------------------------------------------------------
  document.addEventListener("click", (e) => {
    const btn = e.target.closest(".btn-inspect");

    if (btn) {
      e.preventDefault();

      const pid = btn.getAttribute("data-product-id");
      const sid = btn.getAttribute("data-store-id");

      if (pid) {
        inspectProduct(pid, sid);
      }
    }
  });
}

// ============================================================
// Dashboard Data Loading
// ============================================================

async function loadAllDashboardData() {
  updateSystemStatus("Connecting to APIs...", false);

  try {
    await Promise.all([
      loadKPIs(),
      loadAttentionCenter(),
      loadStoresTable(),
      loadProductsTable(),
      loadInventoryTable()
    ]);

    updateSystemStatus("Live & Connected", true);
  } catch (err) {
    console.error("Error loading dashboard data:", err);
    updateSystemStatus("Backend Error", false);
  }
}

// ============================================================
// System Status
// ============================================================

function updateSystemStatus(text, isHealthy) {
  const statusEl = document.getElementById("system-status-text");
  const dotEl = document.querySelector(".status-dot");

  if (statusEl) {
    statusEl.textContent = text;
  }

  if (dotEl) {
    dotEl.style.backgroundColor = isHealthy ? "#3fb950" : "#f85149";
    dotEl.style.boxShadow = isHealthy
      ? "0 0 6px #3fb950"
      : "0 0 6px #f85149";
  }
}

// ============================================================
// 1. Executive KPIs
// ============================================================

async function loadKPIs() {
  const url =
    `${API_BASE}/api/kpis?days=${currentTimeframe}` +
    `${currentStore ? `&store_id=${currentStore}` : ""}`;

  const res = await fetch(url);

  if (!res.ok) {
    throw new Error("Failed to load KPIs");
  }

  const data = await res.json();

  const revenueEl = document.getElementById("kpi-revenue");
  const unitsEl = document.getElementById("kpi-units");
  const ordersEl = document.getElementById("kpi-orders");
  const aovEl = document.getElementById("kpi-aov");
  const timeframeEl = document.getElementById("kpi-timeframe");

  if (revenueEl) {
    revenueEl.textContent =
      `$${Number(data.total_revenue).toLocaleString(undefined, {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
      })}`;
  }

  if (unitsEl) {
    unitsEl.textContent =
      `${Number(data.total_units_sold).toLocaleString()} units`;
  }

  if (ordersEl) {
    ordersEl.textContent =
      `${Number(data.total_transactions).toLocaleString()}`;
  }

  if (aovEl) {
    aovEl.textContent =
      `$${Number(data.average_order_value).toFixed(2)}`;
  }

  if (timeframeEl) {
    timeframeEl.textContent =
      `Window: ${data.start_date} to ${data.end_date}`;
  }
}

// ============================================================
// 2. Today's Attention Center
// ============================================================

async function loadAttentionCenter() {
  const url =
    `${API_BASE}/api/attention` +
    `${currentStore ? `?store_id=${currentStore}` : ""}`;

  const res = await fetch(url);

  if (!res.ok) {
    throw new Error("Failed to load attention data");
  }

  const data = await res.json();

  const attentionCounter =
    document.getElementById("attention-counter");

  if (attentionCounter) {
    attentionCounter.textContent =
      `${data.total_attention_count} Active Alerts`;
  }

  // ----------------------------------------------------------
  // A. Stockout Risks
  // ----------------------------------------------------------

  const stockoutList =
    document.getElementById("stockout-list");

  const stockouts = data.critical_stockouts || [];

  const stockoutCount =
    document.getElementById("stockout-count");

  if (stockoutCount) {
    stockoutCount.textContent =
      `${stockouts.length} items`;
  }

  if (stockoutList) {
    if (stockouts.length === 0) {
      stockoutList.innerHTML =
        '<div class="placeholder-text">No immediate stockout risks detected.</div>';
    } else {
      stockoutList.innerHTML = stockouts
        .slice(0, 4)
        .map(
          (item) => `
            <div
              class="attention-item-card"
              data-product-id="${escapeHtml(item.product_id)}"
              style="cursor: pointer;"
            >
              <div class="attention-item-info">
                <span class="attention-item-name">
                  ${escapeHtml(item.product_name)}
                </span>

                <span class="attention-item-sub">
                  ${escapeHtml(item.store_name)}
                  &bull;
                  Stock: ${escapeHtml(String(item.current_stock))}
                </span>
              </div>

              <span class="attention-item-pill pill-danger">
                ${
                  item.current_stock === 0
                    ? "OUT OF STOCK"
                    : `${item.days_until_stockout}d left`
                }
              </span>
            </div>
          `
        )
        .join("");

      stockoutList
        .querySelectorAll(".attention-item-card")
        .forEach((card) => {
          card.addEventListener("click", () => {
            const productId =
              card.getAttribute("data-product-id");

            if (productId) {
              inspectProduct(productId);
            }
          });
        });
    }
  }

  // ----------------------------------------------------------
  // B. Overstocked
  // ----------------------------------------------------------

  const overstockList =
    document.getElementById("overstock-list");

  const overstocks = data.overstocked_items || [];

  const overstockCount =
    document.getElementById("overstock-count");

  if (overstockCount) {
    overstockCount.textContent =
      `${overstocks.length} items`;
  }

  if (overstockList) {
    if (overstocks.length === 0) {
      overstockList.innerHTML =
        '<div class="placeholder-text">No overstocked inventory.</div>';
    } else {
      overstockList.innerHTML = overstocks
        .slice(0, 4)
        .map(
          (item) => `
            <div
              class="attention-item-card"
              data-product-id="${escapeHtml(item.product_id)}"
              style="cursor: pointer;"
            >
              <div class="attention-item-info">
                <span class="attention-item-name">
                  ${escapeHtml(item.product_name)}
                </span>

                <span class="attention-item-sub">
                  ${escapeHtml(item.store_name)}
                  &bull;
                  Target: ${escapeHtml(String(item.target_stock))}
                </span>
              </div>

              <span class="attention-item-pill pill-warning">
                ${
                  item.days_until_stockout
                    ? `${item.days_until_stockout}d coverage`
                    : `${item.current_stock} units`
                }
              </span>
            </div>
          `
        )
        .join("");

      overstockList
        .querySelectorAll(".attention-item-card")
        .forEach((card) => {
          card.addEventListener("click", () => {
            const productId =
              card.getAttribute("data-product-id");

            if (productId) {
              inspectProduct(productId);
            }
          });
        });
    }
  }

  // ----------------------------------------------------------
  // C. Demand Shifts
  // ----------------------------------------------------------

  const shiftsList =
    document.getElementById("shifts-list");

  const spikes = data.sales_spikes || [];
  const drops = data.sales_drops || [];

  const combinedShifts = [
    ...spikes.slice(0, 2),
    ...drops.slice(0, 2)
  ];

  const shiftsCount =
    document.getElementById("shifts-count");

  if (shiftsCount) {
    shiftsCount.textContent =
      `${spikes.length + drops.length} shifts`;
  }

  if (shiftsList) {
    if (combinedShifts.length === 0) {
      shiftsList.innerHTML =
        '<div class="placeholder-text">No major demand shifts detected.</div>';
    } else {
      shiftsList.innerHTML = combinedShifts
        .map(
          (item) => `
            <div
              class="attention-item-card"
              data-product-id="${escapeHtml(item.product_id)}"
              style="cursor: pointer;"
            >
              <div class="attention-item-info">
                <span class="attention-item-name">
                  ${escapeHtml(item.product_name)}
                </span>

                <span class="attention-item-sub">
                  14d Rev: $${escapeHtml(String(item.recent_revenue))}
                  vs prior $${escapeHtml(String(item.prior_revenue))}
                </span>
              </div>

              <span
                class="attention-item-pill ${
                  item.trend === "SPIKE"
                    ? "pill-success"
                    : "pill-danger"
                }"
              >
                ${
                  item.growth_percentage >= 0
                    ? `+${item.growth_percentage}%`
                    : `${item.growth_percentage}%`
                }
              </span>
            </div>
          `
        )
        .join("");

      shiftsList
        .querySelectorAll(".attention-item-card")
        .forEach((card) => {
          card.addEventListener("click", () => {
            const productId =
              card.getAttribute("data-product-id");

            if (productId) {
              inspectProduct(productId);
            }
          });
        });
    }
  }
}

// ============================================================
// 3. Store Performance Table
// ============================================================

async function loadStoresTable() {
  const url =
    `${API_BASE}/api/stores?days=${currentTimeframe}`;

  const res = await fetch(url);

  if (!res.ok) {
    throw new Error("Failed to load stores");
  }

  const data = await res.json();

  const tbody =
    document.getElementById("stores-table-body");

  const stores = data.stores || [];

  if (!tbody) return;

  if (stores.length === 0) {
    tbody.innerHTML =
      '<tr><td colspan="5" class="placeholder-text">No store data available.</td></tr>';
    return;
  }

  tbody.innerHTML = stores
    .map(
      (store) => `
        <tr>
          <td>
            <strong>#${escapeHtml(String(store.rank))}</strong>
          </td>

          <td>
            <strong>${escapeHtml(store.store_name)}</strong>
          </td>

          <td>
            ${escapeHtml(store.city)}, ${escapeHtml(store.state)}
          </td>

          <td>
            ${Number(store.total_units).toLocaleString()}
          </td>

          <td>
            <strong>
              $${Number(store.total_revenue).toLocaleString(undefined, {
                minimumFractionDigits: 2,
                maximumFractionDigits: 2
              })}
            </strong>
          </td>
        </tr>
      `
    )
    .join("");
}

// ============================================================
// 4. Products Table
// ============================================================

async function loadProductsTable() {
  const url =
    `${API_BASE}/api/products?days=${currentTimeframe}&limit=10` +
    `${currentStore ? `&store_id=${currentStore}` : ""}`;

  const res = await fetch(url);

  if (!res.ok) {
    throw new Error("Failed to load products");
  }

  const data = await res.json();

  const tbody =
    document.getElementById("products-table-body");

  const products = data.products || [];

  if (!tbody) return;

  if (products.length === 0) {
    tbody.innerHTML =
      '<tr><td colspan="5" class="placeholder-text">No product data available.</td></tr>';
    return;
  }

  tbody.innerHTML = products
    .map(
      (prod) => `
        <tr
          class="product-row"
          data-product-id="${escapeHtml(prod.product_id)}"
          style="cursor: pointer;"
          title="Click to view mathematical proof"
        >
          <td>
            <strong>${escapeHtml(prod.product_name)}</strong>
          </td>

          <td>
            ${escapeHtml(prod.category)}
          </td>

          <td>
            ${Number(prod.total_units).toLocaleString()}
          </td>

          <td>
            ${escapeHtml(String(prod.daily_avg_sales))} / day
          </td>

          <td>
            <strong>
              $${Number(prod.total_revenue).toLocaleString(undefined, {
                minimumFractionDigits: 2,
                maximumFractionDigits: 2
              })}
            </strong>
          </td>
        </tr>
      `
    )
    .join("");

  // Product row click
  tbody.querySelectorAll(".product-row").forEach((row) => {
    row.addEventListener("click", () => {
      const productId =
        row.getAttribute("data-product-id");

      if (productId) {
        inspectProduct(productId);
      }
    });
  });
}

// ============================================================
// 5. Inventory Health Table
// ============================================================

async function loadInventoryTable() {
  const url =
    `${API_BASE}/api/inventory/health?days=${currentTimeframe}` +
    `${currentStore ? `&store_id=${currentStore}` : ""}`;

  const res = await fetch(url);

  if (!res.ok) {
    throw new Error("Failed to load inventory");
  }

  const data = await res.json();

  const tbody =
    document.getElementById("inventory-table-body");

  const records = data.inventory || [];

  if (!tbody) return;

  if (records.length === 0) {
    tbody.innerHTML =
      '<tr><td colspan="7" class="placeholder-text">No inventory records found.</td></tr>';
    return;
  }

  // Render top 12 items
  tbody.innerHTML = records
    .slice(0, 12)
    .map((item) => {
      let badgeClass = "badge-healthy";

      if (item.health_status === "OUT_OF_STOCK") {
        badgeClass = "badge-out-of-stock";
      } else if (
        item.health_status === "IMMINENT_STOCKOUT_RISK"
      ) {
        badgeClass = "badge-critical";
      } else if (item.health_status === "LOW_STOCK") {
        badgeClass = "badge-low";
      } else if (item.health_status === "OVERSTOCKED") {
        badgeClass = "badge-overstocked";
      }

      return `
        <tr>
          <td>
            ${escapeHtml(item.store_name)}
          </td>

          <td>
            <strong>
              ${escapeHtml(item.product_name)}
            </strong>
          </td>

          <td>
            <strong>
              ${escapeHtml(String(item.current_stock))}
            </strong>
          </td>

          <td>
            ${escapeHtml(String(item.average_daily_demand))} / day
          </td>

          <td>
            ${
              item.days_until_stockout !== null
                ? `${escapeHtml(String(item.days_until_stockout))} days`
                : "N/A"
            }
          </td>

          <td>
            <span class="badge-status ${badgeClass}">
              ${escapeHtml(
                String(item.health_status).replace(/_/g, " ")
              )}
            </span>
          </td>

          <td>
            <button
              class="btn-inspect"
              data-product-id="${escapeHtml(item.product_id)}"
              data-store-id="${escapeHtml(item.store_id)}"
            >
              Evidence
            </button>
          </td>
        </tr>
      `;
    })
    .join("");
}

// ============================================================
// 6. Inspect Product Evidence
// ============================================================

async function inspectProduct(productId, storeId = null) {
  try {
    const targetStore = storeId || currentStore;

    const url =
      `${API_BASE}/api/product/${productId}` +
      `${targetStore ? `?store_id=${targetStore}` : ""}`;

    const res = await fetch(url);

    if (!res.ok) {
      console.warn(
        "Could not fetch product evidence:",
        productId,
        res.status
      );
      return;
    }

    const data = await res.json();

    const evProduct =
      document.getElementById("ev-product");

    const evStock =
      document.getElementById("ev-stock");

    const evVelocity =
      document.getElementById("ev-velocity");

    const evCalculation =
      document.getElementById("ev-calculation");

    const evAssumption =
      document.getElementById("ev-assumption");

    const evRecommendation =
      document.getElementById("ev-recommendation");

    if (evProduct) {
      evProduct.textContent =
        `${data.product_name} (${data.product_id}) - ${data.category}`;
    }

    if (evStock) {
      evStock.textContent =
        `${data.metrics_30d.current_stock} units (${data.store_filtered})`;
    }

    if (evVelocity) {
      evVelocity.textContent =
        `${data.metrics_30d.daily_average_sales} units/day (30d average)`;
    }

    if (evCalculation) {
      evCalculation.textContent =
        data.evidence.calculation;
    }

    if (evAssumption) {
      evAssumption.textContent =
        data.evidence.assumption;
    }

    if (evRecommendation) {
      evRecommendation.textContent =
        data.metrics_30d.human_coverage;
    }

    // Smoothly scroll to Evidence Inspector
    const evidencePanel =
      document.querySelector(".evidence-panel");

    if (evidencePanel) {
      evidencePanel.scrollIntoView({
        behavior: "smooth",
        block: "nearest"
      });

      evidencePanel.style.transition =
        "box-shadow 0.3s ease, border-color 0.3s ease";

      evidencePanel.style.boxShadow =
        "0 0 20px rgba(56, 139, 253, 0.6)";

      evidencePanel.style.borderColor =
        "var(--primary)";

      setTimeout(() => {
        evidencePanel.style.boxShadow = "";
        evidencePanel.style.borderColor = "";
      }, 1200);
    }
  } catch (err) {
    console.error(
      "Error inspecting product evidence:",
      err
    );
  }
}

// ============================================================
// 7. AI Copilot - Suggested Questions
// ============================================================

function selectPrompt(promptText) {
  const input =
    document.getElementById("copilot-input");

  const submit =
    document.getElementById("copilot-submit");

  if (!input) {
    console.warn("Copilot input not found");
    return;
  }

  if (submit && submit.disabled) {
    return;
  }

  input.value = promptText;

  handleCopilotSubmit();
}

// ============================================================
// 8. AI Copilot - Submit
// ============================================================

async function handleCopilotSubmit() {
  const submit =
    document.getElementById("copilot-submit");

  if (submit && submit.disabled) {
    return;
  }

  const input =
    document.getElementById("copilot-input");

  const query =
    input ? input.value.trim() : "";

  if (!query) {
    return;
  }

  const chatMessages =
    document.getElementById("chat-messages");

  if (!chatMessages) {
    console.error("Chat messages container not found");
    return;
  }

  // ----------------------------------------------------------
  // User message
  // ----------------------------------------------------------

  const userDiv =
    document.createElement("div");

  userDiv.className = "chat-msg user";

  userDiv.innerHTML = `
    <div class="msg-author">
      Store Manager
    </div>

    <div class="msg-bubble">
      ${escapeHtml(query)}
    </div>
  `;

  chatMessages.appendChild(userDiv);

  if (input) {
    input.value = "";
  }

  if (submit) {
    submit.disabled = true;
    submit.textContent = "Thinking...";
  }

  // ----------------------------------------------------------
  // Loading message
  // ----------------------------------------------------------

  const loadingDiv =
    document.createElement("div");

  loadingDiv.className =
    "chat-msg assistant";

  loadingDiv.innerHTML = `
    <div class="msg-author">
      RetailIQ Copilot
    </div>

    <div class="msg-bubble">
      Analyzing verified sales and inventory evidence...
    </div>
  `;

  chatMessages.appendChild(loadingDiv);

  chatMessages.scrollTop =
    chatMessages.scrollHeight;

  // ----------------------------------------------------------
  // Backend request
  // ----------------------------------------------------------

  try {
    const res = await fetch(
      `${API_BASE}/api/copilot`,
      {
        method: "POST",

        headers: {
          "Content-Type": "application/json"
        },

        body: JSON.stringify({
          query,
          store_id: currentStore || null,
          days: currentTimeframe
        })
      }
    );

    const data = await res.json();

    if (!res.ok) {
      throw new Error(
        data.detail || "Copilot request failed"
      );
    }

    // Remove loading message
    loadingDiv.remove();

    // --------------------------------------------------------
    // Copilot response
    // --------------------------------------------------------

    const botDiv =
      document.createElement("div");

    botDiv.className =
      "chat-msg assistant";

    // Evidence
    const evidence =
      (data.evidence || []).slice(0, 4);

    const evidenceHtml =
      evidence.length
        ? `
          <div class="copilot-evidence">
            <strong>Evidence used</strong>

            ${evidence
              .map(
                (e) => `
                  <div class="evidence-mini">
                    [${escapeHtml(e.id || "source")}]
                    ${escapeHtml(e.text || "")}
                  </div>
                `
              )
              .join("")}
          </div>
        `
        : "";

    // Assumptions
    const assumptions =
      (data.assumptions || [])
        .map(
          (a) =>
            `<li>${escapeHtml(a)}</li>`
        )
        .join("");

    botDiv.innerHTML = `
      <div class="msg-author">
        RetailIQ Copilot

        <span class="copilot-source">
          ${escapeHtml(
            data.source || "grounded"
          )}
        </span>
      </div>

      <div class="msg-bubble">

        <div>
          ${escapeHtml(
            data.answer ||
              "I don't have enough data to answer that reliably."
          )}
        </div>

        ${evidenceHtml}

        ${
          assumptions
            ? `
              <div class="copilot-assumptions">
                <strong>Assumptions</strong>

                <ul>
                  ${assumptions}
                </ul>
              </div>
            `
            : ""
        }

      </div>
    `;

    chatMessages.appendChild(botDiv);

    // --------------------------------------------------------
    // Open deterministic product evidence
    // --------------------------------------------------------

    const firstProduct =
      evidence.find(
        (e) =>
          e.metadata &&
          e.metadata.product_id
      );

    if (
      firstProduct &&
      firstProduct.metadata.product_id
    ) {
      inspectProduct(
        firstProduct.metadata.product_id,
        firstProduct.metadata.store_id || null
      );
    }
  } catch (err) {
    // Remove loading message
    loadingDiv.remove();

    // --------------------------------------------------------
    // Error message
    // --------------------------------------------------------

    const botDiv =
      document.createElement("div");

    botDiv.className =
      "chat-msg assistant";

    botDiv.innerHTML = `
      <div class="msg-author">
        RetailIQ Copilot
      </div>

      <div class="msg-bubble">
        I couldn't complete that request right now.
        Deterministic dashboard analytics are still available.

        <small>
          ${escapeHtml(err.message)}
        </small>
      </div>
    `;

    chatMessages.appendChild(botDiv);

    console.error(
      "Copilot request error:",
      err
    );
  } finally {
    // --------------------------------------------------------
    // Restore Ask Copilot button
    // --------------------------------------------------------

    if (submit) {
      submit.disabled = false;
      submit.textContent = "Ask Copilot";
    }

    chatMessages.scrollTop =
      chatMessages.scrollHeight;
  }
}

// ============================================================
// 9. HTML Escape Helper
// ============================================================

function escapeHtml(value) {
  if (value === null || value === undefined) {
    return "";
  }

  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

// ============================================================
// Global exports
// Keep these for compatibility with any remaining
// inline handlers elsewhere in index.html
// ============================================================

window.selectPrompt =
  selectPrompt;

window.handleCopilotSubmit =
  handleCopilotSubmit;

window.inspectProduct =
  inspectProduct;
