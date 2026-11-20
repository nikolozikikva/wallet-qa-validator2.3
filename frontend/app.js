/**
 * Wallet QA Validator - Frontend Logic
 * Ledger Dashboard & QA Test Console
 */

document.addEventListener("DOMContentLoaded", () => {
  // Application State
  const state = {
    users: [],
    selectedUserId: null,
    transactions: [],
    activeFilterType: "all",
    filterUserOnly: true,
    isLoadingTransactions: false,
  };

  // DOM Elements - Navigation & Global
  const accountSelect = document.getElementById("account-select");
  const userCountBadge = document.getElementById("user-count");
  const runAuditBtn = document.getElementById("run-audit-btn");
  const auditBadge = document.getElementById("audit-badge");
  const resetDbBtn = document.getElementById("reset-db-btn");

  // DOM Elements - Balance Readout
  const balanceAmountEl = document.getElementById("balance-amount");
  const balanceStatusTagEl = document.getElementById("balance-status-tag");
  const accountIdDisplayEl = document.getElementById("account-id-display");
  const accountUsernameDisplayEl = document.getElementById("account-username-display");

  // DOM Elements - Transaction Form
  const transactionForm = document.getElementById("transaction-form");
  const txnTypeSelect = document.getElementById("txn-type");
  const txnAmountInput = document.getElementById("txn-amount");
  const txnReferenceInput = document.getElementById("txn-reference");
  const generateRefBtn = document.getElementById("generate-ref-btn");
  const formAlertEl = document.getElementById("form-alert");
  const alertIconEl = document.getElementById("alert-icon");
  const alertMessageEl = document.getElementById("alert-message");
  const submitTxnBtn = document.getElementById("submit-txn-btn");

  // DOM Elements - Ledger Table & Controls
  const filterChips = document.querySelectorAll(".filter-chip");
  const filterUserOnlyCheckbox = document.getElementById("filter-current-user-only");
  const transactionsTbody = document.getElementById("transactions-tbody");
  const ledgerTotalCountEl = document.getElementById("ledger-total-count");
  const tableEmptyStateEl = document.getElementById("table-empty-state");
  const tableLoadingStateEl = document.getElementById("table-loading-state");

  // DOM Elements - Audit Modal
  const auditModal = document.getElementById("audit-modal");
  const auditModalContent = document.getElementById("audit-modal-content");
  const closeAuditModalBtn = document.getElementById("close-audit-modal-btn");

  // ===========================================================================
  // Utility Functions
  // ===========================================================================

  const formatCurrency = (val) => {
    const num = Number(val) || 0;
    return num.toLocaleString("en-US", {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    });
  };

  const generateReferenceId = () => {
    const randomHex = Math.random().toString(16).substring(2, 8).toUpperCase();
    return `TXN-REF-${Date.now().toString().slice(-4)}-${randomHex}`;
  };

  const showAlert = (message, isError = true) => {
    formAlertEl.className = isError ? "alert-box alert-error" : "alert-box alert-success";
    alertIconEl.textContent = isError ? "✕" : "✓";
    alertMessageEl.textContent = message;
    formAlertEl.style.display = "flex";
  };

  const hideAlert = () => {
    formAlertEl.style.display = "none";
    alertMessageEl.textContent = "";
  };

  // ===========================================================================
  // Data Fetching & Sync
  // ===========================================================================

  async function fetchUsers() {
    try {
      const res = await fetch("/api/users");
      if (!res.ok) throw new Error("Failed to load users");
      state.users = await res.json();
      renderUserSelect();

      // Check for anomalies count in background to show badge
      fetchAuditSummary();
    } catch (err) {
      showAlert(`Error loading accounts: ${err.message}`, true);
    }
  }

  function renderUserSelect() {
    accountSelect.innerHTML = "";
    userCountBadge.textContent = `${state.users.length} USERS`;

    state.users.forEach((u) => {
      const opt = document.createElement("option");
      opt.value = u.id;
      opt.textContent = `${u.username} (ID: ${u.id}) - $${formatCurrency(u.balance)}`;
      accountSelect.appendChild(opt);
    });

    if (state.users.length > 0) {
      if (!state.selectedUserId || !state.users.some((u) => u.id === state.selectedUserId)) {
        state.selectedUserId = state.users[0].id;
      }
      accountSelect.value = state.selectedUserId;
      updateActiveUserDisplay();
      fetchTransactions();
    }
  }

  function updateActiveUserDisplay() {
    const currentUser = state.users.find((u) => u.id === Number(state.selectedUserId));
    if (!currentUser) return;

    accountIdDisplayEl.textContent = `#${currentUser.id}`;
    accountUsernameDisplayEl.textContent = currentUser.username;
    balanceAmountEl.textContent = formatCurrency(currentUser.balance);

    if (currentUser.balance < 0) {
      balanceStatusTagEl.textContent = "OVERDRAFT / NEGATIVE";
      balanceStatusTagEl.className = "status-indicator status-negative";
    } else {
      balanceStatusTagEl.textContent = "ACTIVE";
      balanceStatusTagEl.className = "status-indicator status-normal";
    }
  }

  async function fetchTransactions() {
    state.isLoadingTransactions = true;
    tableLoadingStateEl.style.display = "flex";
    tableEmptyStateEl.style.display = "none";
    transactionsTbody.innerHTML = "";

    try {
      const params = new URLSearchParams();
      if (state.filterUserOnly && state.selectedUserId) {
        params.append("user_id", state.selectedUserId);
      }
      if (state.activeFilterType && state.activeFilterType !== "all") {
        params.append("type", state.activeFilterType);
      }

      const res = await fetch(`/api/transactions?${params.toString()}`);
      if (!res.ok) throw new Error("Failed to fetch transactions");
      state.transactions = await res.json();
      renderTransactionsTable();
    } catch (err) {
      console.error(err);
    } finally {
      state.isLoadingTransactions = false;
      tableLoadingStateEl.style.display = "none";
    }
  }

  function renderTransactionsTable() {
    transactionsTbody.innerHTML = "";
    ledgerTotalCountEl.textContent = `${state.transactions.length} RECORDS`;

    if (state.transactions.length === 0) {
      tableEmptyStateEl.style.display = "flex";
      return;
    }
    tableEmptyStateEl.style.display = "none";

    state.transactions.forEach((tx) => {
      const tr = document.createElement("tr");

      const isCredit = tx.type === "deposit" || tx.type === "win";
      const sign = isCredit ? "+" : "-";
      const amountClass = isCredit ? "td-amount td-credit" : "td-amount td-debit";
      const badgeClass = `type-badge badge-${tx.type}`;

      tr.innerHTML = `
        <td class="td-mono">#${tx.id}</td>
        <td><strong>${escapeHtml(tx.username)}</strong></td>
        <td><span class="${badgeClass}">${tx.type}</span></td>
        <td class="td-mono">${escapeHtml(tx.reference_id)}</td>
        <td class="${amountClass}">${sign}$${formatCurrency(tx.amount)}</td>
        <td style="text-align: center;"><span class="status-badge-completed">${tx.status}</span></td>
        <td class="td-mono" style="text-align: right;">${escapeHtml(tx.created_at)}</td>
      `;
      transactionsTbody.appendChild(tr);
    });
  }

  function escapeHtml(str) {
    if (!str) return "";
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  // ===========================================================================
  // Event Handlers
  // ===========================================================================

  accountSelect.addEventListener("change", (e) => {
    state.selectedUserId = Number(e.target.value);
    hideAlert();
    updateActiveUserDisplay();
    fetchTransactions();
  });

  generateRefBtn.addEventListener("click", () => {
    txnReferenceInput.value = generateReferenceId();
  });

  filterChips.forEach((chip) => {
    chip.addEventListener("click", () => {
      filterChips.forEach((c) => c.classList.remove("active"));
      chip.classList.add("active");
      state.activeFilterType = chip.dataset.type;
      fetchTransactions();
    });
  });

  filterUserOnlyCheckbox.addEventListener("change", (e) => {
    state.filterUserOnly = e.target.checked;
    fetchTransactions();
  });

  // Submit Transaction Form
  transactionForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    hideAlert();

    const userId = Number(state.selectedUserId);
    const type = txnTypeSelect.value;
    const amountVal = txnAmountInput.value.trim();
    const referenceId = txnReferenceInput.value.trim();

    // Client-side presence validation
    if (!amountVal) {
      showAlert("Please specify a numeric transaction amount.", true);
      txnAmountInput.focus();
      return;
    }

    if (!referenceId) {
      showAlert("Reference ID is required for ledger tracking.", true);
      txnReferenceInput.focus();
      return;
    }

    submitTxnBtn.disabled = true;
    submitTxnBtn.textContent = "Processing...";

    try {
      const payload = {
        user_id: userId,
        type: type,
        amount: parseFloat(amountVal),
        reference_id: referenceId,
      };

      const res = await fetch("/api/transaction", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      const data = await res.json();

      if (!res.ok) {
        // Display backend error message directly in inline alert box
        showAlert(data.error || "Transaction failed.", true);
        return;
      }

      // Success
      showAlert(`Transaction #${data.transaction.id} processed successfully. New balance: $${formatCurrency(data.new_balance)}`, false);

      // Refresh data
      txnAmountInput.value = "";
      txnReferenceInput.value = generateReferenceId();
      await fetchUsers();
      await fetchTransactions();
    } catch (err) {
      showAlert(`Network/Execution error: ${err.message}`, true);
    } finally {
      submitTxnBtn.disabled = false;
      submitTxnBtn.textContent = "POST /api/transaction";
    }
  });

  // Reset Database
  resetDbBtn.addEventListener("click", async () => {
    if (!confirm("Are you sure you want to reset the database to seed baseline?")) return;
    try {
      resetDbBtn.disabled = true;
      resetDbBtn.textContent = "Resetting...";
      const res = await fetch("/api/reset", { method: "POST" });
      if (!res.ok) throw new Error("Reset failed");
      hideAlert();
      await fetchUsers();
      await fetchTransactions();
      showAlert("Database successfully restored to baseline seed state.", false);
    } catch (err) {
      showAlert(err.message, true);
    } finally {
      resetDbBtn.disabled = false;
      resetDbBtn.textContent = "↺ Reset DB";
    }
  });

  // ===========================================================================
  // SQL Integrity Audit Modal
  // ===========================================================================

  async function fetchAuditSummary() {
    try {
      const res = await fetch("/api/audit");
      if (res.ok) {
        const data = await res.json();
        if (data.total_anomalies > 0) {
          auditBadge.textContent = data.total_anomalies;
          auditBadge.style.display = "inline-block";
        }
      }
    } catch (e) {
      console.warn("Could not fetch audit summary", e);
    }
  }

  runAuditBtn.addEventListener("click", async () => {
    auditModal.style.display = "flex";
    auditModalContent.innerHTML = `
      <div class="table-state-box">
        <div class="spinner"></div>
        <div class="state-title">Executing database audit queries...</div>
      </div>
    `;

    try {
      const res = await fetch("/api/audit");
      if (!res.ok) throw new Error("Failed to run audit");
      const data = await res.json();
      renderAuditReport(data);
    } catch (err) {
      auditModalContent.innerHTML = `
        <div class="alert-box alert-error">
          <span class="alert-icon">✕</span>
          <span class="alert-text">Error executing audit queries: ${err.message}</span>
        </div>
      `;
    }
  });

  closeAuditModalBtn.addEventListener("click", () => {
    auditModal.style.display = "none";
  });

  auditModal.addEventListener("click", (e) => {
    if (e.target === auditModal) {
      auditModal.style.display = "none";
    }
  });

  function renderAuditReport(data) {
    const anomalies = data.anomalies;

    let html = `
      <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid var(--border-subtle); padding-bottom: 12px;">
        <span class="section-label">AUDIT EXECUTION SUMMARY</span>
        <span class="badge badge-warning">${data.total_anomalies} INTEGRITY ANOMALIES DETECTED</span>
      </div>
    `;

    // Section 1: Ledger Mismatch
    html += `
      <div class="audit-card">
        <div class="audit-card-header">
          <span class="audit-card-title">1. LEDGER RECONCILIATION DISCREPANCY</span>
          <span class="mono-badge">${anomalies.ledger_mismatches.length} VIOLATION(S)</span>
        </div>
        <p class="audit-desc">Identifies accounts where users.balance does not equal the sum of completed ledger transactions.</p>
        <table class="sub-table">
          <thead>
            <tr>
              <th>USER ID</th>
              <th>USERNAME</th>
              <th>CACHED BALANCE</th>
              <th>LEDGER SUM</th>
              <th>DISCREPANCY</th>
              <th>CLASSIFICATION</th>
            </tr>
          </thead>
          <tbody>
            ${
              anomalies.ledger_mismatches.length > 0
                ? anomalies.ledger_mismatches
                    .map(
                      (m) => `
                <tr>
                  <td>#${m.user_id}</td>
                  <td>${m.username}</td>
                  <td>$${formatCurrency(m.current_cached_balance)}</td>
                  <td>$${formatCurrency(m.ledger_calculated_balance)}</td>
                  <td style="color: var(--color-debit); font-weight: 700;">$${formatCurrency(m.discrepancy_amount)}</td>
                  <td><span class="badge badge-warning">${m.anomaly_classification}</span></td>
                </tr>
              `
                    )
                    .join("")
                : '<tr><td colspan="6">No discrepancies detected.</td></tr>'
            }
          </tbody>
        </table>
      </div>
    `;

    // Section 2: Duplicate Transactions
    html += `
      <div class="audit-card">
        <div class="audit-card-header">
          <span class="audit-card-title">2. DUPLICATE TRANSACTION (IDEMPOTENCY FAILURE)</span>
          <span class="mono-badge">${anomalies.duplicate_transactions.length} VIOLATION(S)</span>
        </div>
        <p class="audit-desc">Identifies transactions with identical reference_id, user_id, amount, and type processed multiple times.</p>
        <table class="sub-table">
          <thead>
            <tr>
              <th>REFERENCE ID</th>
              <th>USER</th>
              <th>TYPE</th>
              <th>AMOUNT</th>
              <th>COUNT</th>
              <th>TRANSACTION IDS</th>
            </tr>
          </thead>
          <tbody>
            ${
              anomalies.duplicate_transactions.length > 0
                ? anomalies.duplicate_transactions
                    .map(
                      (d) => `
                <tr>
                  <td>${d.reference_id}</td>
                  <td>${d.username} (#${d.user_id})</td>
                  <td>${d.type}</td>
                  <td>$${formatCurrency(d.amount)}</td>
                  <td style="color: var(--color-debit); font-weight: 700;">${d.occurrence_count}x</td>
                  <td>#${d.duplicate_transaction_ids}</td>
                </tr>
              `
                    )
                    .join("")
                : '<tr><td colspan="6">No duplicates detected.</td></tr>'
            }
          </tbody>
        </table>
      </div>
    `;

    // Section 3: Negative Balances
    html += `
      <div class="audit-card">
        <div class="audit-card-header">
          <span class="audit-card-title">3. NEGATIVE BALANCE (OVERDRAFT VIOLATION)</span>
          <span class="mono-badge">${anomalies.negative_balances.length} VIOLATION(S)</span>
        </div>
        <p class="audit-desc">Identifies user accounts with balance &lt; 0.00 in a strict non-credit wallet architecture.</p>
        <table class="sub-table">
          <thead>
            <tr>
              <th>USER ID</th>
              <th>USERNAME</th>
              <th>CURRENT BALANCE</th>
              <th>ACCOUNT CREATED AT</th>
            </tr>
          </thead>
          <tbody>
            ${
              anomalies.negative_balances.length > 0
                ? anomalies.negative_balances
                    .map(
                      (n) => `
                <tr>
                  <td>#${n.user_id}</td>
                  <td>${n.username}</td>
                  <td style="color: var(--color-debit); font-weight: 700;">$${formatCurrency(n.negative_balance)}</td>
                  <td>${n.account_created_at}</td>
                </tr>
              `
                    )
                    .join("")
                : '<tr><td colspan="4">No negative balances detected.</td></tr>'
            }
          </tbody>
        </table>
      </div>
    `;

    auditModalContent.innerHTML = html;
  }

  // Initial Load
  txnReferenceInput.value = generateReferenceId();
  fetchUsers();
});
