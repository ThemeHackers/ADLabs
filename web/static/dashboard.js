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
    
   
    const labLogModal = document.getElementById("lab-log-modal");
    const labLogBody = document.getElementById("lab-log-body");
    const btnCloseLabModal = document.getElementById("btn-close-lab-modal");
    const labModalTitle = document.getElementById("lab-modal-title");
    const labModalStatus = document.getElementById("lab-modal-status");
    const btnModalCopyLog = document.getElementById("btn-modal-copy-log");
    const btnModalAutoscroll = document.getElementById("btn-modal-autoscroll");
    const btnModalClearLog = document.getElementById("btn-modal-clear-log");
    
    let eventSource = null;
    let labsDataCache = [];
    const activeLogs = {};
    const activeLogVisible = {};
    const activeLogAutoscroll = {};

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
                        <div class="terminal-dots">
                            <span class="dot dot-close btn-close-log" data-index="${lab.index}" title="Close Log"></span>
                            <span class="dot dot-minimize" title="Minimize"></span>
                            <span class="dot dot-expand btn-maximize-log" data-index="${lab.index}" title="Maximize Log"></span>
                        </div>
                        <span class="terminal-title">Execution Log</span>
                        <div class="terminal-actions">
                            <button class="btn-log-action btn-copy-log" data-index="${lab.index}" title="Copy Logs">
                                <i data-lucide="copy" style="width: 12px; height: 12px;"></i>
                            </button>
                            <button class="btn-log-action btn-autoscroll" data-index="${lab.index}" title="Toggle Auto-scroll">
                                <i data-lucide="chevrons-down" style="width: 12px; height: 12px;"></i>
                            </button>
                        </div>
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
                if (activeLogAutoscroll[lab.index] !== false) {
                    setTimeout(() => { logBody.scrollTop = logBody.scrollHeight; }, 0);
                }
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

       
        document.querySelectorAll(".btn-copy-log").forEach(btn => {
            btn.addEventListener("click", (e) => {
                e.stopPropagation();
                const index = btn.dataset.index;
                const logBody = btn.closest(".lab-card").querySelector(".lab-log-body");
                if (logBody) {
                    const clone = logBody.cloneNode(true);
                    const cursor = clone.querySelector(".terminal-cursor");
                    if (cursor) cursor.remove();
                    const text = clone.innerText || clone.textContent;
                    navigator.clipboard.writeText(text).then(() => {
                        showToast(`Copied Lab ${index} execution log to clipboard!`, "success");
                    }).catch(err => {
                        showToast("Failed to copy log: " + err.message, "error");
                    });
                }
            });
        });

 
        document.querySelectorAll(".btn-autoscroll").forEach(btn => {
            const index = btn.dataset.index;
            if (activeLogAutoscroll[index] !== false) {
                btn.classList.add("active");
            } else {
                btn.classList.remove("active");
            }
            btn.addEventListener("click", (e) => {
                e.stopPropagation();
                const current = activeLogAutoscroll[index] !== false;
                activeLogAutoscroll[index] = !current;
                if (!current) {
                    btn.classList.remove("active");
                    showToast(`Auto-scroll disabled for Lab ${index}`, "info");
                } else {
                    btn.classList.add("active");
                    showToast(`Auto-scroll enabled for Lab ${index}`, "info");
                    const logBody = btn.closest(".lab-card").querySelector(".lab-log-body");
                    if (logBody) logBody.scrollTop = logBody.scrollHeight;
                }
            });
        });

        document.querySelectorAll(".btn-maximize-log").forEach(btn => {
            btn.addEventListener("click", (e) => {
                e.stopPropagation();
                const index = btn.dataset.index;
                showMaximizedLog(index);
            });
        });
    }

    let maximizedLabIndex = null;
    let maximizedInterval = null;

    function showMaximizedLog(index) {
        const lab = labsDataCache.find(l => l.index === parseInt(index));
        if (!lab) return;

        maximizedLabIndex = index;
        const labDisplayName = lab.dir.replace(/[-_]/g, " ").replace(/\b\w/g, c => c.toUpperCase());
        
        labModalTitle.textContent = `Lab ${index} Terminal Console — ${labDisplayName}`;
        

        labModalStatus.textContent = lab.status;
        labModalStatus.className = `lab-modal-status-badge ${
            lab.status === 'RUNNING' ? 'status-running' : 
            lab.status === 'PARTIAL' ? 'status-partial' : 'status-stopped'
        }`;


        if (activeLogAutoscroll[index] !== false) {
            btnModalAutoscroll.classList.add("active");
        } else {
            btnModalAutoscroll.classList.remove("active");
        }

        labLogModal.classList.add("active");
        
        const updateMaximizedContent = () => {
            const currentLogHTML = activeLogs[index] || "<div class=\"log-line\">Console initialized. Waiting for command execution...</div>";
            labLogBody.innerHTML = currentLogHTML;
            if (activeLogAutoscroll[index] !== false) {
                labLogBody.scrollTop = labLogBody.scrollHeight;
            }
        };

        updateMaximizedContent();

        if (maximizedInterval) clearInterval(maximizedInterval);
        maximizedInterval = setInterval(() => {
            if (!labLogModal.classList.contains("active") || maximizedLabIndex !== index) {
                clearInterval(maximizedInterval);
                return;
            }
            updateMaximizedContent();
        }, 1000);
    }

    function closeLabLogModal() {
        labLogModal.classList.remove("active");
        if (maximizedInterval) {
            clearInterval(maximizedInterval);
            maximizedInterval = null;
        }
        maximizedLabIndex = null;
    }

    function startStream(index, action) {
        if (eventSource) {
            eventSource.close();
        }

        const card = document.querySelector(`.btn-deploy[data-index="${index}"]`).closest('.lab-card');
        const logArea = card.querySelector(".lab-log-area");
        const logBody = card.querySelector(".lab-log-body");
        
        logArea.style.display = "flex";
        logBody.innerHTML = '<span class="terminal-cursor"></span>';
        activeLogs[index] = logBody.innerHTML;
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
            
            const cursor = logBody.querySelector(".terminal-cursor");
            if (cursor) cursor.remove();

            if (line === "[DONE]") {
                eventSource.close();
                eventSource = null;
                
                const banner = document.createElement("div");
                banner.className = "completion-banner completion-banner-success";
                banner.innerHTML = `<i data-lucide="check-circle" style="width: 14px; height: 14px;"></i> Execution Finished`;
                logBody.appendChild(banner);
                
                lucide.createIcons();
                
                if (activeLogAutoscroll[index] !== false) {
                    logBody.scrollTop = logBody.scrollHeight;
                }
                
                activeLogs[index] = logBody.innerHTML;
                fetchLabs();
                return;
            }
            
            const logLine = document.createElement("div");
            logLine.className = "log-line";
            logLine.innerHTML = ansiToHtml(line);
            logBody.appendChild(logLine);
            
            const newCursor = document.createElement("span");
            newCursor.className = "terminal-cursor";
            logBody.appendChild(newCursor);
            
            if (activeLogAutoscroll[index] !== false) {
                logBody.scrollTop = logBody.scrollHeight;
            }
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
        globalLogBody.className = "modal-body";
        
        const modalTitle = document.getElementById("global-modal-title");
        const actionTitle = action === 'stop-all' ? 'Stop All Labs' : (action === 'clean-all' ? 'Clean All Labs' : 'Rebuild Wordlists');
        modalTitle.textContent = `Global Task: ${actionTitle}`;

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
        if (maximizedInterval) {
            clearInterval(maximizedInterval);
            maximizedInterval = null;
        }
        maximizedLabIndex = null;
    };

    btnCloseModal.addEventListener("click", closeTargetsModal);
    btnCloseLabModal.addEventListener("click", closeLabLogModal);
    window.addEventListener("click", (e) => {
        if (e.target === targetsModal) closeTargetsModal();
        if (e.target === globalLogModal && !btnCloseGlobalModal.disabled) closeGlobalModal();
        if (e.target === labLogModal) closeLabLogModal();
    });

    btnCloseGlobalModal.addEventListener("click", closeGlobalModal);
    btnCloseGlobalModalFooter.addEventListener("click", closeGlobalModal);


    btnModalCopyLog.addEventListener("click", () => {
        if (maximizedLabIndex !== null) {
            const currentLogText = labLogBody.innerText || labLogBody.textContent;
            navigator.clipboard.writeText(currentLogText).then(() => {
                showToast("Copied terminal output to clipboard!", "success");
            }).catch(err => {
                showToast("Failed to copy log: " + err.message, "error");
            });
        }
    });

    btnModalAutoscroll.addEventListener("click", () => {
        if (maximizedLabIndex !== null) {
            const index = maximizedLabIndex;
            const current = activeLogAutoscroll[index] !== false;
            activeLogAutoscroll[index] = !current;
            
            if (!current) {
                btnModalAutoscroll.classList.remove("active");
                showToast(`Auto-scroll disabled`, "info");
            } else {
                btnModalAutoscroll.classList.add("active");
                showToast(`Auto-scroll enabled`, "info");
                labLogBody.scrollTop = labLogBody.scrollHeight;
            }

            const cardAutoscrollBtn = document.querySelector(`.btn-autoscroll[data-index="${index}"]`);
            if (cardAutoscrollBtn) {
                if (!current) {
                    cardAutoscrollBtn.classList.remove("active");
                } else {
                    cardAutoscrollBtn.classList.add("active");
                }
            }
        }
    });

    btnModalClearLog.addEventListener("click", () => {
        if (maximizedLabIndex !== null) {
            const index = maximizedLabIndex;
            
            activeLogs[index] = '<span class="terminal-cursor"></span>';
            labLogBody.innerHTML = activeLogs[index];
            
            const card = document.querySelector(`.btn-deploy[data-index="${index}"]`).closest('.lab-card');
            const cardLogBody = card.querySelector(".lab-log-body");
            if (cardLogBody) {
                cardLogBody.innerHTML = activeLogs[index];
            }
            
            showToast(`Cleared execution logs for Lab ${index}`, "success");
        }
    });

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
