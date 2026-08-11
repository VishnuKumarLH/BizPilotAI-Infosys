(() => {
  "use strict";

  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
  const today = new Date().toISOString().slice(0, 10);

  function element(tag, className = "", text = null) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== null && text !== undefined) node.textContent = String(text);
    return node;
  }

  function avatarImage(source, alt = "") {
    const image = element("img");
    image.src = source;
    image.alt = alt;
    return image;
  }

  async function apiFetch(url, options = {}) {
    const response = await fetch(url, {
      credentials: "same-origin",
      headers: { Accept: "application/json", ...(options.headers || {}) },
      ...options,
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(
        payload.error || payload.errors?.join(" ") || "The request could not be completed."
      );
    }
    return payload;
  }

  function toast(message, type = "success") {
    const stack = $("#toastStack");
    if (!stack) return;
    const node = element("div", `toast ${type}`, message);
    stack.append(node);
    window.setTimeout(() => node.remove(), 4200);
  }

  function initNavigation() {
    const sidebar = $("#leftSidebar");
    if (!sidebar) {
      $$(".password-toggle").forEach(initPasswordToggle);
      return;
    }

    const leftToggle = $("#leftSidebarToggle");
    const mobileToggle = $("#mobileNavToggle");
    const backdrop = $("#mobileBackdrop");
    const accountToggle = $("#accountMenuToggle");
    const accountMenu = $("#accountMenu");
    const navSearch = $("#sidebarNavSearch");
    const overlayBreakpoint = 1199;
    const isOverlay = () => window.innerWidth <= overlayBreakpoint;

    function setAccountMenuOpen(open) {
      if (!accountToggle || !accountMenu) return;
      accountMenu.hidden = !open;
      accountToggle.setAttribute("aria-expanded", String(open));
    }

    function setDesktopCollapsed(collapsed, persist = true) {
      document.body.classList.toggle("nav-collapsed", collapsed);
      leftToggle?.setAttribute("aria-expanded", String(!collapsed));
      leftToggle?.setAttribute("aria-label", collapsed ? "Expand navigation" : "Collapse navigation");
      if (leftToggle) leftToggle.title = collapsed ? "Expand navigation" : "Collapse navigation";
      if (persist) localStorage.setItem("bizpilot-nav", collapsed ? "collapsed" : "open");
      setAccountMenuOpen(false);
    }

    function setDrawerOpen(open, restoreFocus = false) {
      document.body.classList.toggle("mobile-nav-open", open);
      mobileToggle?.setAttribute("aria-expanded", String(open));
      mobileToggle?.setAttribute("aria-label", open ? "Close navigation" : "Open navigation");
      sidebar.setAttribute("aria-hidden", String(!open));
      sidebar.inert = !open;
      leftToggle?.setAttribute("aria-label", "Close navigation");
      if (!open) setAccountMenuOpen(false);
      if (open) window.setTimeout(() => leftToggle?.focus(), 160);
      else if (restoreFocus) mobileToggle?.focus();
    }

    function syncNavigation() {
      if (isOverlay()) {
        document.body.classList.remove("nav-collapsed");
        setDrawerOpen(false);
      } else {
        document.body.classList.remove("mobile-nav-open");
        sidebar.removeAttribute("aria-hidden");
        sidebar.inert = false;
        setDesktopCollapsed(localStorage.getItem("bizpilot-nav") === "collapsed", false);
      }
    }

    leftToggle?.addEventListener("click", () => {
      if (isOverlay()) setDrawerOpen(false, true);
      else setDesktopCollapsed(!document.body.classList.contains("nav-collapsed"));
    });
    mobileToggle?.setAttribute("aria-controls", "leftSidebar");
    mobileToggle?.addEventListener("click", () => {
      setDrawerOpen(!document.body.classList.contains("mobile-nav-open"), true);
    });
    backdrop?.addEventListener("click", () => setDrawerOpen(false, true));
    accountToggle?.addEventListener("click", (event) => {
      event.stopPropagation();
      setAccountMenuOpen(accountMenu?.hidden ?? true);
    });
    accountMenu?.addEventListener("click", (event) => event.stopPropagation());
    document.addEventListener("click", () => setAccountMenuOpen(false));
    $$(".left-sidebar a").forEach((link) => {
      link.addEventListener("click", () => {
        setAccountMenuOpen(false);
        if (isOverlay()) window.setTimeout(() => setDrawerOpen(false), 0);
      });
    });

    let previousOverlay = isOverlay();
    window.addEventListener("resize", () => {
      const overlay = isOverlay();
      if (overlay !== previousOverlay) {
        syncNavigation();
        previousOverlay = overlay;
      }
    });

    function applyTheme(theme, persist = true) {
      const nextTheme = theme === "dark" ? "dark" : "light";
      document.documentElement.dataset.theme = nextTheme;
      document.querySelector('meta[name="theme-color"]')?.setAttribute(
        "content",
        nextTheme === "dark" ? "#101218" : "#f4f6fb"
      );
      $$('[data-theme-value]').forEach((button) => {
        const active = button.dataset.themeValue === nextTheme;
        button.classList.toggle("active", active);
        button.setAttribute("aria-pressed", String(active));
      });
      $$('[data-theme-cycle]').forEach((button) => {
        button.setAttribute("aria-label", nextTheme === "dark" ? "Use light theme" : "Use dark theme");
        button.title = nextTheme === "dark" ? "Use light theme" : "Use dark theme";
      });
      if (persist) localStorage.setItem("bizpilot-theme", nextTheme);
    }

    applyTheme(localStorage.getItem("bizpilot-theme") || "light", false);
    $$('[data-theme-value]').forEach((button) => {
      button.addEventListener("click", () => applyTheme(button.dataset.themeValue));
    });
    $$('[data-theme-cycle]').forEach((button) => {
      button.addEventListener("click", () => {
        applyTheme(document.documentElement.dataset.theme === "dark" ? "light" : "dark");
      });
    });

    navSearch?.addEventListener("input", () => {
      const query = navSearch.value.trim().toLowerCase();
      $$(".primary-nav .nav-item").forEach((item) => {
        item.hidden = Boolean(query) && !item.textContent.toLowerCase().includes(query);
      });
    });
    navSearch?.addEventListener("keydown", (event) => {
      if (event.key !== "Enter") return;
      const match = $(".primary-nav .nav-item:not([hidden])");
      if (match?.href) match.click();
    });
    document.addEventListener("keydown", (event) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k" && navSearch) {
        event.preventDefault();
        if (isOverlay()) setDrawerOpen(true);
        navSearch.focus();
        return;
      }
      if (event.key !== "Escape") return;
      if (accountMenu && !accountMenu.hidden) {
        setAccountMenuOpen(false);
        accountToggle?.focus();
      } else if (isOverlay() && document.body.classList.contains("mobile-nav-open")) {
        setDrawerOpen(false, true);
      }
    });

    $$(".password-toggle").forEach(initPasswordToggle);
    syncNavigation();
  }

  function initPasswordToggle(button) {
    button.addEventListener("click", () => {
      const input = button.closest(".password-field")?.querySelector("input");
      if (!input) return;
      const showing = input.type === "text";
      input.type = showing ? "password" : "text";
      button.textContent = showing ? "Show" : "Hide";
      button.setAttribute("aria-label", showing ? "Show password" : "Hide password");
    });
  }

  function setDefaultDates(root = document) {
    $$('input[type="date"]', root).forEach((input) => {
      if (!input.value && !input.closest(".filter-row")) input.value = today;
    });
  }

  function openDialog(trigger) {
    const dialog = document.getElementById(trigger.dataset.dialogOpen);
    if (!dialog) return;
    const form = $("form.api-form", dialog);
    if (form) {
      form.reset();
      delete form.dataset.recordId;
      const title = $("[data-dialog-title]", form);
      if (title) title.textContent = title.textContent.replace(/^Edit/, "Add");
      setDefaultDates(form);
      if (trigger.dataset.recordId && trigger.dataset.fields) {
        form.dataset.recordId = trigger.dataset.recordId;
        if (title) title.textContent = title.textContent.replace(/^Add/, "Edit");
        let fields = {};
        try { fields = JSON.parse(trigger.dataset.fields); } catch (_) { fields = {}; }
        Object.entries(fields).forEach(([name, value]) => {
          const input = form.elements.namedItem(name);
          if (!input || value === null || value === undefined) return;
          if (input.type === "checkbox") input.checked = Boolean(value);
          else input.value = value;
        });
      }
    }
    dialog.showModal();
  }

  function serializeForm(form) {
    const data = {};
    new FormData(form).forEach((value, key) => { data[key] = value; });
    $$('input[type="checkbox"]', form).forEach((input) => { data[input.name] = input.checked; });
    if (form.classList.contains("sale-form")) {
      data.items = $$(".sale-line", form).map((line) => ({
        product_id: $('[name="product_id"]', line)?.value,
        quantity: $('[name="quantity"]', line)?.value,
      }));
      delete data.product_id;
      delete data.quantity;
    }
    return data;
  }

  async function submitApiForm(form) {
    const button = $('button[type="submit"]', form);
    const original = button?.innerHTML;
    if (button) {
      button.disabled = true;
      button.textContent = "Saving...";
    }
    try {
      const endpoint = form.dataset.recordId
        ? `${form.dataset.createEndpoint}${form.dataset.recordId}`
        : form.dataset.createEndpoint;
      const payload = await apiFetch(endpoint, {
        method: form.dataset.recordId ? "PUT" : "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(serializeForm(form)),
      });
      toast(payload.message || "Saved.");
      form.closest("dialog")?.close();
      window.setTimeout(() => window.location.reload(), 300);
    } catch (error) {
      toast(error.message, "error");
    } finally {
      if (button) {
        button.disabled = false;
        button.innerHTML = original;
      }
    }
  }

  function initDialogsAndCrud() {
    setDefaultDates();
    $$('[data-dialog-open]').forEach((trigger) => {
      trigger.addEventListener("click", () => openDialog(trigger));
    });
    $$('[data-dialog-close]').forEach((button) => {
      button.addEventListener("click", () => button.closest("dialog")?.close());
    });
    $$(".app-dialog").forEach((dialog) => {
      dialog.addEventListener("click", (event) => {
        if (event.target === dialog) dialog.close();
      });
    });
    $$("form.api-form").forEach((form) => {
      form.addEventListener("submit", (event) => {
        event.preventDefault();
        if (form.reportValidity()) submitApiForm(form);
      });
    });
    $$(".delete-button").forEach((button) => {
      button.addEventListener("click", async () => {
        const question = button.dataset.deleteMessage || `Delete or archive ${button.dataset.deleteName}?`;
        if (!window.confirm(question)) return;
        button.disabled = true;
        try {
          const payload = await apiFetch(button.dataset.deleteUrl, { method: "DELETE" });
          toast(payload.message || "Removed.");
          button.closest("tr, .feedback-card")?.remove();
        } catch (error) {
          toast(error.message, "error");
          button.disabled = false;
        }
      });
    });

    $$('[data-add-sale-line]').forEach((button) => {
      button.addEventListener("click", () => {
        const container = $("[data-sale-lines]", button.closest("form"));
        const first = $(".sale-line", container);
        if (!first) return;
        const clone = first.cloneNode(true);
        clone.querySelector("select").value = "";
        clone.querySelector('input[name="quantity"]').value = "1";
        container.append(clone);
      });
    });
    document.addEventListener("click", (event) => {
      const remove = event.target.closest("[data-remove-sale-line]");
      if (!remove) return;
      const container = remove.closest("[data-sale-lines]");
      if ($$(".sale-line", container).length > 1) remove.closest(".sale-line").remove();
      else toast("A sale needs at least one line item.", "error");
    });
    $$(".view-button").forEach((button) => button.addEventListener("click", () => showSale(button)));
  }

  async function showSale(button) {
    const dialog = document.getElementById(button.dataset.viewDialog);
    const content = $("[data-view-content]", dialog);
    if (!dialog || !content) return;
    content.replaceChildren(element("div", "history-skeleton"));
    dialog.showModal();
    try {
      const { sale } = await apiFetch(button.dataset.viewUrl);
      const title = $("[data-view-title]", dialog);
      if (title) title.textContent = sale.invoice_number;
      const summary = element("div", "invoice-summary");
      [
        ["Customer", sale.customer_name || "Walk-in Customer"],
        ["Date", `${sale.sale_date} · ${sale.sale_time}`],
        ["Payment", sale.payment_method],
        ["Subtotal", formatMoney(sale.total_amount)],
        ["Discount", formatMoney(sale.discount_amount)],
        ["Final amount", formatMoney(sale.final_amount)],
      ].forEach(([label, value]) => {
        const row = element("div", "invoice-summary-row");
        row.append(element("span", "", label), element("strong", "", value));
        summary.append(row);
      });
      const table = element("table", "invoice-items");
      const head = element("thead");
      const headRow = element("tr");
      ["Item", "Qty", "Price", "Total"].forEach((name) => headRow.append(element("th", "", name)));
      head.append(headRow);
      const body = element("tbody");
      sale.items.forEach((item) => {
        const row = element("tr");
        [item.product_name, item.quantity, formatMoney(item.unit_price), formatMoney(item.total_price)]
          .forEach((value) => row.append(element("td", "", value)));
        body.append(row);
      });
      table.append(head, body);
      content.replaceChildren(summary, table);
    } catch (error) {
      content.replaceChildren(element("div", "history-empty", error.message));
    }
  }

  function formatMoney(value) {
    return new Intl.NumberFormat("en-IN", {
      style: "currency",
      currency: "INR",
      maximumFractionDigits: 0,
    }).format(Number(value || 0));
  }

  function initChat() {
    const form = $("#chatForm");
    if (!form) return;

    const input = $("#chatInput");
    const messages = $("#messages");
    const welcome = $("#welcomeState");
    const typing = $("#typingIndicator");
    const sendButton = $("#sendButton");
    const clearButton = $("#clearPromptButton");
    const promptMenu = $("#promptMenu");
    const browsePrompts = $("#browsePromptsButton");
    const historyList = $("#historyList");
    const historySearch = $("#historySearch");
    const historyPanel = $("#historySidebar");
    const historyToggle = $("#historyToggle");
    const historyBackdrop = $("#historyBackdrop");
    const scrollToBottom = $("#scrollToBottom");
    const overlayBreakpoint = 1199;
    let activeSessionId = null;
    let sessions = [];
    let busy = false;
    let previousOverlay = window.innerWidth <= overlayBreakpoint;

    function ensureStream(clear = false) {
      if (clear) messages.replaceChildren();
      welcome?.setAttribute("hidden", "");
      let stream = $(".message-stream", messages);
      if (!stream) {
        stream = element("div", "message-stream");
        messages.append(stream);
      }
      return stream;
    }

    function isNearBottom() {
      return messages.scrollHeight - messages.scrollTop - messages.clientHeight < 96;
    }

    function updateScrollControl() {
      if (scrollToBottom) {
        scrollToBottom.hidden = isNearBottom() || messages.scrollHeight <= messages.clientHeight;
      }
    }

    function scrollBottom() {
      requestAnimationFrame(() => {
        messages.scrollTop = messages.scrollHeight;
        updateScrollControl();
      });
    }

    function setHistoryOpen(open, restoreFocus = false) {
      document.body.classList.toggle("history-closed", !open);
      historyToggle?.setAttribute("aria-expanded", String(open));
      historyToggle?.setAttribute("aria-label", open ? "Close recent decisions" : "Open recent decisions");
      historyPanel?.setAttribute("aria-hidden", String(!open));
      if (historyPanel) historyPanel.inert = !open;
      if (open && window.innerWidth <= overlayBreakpoint) {
        window.setTimeout(() => historySearch?.focus(), 160);
      } else if (!open && restoreFocus) historyToggle?.focus();
    }

    function closeHistoryOnNarrow() {
      if (window.innerWidth <= overlayBreakpoint) setHistoryOpen(false);
    }

    function setPromptMenuOpen(open) {
      if (!promptMenu) return;
      promptMenu.hidden = !open;
      browsePrompts?.setAttribute("aria-expanded", String(open));
    }

    function setPrompt(text) {
      input.value = text;
      updateInput();
      setPromptMenuOpen(false);
      input.focus();
    }

    function renderUser(text, timestamp = null) {
      const stream = ensureStream();
      const article = element("article", "message user");
      const avatar = element("div", "message-avatar user-message-avatar");
      avatar.append(avatarImage("/static/images/demo-user.png", ""));
      const body = element("div", "message-body");
      const meta = element("div", "message-meta");
      meta.append(element("strong", "", "You"), element("span", "", timestamp || "Just now"));
      body.append(meta, element("div", "user-bubble", text));
      article.append(body, avatar);
      stream.append(article);
      scrollBottom();
    }

    function renderList(container, items, ordered = false) {
      const list = element(ordered ? "ol" : "ul");
      (items || []).forEach((item) => list.append(element("li", "", item)));
      if (!list.children.length) list.append(element("li", "", "No additional items were returned."));
      container.append(list);
    }

    function renderWorkflow(card, workflow, response = {}) {
      if (!workflow || typeof workflow !== "object") return;
      const stages = [
        ["coordinator", "Coordinator"],
        ["orchestrator", "Planning Agent"],
        ["retriever", "Research Agent"],
        ["decision", "Analysis & Decision Agent"],
        ["response", "Response Agent"],
      ];
      const available = stages.filter(([name]) => workflow[name]);
      if (!available.length) return;
      const details = element("details", "workflow-details");
      const summary = element("summary");
      summary.append(element("span", "", "Agent workflow"), element("small", "", `${available.length} steps completed`));
      const steps = element("div", "workflow-steps");
      available.forEach(([, label], index) => {
        const step = element("div", "workflow-step");
        step.append(element("strong", "", `${index + 1}. ${label}`), element("small", "", "Completed"));
        steps.append(step);
      });
      if (response.workflow_id) {
        const workflowId = element("code", "workflow-id", response.workflow_id);
        steps.append(workflowId);
      }
      details.append(summary, steps);
      card.append(details);
    }

    function renderAssistant(response, timestamp = null, workflow = null) {
      const stream = ensureStream();
      const article = element("article", "message assistant");
      const avatar = element("div", "message-avatar ai-message-avatar");
      avatar.append(avatarImage("/static/images/bizpilot-ai-logo.png", ""));
      const body = element("div", "message-body");
      const meta = element("div", "message-meta");
      meta.append(element("strong", "", "BizPilot AI"), element("span", "", timestamp || "Just now"));
      const card = element("div", "ai-card");

      const summary = element("section", "ai-summary");
      summary.append(element("small", "", "Summary"), element("p", "", response.summary || "Analysis completed."));
      card.append(summary);

      const findings = element("section", "ai-section");
      findings.append(element("small", "", "Key findings"));
      renderList(findings, response.key_findings || []);
      card.append(findings);

      const decision = element("section", "ai-section");
      decision.append(element("small", "", "Final decision"));
      decision.append(element("div", "decision-block", response.final_decision || response.summary));
      card.append(decision);

      const actions = element("section", "ai-section");
      actions.append(element("small", "", "Recommendations"));
      renderList(actions, response.recommendations || [], true);
      card.append(actions);

      if (response.reasoning) {
        const reasoning = element("section", "ai-section");
        reasoning.append(element("small", "", "Why this decision"), element("p", "", response.reasoning));
        card.append(reasoning);
      }

      if (response.avoid_actions?.length) {
        const avoid = element("section", "ai-section avoid-section");
        avoid.append(element("small", "", "Avoid"));
        renderList(avoid, response.avoid_actions);
        card.append(avoid);
      }

      if (response.data_sources?.length) {
        const sources = element("section", "ai-section");
        sources.append(element("small", "", "Tools and data used"));
        const list = element("div", "source-list");
        response.data_sources.forEach((source) => list.append(element("span", "source-chip", source)));
        sources.append(list);
        card.append(sources);
      }

      if (response.fallback_used) {
        const fallbackLabel = response.ai_provider === "groq"
          ? "Gemini was unavailable, so BizPilot used the Groq fallback."
          : "AI providers were unavailable, so BizPilot used verified rule-based analysis.";
        card.append(element("div", "fallback-note", fallbackLabel));
      }

      renderWorkflow(card, workflow, response);

      const footer = element("footer", "ai-footer");
      const confidence = Math.round(Number(response.confidence || 0) * 100);
      const confidenceWrap = element("div", "confidence-wrap");
      confidenceWrap.append(element("span", "", `Confidence ${confidence}%`));
      const track = element("span", "confidence-track");
      const fill = element("i");
      fill.style.width = `${confidence}%`;
      track.append(fill);
      confidenceWrap.append(track);
      const provider = element(
        "span",
        "source-chip",
        response.ai_provider === "rule_based" ? "Rule-based" : (response.ai_provider || "Unavailable")
      );
      const copy = element("button", "icon-btn copy-response", "Copy");
      copy.type = "button";
      copy.addEventListener("click", async () => {
        const copyText = [
          response.summary,
          `Decision: ${response.final_decision || response.summary}`,
          ...(response.recommendations || []).map((item, index) => `${index + 1}. ${item}`),
        ].join("\n");
        try {
          await navigator.clipboard.writeText(copyText);
          copy.textContent = "Copied";
          window.setTimeout(() => { copy.textContent = "Copy"; }, 1300);
        } catch (_) {
          toast("Copy is not available in this browser.", "error");
        }
      });
      footer.append(confidenceWrap, provider, copy);
      card.append(footer);
      body.append(meta, card);
      article.append(avatar, body);
      stream.append(article);
      scrollBottom();
    }

    function dateLabel(value) {
      if (!value) return "";
      const date = new Date(value);
      return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    }

    function relativeDate(value) {
      if (!value) return "";
      const date = new Date(value);
      const diff = Date.now() - date.getTime();
      if (diff < 60000) return "Just now";
      if (diff < 3600000) return `${Math.floor(diff / 60000)}m ago`;
      if (diff < 86400000) return `${Math.floor(diff / 3600000)}h ago`;
      return date.toLocaleDateString([], { day: "numeric", month: "short" });
    }

    async function loadSession(sessionId) {
      try {
        const payload = await apiFetch(`/chat/sessions/${sessionId}`);
        activeSessionId = Number(sessionId);
        messages.replaceChildren();
        payload.messages.forEach((message) => {
          if (message.role === "user") renderUser(message.message_text, dateLabel(message.created_at));
          else if (message.role === "assistant") {
            const response = message.agent_workflow?.response || {
              summary: message.message_text,
              final_decision: message.message_text,
              confidence: message.confidence_score,
              ai_provider: message.ai_provider,
              fallback_used: message.fallback_used,
            };
            renderAssistant(response, dateLabel(message.created_at), message.agent_workflow);
          }
        });
        if (!payload.messages.length) resetChat();
        renderHistory();
        closeHistoryOnNarrow();
      } catch (error) {
        toast(error.message, "error");
      }
    }

    function groupLabel(value) {
      const date = new Date(value);
      const now = new Date();
      const diff = Math.floor((new Date(now.toDateString()) - new Date(date.toDateString())) / 86400000);
      if (diff === 0) return "Today";
      if (diff === 1) return "Yesterday";
      if (diff < 7) return "This week";
      return "Earlier";
    }

    function renderHistory() {
      const query = historySearch?.value.trim().toLowerCase() || "";
      const filtered = sessions.filter((session) =>
        `${session.session_title} ${session.preview}`.toLowerCase().includes(query)
      );
      const historyCount = $("#historyCount");
      if (historyCount) historyCount.textContent = `(${sessions.length})`;
      historyList.replaceChildren();
      if (!filtered.length) {
        historyList.append(element("div", "history-empty", query ? "No decisions match that search." : "Your saved decisions will appear here."));
        return;
      }
      const groups = new Map();
      filtered.forEach((session) => {
        const label = groupLabel(session.updated_at);
        if (!groups.has(label)) groups.set(label, []);
        groups.get(label).push(session);
      });
      groups.forEach((items, label) => {
        historyList.append(element("p", "history-group-title", label));
        items.forEach((session) => {
          const item = element("article", `history-item${Number(session.id) === activeSessionId ? " active" : ""}`);
          const open = element("button", "history-main");
          open.type = "button";
          open.setAttribute("aria-label", `Open decision: ${session.session_title}`);
          const mainTitle = element("strong", "", session.session_title);
          const preview = element("small", "", session.preview || "No response yet");
          const meta = element("span", "history-meta");
          meta.append(element("span", "history-date", relativeDate(session.updated_at)), element("span", "saved-badge", "Saved"));
          open.append(mainTitle, preview, meta);
          const actions = element("span", "history-actions");
          const rename = element("button", "", "R");
          rename.type = "button";
          rename.title = "Rename";
          rename.setAttribute("aria-label", `Rename ${session.session_title}`);
          rename.addEventListener("click", async (event) => {
            event.stopPropagation();
            const title = window.prompt("Rename decision", session.session_title);
            if (!title?.trim()) return;
            try {
              await apiFetch(`/chat/sessions/${session.id}/rename`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ title: title.trim() }),
              });
              await loadSessions();
            } catch (error) { toast(error.message, "error"); }
          });
          const archive = element("button", "", "×");
          archive.type = "button";
          archive.title = "Archive";
          archive.setAttribute("aria-label", `Archive ${session.session_title}`);
          archive.addEventListener("click", async (event) => {
            event.stopPropagation();
            if (!window.confirm("Archive this decision?")) return;
            try {
              await apiFetch(`/chat/sessions/${session.id}`, { method: "DELETE" });
              if (activeSessionId === Number(session.id)) resetChat();
              await loadSessions();
            } catch (error) { toast(error.message, "error"); }
          });
          actions.append(rename, archive);
          item.append(open, actions);
          open.addEventListener("click", () => loadSession(session.id));
          historyList.append(item);
        });
      });
    }

    async function loadSessions() {
      try {
        const payload = await apiFetch("/chat/sessions");
        sessions = payload.sessions;
        renderHistory();
      } catch (_) {
        historyList.replaceChildren(element("div", "history-empty", "Recent decisions could not be loaded."));
      }
    }

    function resetChat() {
      activeSessionId = null;
      messages.replaceChildren();
      if (welcome) {
        welcome.removeAttribute("hidden");
        messages.append(welcome);
      }
      input.value = "";
      updateInput();
      renderHistory();
      closeHistoryOnNarrow();
      input.focus();
      scrollBottom();
    }

    function setBusy(value) {
      busy = value;
      typing.hidden = !value;
      input.disabled = value;
      sendButton.disabled = value || !input.value.trim();
      clearButton.disabled = value;
      if (browsePrompts) browsePrompts.disabled = value;
      form.setAttribute("aria-busy", String(value));
    }

    async function sendPrompt(text) {
      const prompt = text.trim();
      if (!prompt || busy) return;
      renderUser(prompt);
      input.value = "";
      updateInput();
      setPromptMenuOpen(false);
      setBusy(true);
      scrollBottom();
      try {
        const payload = await apiFetch("/chat/send", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ prompt, session_id: activeSessionId }),
        });
        activeSessionId = Number(payload.session.id);
        renderAssistant(payload.response, null, payload.workflow);
        await loadSessions();
      } catch (error) {
        toast(error.message, "error");
        renderAssistant({
          summary: "BizPilot could not finish this analysis.",
          final_decision: "Please try the question again in a moment.",
          key_findings: [],
          recommendations: ["Retry the request.", "Check that your business data is available."],
          avoid_actions: [],
          reasoning: error.message,
          confidence: 0,
          ai_provider: "unavailable",
          fallback_used: false,
        });
      } finally {
        setBusy(false);
        updateInput();
        input.focus();
      }
    }

    function updateInput() {
      const count = input.value.length;
      $("#charCount").textContent = `${count} / 2000`;
      input.style.height = "auto";
      input.style.height = `${Math.min(input.scrollHeight, 132)}px`;
      sendButton.disabled = busy || !input.value.trim();
      clearButton.hidden = !input.value;
    }

    form.addEventListener("submit", (event) => {
      event.preventDefault();
      sendPrompt(input.value);
    });
    input.addEventListener("input", updateInput);
    input.addEventListener("keydown", (event) => {
      if (event.key === "Enter" && !event.shiftKey) {
        event.preventDefault();
        sendPrompt(input.value);
      }
    });
    clearButton?.addEventListener("click", () => setPrompt(""));
    $$("[data-prompt]").forEach((button) => {
      button.addEventListener("click", () => setPrompt(button.dataset.prompt));
    });
    $$('[data-suggested-prompt]').forEach((button) => {
      button.addEventListener("click", () => setPrompt(button.dataset.suggestedPrompt));
    });
    browsePrompts?.addEventListener("click", (event) => {
      event.stopPropagation();
      setPromptMenuOpen(promptMenu.hidden);
    });
    $("#closePromptMenu")?.addEventListener("click", () => setPromptMenuOpen(false));
    promptMenu?.addEventListener("click", (event) => event.stopPropagation());
    document.addEventListener("click", () => setPromptMenuOpen(false));
    historySearch?.addEventListener("input", renderHistory);

    const startNewChat = () => resetChat();
    $("#newChatButton")?.addEventListener("click", startNewChat);
    $("#topNewChatButton")?.addEventListener("click", startNewChat);
    $("#chatHelpButton")?.addEventListener("click", () => {
      toast("Ask about sales, inventory, expenses, feedback, or your next promotion.");
      input.focus();
    });
    $("#sidebarNewChat")?.addEventListener("click", (event) => {
      event.preventDefault();
      startNewChat();
    });
    historyToggle?.addEventListener("click", () => {
      setHistoryOpen(document.body.classList.contains("history-closed"));
    });
    $("#closeHistory")?.addEventListener("click", () => setHistoryOpen(false, true));
    historyBackdrop?.addEventListener("click", () => setHistoryOpen(false, true));
    scrollToBottom?.addEventListener("click", scrollBottom);
    messages.addEventListener("scroll", updateScrollControl, { passive: true });
    document.addEventListener("keydown", (event) => {
      if (event.key !== "Escape") return;
      if (!promptMenu.hidden) {
        setPromptMenuOpen(false);
        browsePrompts?.focus();
      } else if (!document.body.classList.contains("history-closed") && window.innerWidth <= overlayBreakpoint) {
        setHistoryOpen(false, true);
      }
    });
    window.addEventListener("resize", () => {
      const overlay = window.innerWidth <= overlayBreakpoint;
      if (overlay !== previousOverlay) {
        setHistoryOpen(!overlay);
        previousOverlay = overlay;
      }
      updateScrollControl();
    });

    setHistoryOpen(window.innerWidth > overlayBreakpoint);
    updateInput();
    updateScrollControl();
    loadSessions();
  }

  function initMemoryActions() {
    document.addEventListener("click", async (event) => {
      const deleteButton = event.target.closest("[data-delete-memory]");
      if (deleteButton) {
        const memoryId = deleteButton.dataset.deleteMemory;
        if (!window.confirm("Delete this long-term memory?")) return;
        try {
          await apiFetch(`/api/memory/${memoryId}`, { method: "DELETE" });
          document.querySelector(`[data-memory-card="${memoryId}"]`)?.remove();
          toast("Long-term memory deleted.");
        } catch (error) {
          toast(error.message, "error");
        }
        return;
      }
      const clearButton = event.target.closest("[data-clear-session]");
      if (clearButton) {
        const sessionId = clearButton.dataset.clearSession;
        if (!window.confirm("Clear all short-term messages in this session? Workflow history and long-term memory will remain.")) return;
        try {
          await apiFetch(`/api/memory/session/${sessionId}`, { method: "DELETE" });
          toast("Short-term session memory cleared.");
          window.location.reload();
        } catch (error) {
          toast(error.message, "error");
        }
      }
    });
  }

  document.addEventListener("DOMContentLoaded", () => {
    initNavigation();
    initDialogsAndCrud();
    initChat();
    initMemoryActions();
  });
})();
