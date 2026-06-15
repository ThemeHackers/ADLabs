document.addEventListener("DOMContentLoaded", () => {
    const labsContainer = document.getElementById("labs-container");
    const targetsModal = document.getElementById("targets-modal");
    const modalLabName = document.getElementById("modal-lab-name");
    const modalTargetsContent = document.getElementById("modal-targets-content");
    const btnCloseModal = document.getElementById("btn-close-modal");

    const globalLogModal = document.getElementById("global-log-modal");
    const globalLogBody = document.getElementById("global-log-body");
    const btnCloseGlobalModal = document.getElementById("btn-close-global-modal");
    const btnCloseGlobalModalFooter = document.getElementById("btn-close-global-modal-footer");
    
    let eventSource = null;
    let labsDataCache = [];
    const activeLogs = {};
    const activeLogVisible = {};

    lucide.createIcons();

    function escapeHtml(unsafe) {
        return unsafe
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }

    function showToast(message, type = "info") {
        let container = document.getElementById("toast-container");
        if (!container) {
            container = document.createElement("div");
            container.id = "toast-container";
            container.className = "toast-container";
            document.body.appendChild(container);
        }
        const toast = document.createElement("div");
        toast.className = `toast toast-${type}`;
        let icon = "info";
        if (type === "success") icon = "check-circle";
        if (type === "error") icon = "alert-circle";
        if (type === "warning") icon = "alert-triangle";
        toast.innerHTML = `
            <i data-lucide="${icon}" class="toast-icon"></i>
            <div class="toast-message">${escapeHtml(message)}</div>
        `;
        container.appendChild(toast);
        lucide.createIcons();
        setTimeout(() => toast.classList.add("active"), 50);
        setTimeout(() => {
            toast.classList.remove("active");
            setTimeout(() => toast.remove(), 300);
        }, 4000);
    }

    function ansiToHtml(ansiStr) {
        const ansiMap = {
            '0': 'reset',
            '31': 'term-red', '91': 'term-red',
            '32': 'term-green', '92': 'term-green',
            '33': 'term-yellow', '93': 'term-yellow',
            '34': 'term-blue', '94': 'term-blue',
            '35': 'term-magenta', '95': 'term-magenta',
            '36': 'term-cyan', '96': 'term-cyan',
            '39': 'reset'
        };
        
        let html = '';
        let openSpan = false;
        const parts = ansiStr.split(/\u001b\[/);
        
        parts.forEach((part, index) => {
            if (index === 0) {
                html += escapeHtml(part);
                return;
            }
            
            const match = part.match(/^([0-9;]*)m([\s\S]*)/);
            if (!match) {
                html += escapeHtml('\u001b[' + part);
                return;
            }
            
            const codes = match[1].split(';');
            const text = match[2];
            let className = '';
            
            codes.forEach(code => {
                if (ansiMap[code]) {
                    className = ansiMap[code];
                }
            });
            
            if (openSpan) {
                html += '</span>';
                openSpan = false;
            }
            
            if (className && className !== 'reset') {
                html += `<span class="${className}">${escapeHtml(text)}`;
                openSpan = true;
            } else {
                html += escapeHtml(text);
            }
        });
        
        if (openSpan) {
            html += '</span>';
        }
        
        return html;
    }

    async function fetchLabs() {
        try {
            const response = await fetch("/api/labs");
            const labs = await response.json();
            labsDataCache = labs;
            renderLabs(labs);
        } catch (error) {
            console.error("Error fetching labs:", error);
            labsContainer.innerHTML = `
                <div class="loading-state">
                    <p style="color: var(--danger)">❌ Failed to connect to backend server. Make sure Flask is running.</p>
                </div>
            `;
        }
    }

    function renderLabs(labs) {
        labsContainer.innerHTML = "";
        
        labs.forEach(lab => {
            const isRunning = lab.status === "RUNNING";
            const isPartial = lab.status === "PARTIAL";
            
            let statusClass = "status-stopped";
            if (isRunning) statusClass = "status-running";
            if (isPartial) statusClass = "status-partial";

            const statusLabel = isRunning ? "Running" : isPartial ? "Partial" : "Stopped";
            const labDisplayName = lab.dir.replace(/[-_]/g, " ").replace(/\b\w/g, c => c.toUpperCase());
            const runningCount = lab.containers.filter(c => c.status === "RUNNING").length;
            const totalCount = lab.containers.length;

            const card = document.createElement("div");
            card.className = `lab-card ${isRunning ? "active-lab" : ""}`;
            card.innerHTML = `
                <div class="lab-card-header">
                    <div class="lab-title-area">
                        <span class="lab-number">Lab ${lab.index}</span>
                        <h2 class="lab-name">${labDisplayName}</h2>
                    </div>
                    <span class="lab-status ${statusClass}">${statusLabel}</span>
                </div>

                <div class="lab-details">
                    <div class="detail-row">
                        <span class="detail-label">VPN Port</span>
                        <span class="detail-value">${lab.vpn_port ?? "—"}</span>
                    </div>
                    <div class="detail-row">
                        <span class="detail-label">Domains</span>
                        <span class="detail-value" title="${lab.dns_domains.join(", ")}">${lab.dns_domains.join(", ") || "—"}</span>
                    </div>
                    <div class="detail-row">
                        <span class="detail-label">Containers</span>
                        <span class="detail-value ${runningCount === totalCount && totalCount > 0 ? 'detail-value--up' : runningCount === 0 ? 'detail-value--down' : 'detail-value--partial'}">${runningCount}/${totalCount} Up</span>
                    </div>
                </div>

                <div class="lab-log-area">
                    <div class="lab-log-header">
                        <span>Execution Log</span>
                        <button class="btn-close-log" data-index="${lab.index}">&times;</button>
                    </div>
                    <div class="lab-log-body"></div>
                </div>

                <div class="lab-actions">
                    <div class="actions-left">
                        <button class="btn btn-primary btn-deploy" data-index="${lab.index}" ${isRunning ? "disabled" : ""}>
                            <i data-lucide="play" style="width: 14px; height: 14px;"></i> <span class="btn-text">Deploy</span>
                        </button>
                        <button class="btn btn-warning btn-stop" data-index="${lab.index}" ${!isRunning && !isPartial ? "disabled" : ""}>
                            <i data-lucide="square" style="width: 14px; height: 14px;"></i> <span class="btn-text">Stop</span>
                        </button>
                        <button class="btn btn-danger btn-clean" data-index="${lab.index}">
                            <i data-lucide="trash-2" style="width: 14px; height: 14px;"></i> <span class="btn-text">Clean</span>
                        </button>
                    </div>
                    <div class="actions-right">
                        <button class="btn btn-secondary btn-test" data-index="${lab.index}" title="Test Connectivity">
                            <i data-lucide="activity" style="width: 14px; height: 14px;"></i> <span class="btn-text">Test</span>
                        </button>
                        <button class="btn btn-secondary btn-regen-vpn" data-index="${lab.index}" title="Regenerate VPN Profile">
                            <i data-lucide="key" style="width: 14px; height: 14px;"></i>
                        </button>
                    </div>
                </div>

                <button class="vpn-download-bar btn-download-vpn" data-index="${lab.index}" data-filename="${lab.vpn_profile}">
                    <div class="vpn-download-left">
                        <i data-lucide="file-key" style="width: 15px; height: 15px;"></i>
                        <span class="vpn-download-filename">${lab.vpn_profile}</span>
                    </div>
                    <div class="vpn-download-right">
                        <span class="vpn-download-label">WireGuard Config</span>
                        <i data-lucide="arrow-down-to-line" style="width: 14px; height: 14px;"></i>
                    </div>
                </button>
            `;

            const logArea = card.querySelector(".lab-log-area");
            const logBody = card.querySelector(".lab-log-body");
            if (activeLogVisible[lab.index]) {
                logArea.style.display = "flex";
                logBody.innerHTML = activeLogs[lab.index] || "";
                setTimeout(() => { logBody.scrollTop = logBody.scrollHeight; }, 0);
            }

            const closeLogBtn = card.querySelector(".btn-close-log");
            closeLogBtn.addEventListener("click", (e) => {
                e.stopPropagation();
                logArea.style.display = "none";
                activeLogVisible[lab.index] = false;
            });

            const titleArea = card.querySelector(".lab-title-area");
            titleArea.style.cursor = "pointer";
            titleArea.addEventListener("click", () => showTargetsModal(lab.index));

            labsContainer.appendChild(card);
        });

        lucide.createIcons();
        bindCardEvents();
    }

    function bindCardEvents() {
        document.querySelectorAll(".btn-deploy").forEach(btn => {
            btn.addEventListener("click", () => startStream(btn.dataset.index, "deploy"));
        });
        document.querySelectorAll(".btn-stop").forEach(btn => {
            btn.addEventListener("click", () => startStream(btn.dataset.index, "stop"));
        });
        document.querySelectorAll(".btn-clean").forEach(btn => {
            btn.addEventListener("click", () => startStream(btn.dataset.index, "clean"));
        });
        document.querySelectorAll(".btn-test").forEach(btn => {
            btn.addEventListener("click", () => startStream(btn.dataset.index, "test"));
        });
        
        document.querySelectorAll(".btn-regen-vpn").forEach(btn => {
            btn.addEventListener("click", async () => {
                const index = btn.dataset.index;
                btn.disabled = true;
                try {
                    const response = await fetch(`/api/labs/${index}/gen-vpn`, { method: 'POST' });
                    const result = await response.json();
                    if (result.success) {
                        showToast(result.message, "success");
                    } else {
                        showToast(result.message, "error");
                    }
                } catch (error) {
                    showToast("Connection error: " + error.message, "error");
                } finally {
                    btn.disabled = false;
                }
            });
        });

        document.querySelectorAll(".btn-download-vpn").forEach(btn => {
            btn.addEventListener("click", async () => {
                const index = btn.dataset.index;
                const filename = (btn.dataset.filename || "").trim();
                btn.disabled = true;
                try {
                    const check = await fetch(`/api/labs/${index}/vpn-config`, { method: "HEAD" });
                    if (check.ok) {
                        const a = document.createElement("a");
                        a.href = `/api/labs/${index}/vpn-config`;
                        if (filename && filename !== "undefined" && filename !== "null") {
                            a.download = filename;
                        }
                        document.body.appendChild(a);
                        a.click();
                        a.remove();
                        showToast(`Downloading ${filename || "VPN config"}...`, "success");
                    } else {
                        const result = await (await fetch(`/api/labs/${index}/vpn-config`)).json();
                        showToast(result.error || "VPN config not found.", "error");
                    }
                } catch (error) {
                    showToast("Connection error: " + error.message, "error");
                } finally {
                    setTimeout(() => { btn.disabled = false; }, 800);
                }
            });
        });
    }

    function startStream(index, action) {
        if (eventSource) {
            eventSource.close();
        }

        const card = document.querySelector(`.btn-deploy[data-index="${index}"]`).closest('.lab-card');
        const logArea = card.querySelector(".lab-log-area");
        const logBody = card.querySelector(".lab-log-body");
        
        logArea.style.display = "flex";
        logBody.innerHTML = "";
        activeLogs[index] = "";
        activeLogVisible[index] = true;

        if (card) {
            card.querySelectorAll('.btn').forEach(btn => btn.disabled = true);
            const activeBtn = card.querySelector(`.btn-${action}`);
            if (activeBtn) {
                activeBtn.innerHTML = `<span class="spinner" style="width: 12px; height: 12px; border-width: 2px; display: inline-block;"></span>`;
            }
        }

        eventSource = new EventSource(`/api/labs/${index}/${action}`);
        
        eventSource.onmessage = (event) => {
            const line = event.data;
            if (line === "[DONE]") {
                eventSource.close();
                eventSource = null;
                fetchLabs();
                return;
            }
            
            const logLine = document.createElement("div");
            logLine.className = "log-line";
            logLine.innerHTML = ansiToHtml(line);
            logBody.appendChild(logLine);
            logBody.scrollTop = logBody.scrollHeight;
            activeLogs[index] = logBody.innerHTML;
        };

        eventSource.onerror = (err) => {
            console.error("EventSource error:", err);
            eventSource.close();
            eventSource = null;
            fetchLabs();
        };
    }

    function startGlobalStream(action) {
        if (eventSource) {
            eventSource.close();
        }

        globalLogModal.classList.add("active");
        globalLogBody.innerHTML = "";
        btnCloseGlobalModal.disabled = true;
        btnCloseGlobalModalFooter.disabled = true;

        const globalBtn = document.getElementById(`btn-global-${action === 'stop-all' ? 'stop' : (action === 'clean-all' ? 'clean' : 'wordlists')}`);
        if (globalBtn) {
            globalBtn.innerHTML = `<span class="spinner" style="width: 12px; height: 12px; border-width: 2px; display: inline-block;"></span>`;
        }

        document.querySelectorAll('.btn').forEach(btn => btn.disabled = true);

        eventSource = new EventSource(`/api/global/${action}`);
        
        eventSource.onmessage = (event) => {
            const line = event.data;
            if (line === "[DONE]") {
                eventSource.close();
                eventSource = null;
                btnCloseGlobalModal.disabled = false;
                btnCloseGlobalModalFooter.disabled = false;
                fetchLabs();
                return;
            }
            
            const logLine = document.createElement("div");
            logLine.className = "log-line";
            logLine.innerHTML = ansiToHtml(line);
            globalLogBody.appendChild(logLine);
            globalLogBody.scrollTop = globalLogBody.scrollHeight;
        };

        eventSource.onerror = (err) => {
            console.error("EventSource error:", err);
            eventSource.close();
            eventSource = null;
            btnCloseGlobalModal.disabled = false;
            btnCloseGlobalModalFooter.disabled = false;
            fetchLabs();
        };
    }

    async function showTargetsModal(index) {
        const lab = labsDataCache.find(l => l.index === index);
        if (!lab) return;

        modalLabName.textContent = `Lab ${index} Targets - ${lab.dir}`;
        modalTargetsContent.innerHTML = `<div class="spinner"></div><p>Fetching dynamic target statuses...</p>`;
        
        targetsModal.classList.add("active");

        try {
            const response = await fetch(`/api/labs/${index}/status`);
            const statusData = await response.json();
            
            if (statusData.targets && statusData.targets.length > 0) {
                let html = `<div class="targets-list">`;
                statusData.targets.forEach(t => {
                    html += `
                        <div class="target-item">
                            <div class="target-header">
                                <span>${t.name}</span>
                                <span class="detail-value">${t.protocol} / ${t.port}</span>
                            </div>
                            <div class="target-info">
                                <span>IP Address: <strong>${t.ip}</strong></span>
                            </div>
                        </div>
                    `;
                });
                html += `</div>`;
                modalTargetsContent.innerHTML = html;
            } else {
                modalTargetsContent.innerHTML = `<p style="color: var(--text-muted)">No targets defined for this lab.</p>`;
            }
        } catch (error) {
            modalTargetsContent.innerHTML = `<p style="color: var(--danger)">Failed to load targets info.</p>`;
        }
    }

    function closeTargetsModal() {
        targetsModal.classList.remove("active");
    }

    const closeGlobalModal = () => {
        globalLogModal.classList.remove("active");
    };

    btnCloseModal.addEventListener("click", closeTargetsModal);
    window.addEventListener("click", (e) => {
        if (e.target === targetsModal) closeTargetsModal();
        if (e.target === globalLogModal && !btnCloseGlobalModal.disabled) closeGlobalModal();
    });

    btnCloseGlobalModal.addEventListener("click", closeGlobalModal);
    btnCloseGlobalModalFooter.addEventListener("click", closeGlobalModal);

    document.getElementById("btn-global-stop").addEventListener("click", () => startGlobalStream("stop-all"));
    document.getElementById("btn-global-clean").addEventListener("click", () => {
        if (confirm("WARNING: Cleaning all labs will destroy all persistent databases and AD states. Proceed?")) {
            startGlobalStream("clean-all");
        }
    });
    document.getElementById("btn-global-wordlists").addEventListener("click", () => startGlobalStream("generate-wordlists"));

    fetchLabs();
    setInterval(fetchLabs, 15000);
});
