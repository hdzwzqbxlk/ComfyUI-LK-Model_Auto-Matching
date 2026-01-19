import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

const VERSION = "1.3.1";

app.registerExtension({
    name: "Comfy.AutoModelMatcher",
    async setup() {
        // 创建悬浮条容器 (仿 BizyAir 风格)
        const floater = document.createElement("div");
        floater.id = "lk-automatch-floater";
        floater.className = "lk-automatch-bar";

        // 使用 Glassmorphism 样式
        floater.style.cssText = `
            position: fixed;
            top: 20px;
            left: 50%;
            transform: translateX(-50%);
            z-index: 9000;
            background: rgba(30, 30, 30, 0.85); /* 深色磨砂背景 */
            backdrop-filter: blur(12px);
            -webkit-backdrop-filter: blur(12px);
            border: 1px solid rgba(255, 255, 255, 0.15);
            border-radius: 999px; /* Pill shape */
            padding: 6px 16px;
            display: flex;
            align-items: center;
            gap: 12px;
            box-shadow: 0 8px 20px rgba(0, 0, 0, 0.4);
            transition: all 0.3s ease;
            cursor: move; /* 指示可拖拽 */
            user-select: none;
            color: white;
            font-family: sans-serif;
            min-width: 200px;
            justify-content: center;
        `;

        // 添加拖拽逻辑
        let isDragging = false;
        let startX, startY, initialLeft, initialTop;

        floater.addEventListener("mousedown", (e) => {
            if (e.target.tagName === "BUTTON" || e.target.closest("button")) return;
            isDragging = true;

            // 计算当前 transform 的偏移量或直接改用 left/top 定位
            // 为了简单稳健，拖拽开始时我们切换为绝对定位计算
            const rect = floater.getBoundingClientRect();

            // 清除 transform 居中，转为 absolute layout
            floater.style.transform = "none";
            floater.style.left = `${rect.left}px`;
            floater.style.top = `${rect.top}px`;

            startX = e.clientX;
            startY = e.clientY;
            initialLeft = rect.left;
            initialTop = rect.top;

            floater.style.cursor = "grabbing";
            floater.style.transition = "none"; // Fix: Disable transition for instant drag response
        });

        document.addEventListener("mousemove", (e) => {
            if (!isDragging) return;
            const dx = e.clientX - startX;
            const dy = e.clientY - startY;
            floater.style.left = `${initialLeft + dx}px`;
            floater.style.top = `${initialTop + dy}px`;
        });

        document.addEventListener("mouseup", () => {
            if (isDragging) {
                isDragging = false;
                floater.style.cursor = "move";
                floater.style.transition = "all 0.3s ease"; // Restore transition
            }
        });

        // --- Logo / Title ---
        const titleSpan = document.createElement("span");
        titleSpan.innerHTML = `<span style="color: #64b5f6; font-weight: 800;">LK</span> Auto Match <span style="color: #888; font-size: 11px;">v${VERSION}</span>`;
        titleSpan.style.fontSize = "14px";
        titleSpan.style.fontWeight = "600";
        titleSpan.style.marginRight = "8px";
        titleSpan.style.pointerEvents = "none";

        // --- 核心按钮: 魔法棒 (Auto Match) ---
        const autoMatchBtn = document.createElement("button");
        autoMatchBtn.id = "lk-auto-match-btn";
        autoMatchBtn.innerHTML = `🪄 Start`;
        autoMatchBtn.title = "扫描丢失模型并自动匹配 (Shift+点击: 强制刷新在线搜索)";
        autoMatchBtn.style.cssText = `
            background: linear-gradient(135deg, #64b5f6 0%, #42a5f5 100%);
            color: white;
            border: none;
            border-radius: 20px;
            padding: 6px 16px;
            font-size: 13px;
            font-weight: 600;
            cursor: pointer;
            box-shadow: 0 2px 5px rgba(66, 165, 245, 0.3);
            transition: transform 0.1s, box-shadow 0.2s;
            display: flex;
            align-items: center;
            gap: 6px;
        `;
        autoMatchBtn.onmousedown = () => autoMatchBtn.style.transform = "scale(0.95)";
        autoMatchBtn.onmouseup = () => autoMatchBtn.style.transform = "scale(1)";
        autoMatchBtn.onmouseenter = () => autoMatchBtn.style.boxShadow = "0 4px 10px rgba(66, 165, 245, 0.5)";
        autoMatchBtn.onmouseleave = () => autoMatchBtn.style.boxShadow = "0 2px 5px rgba(66, 165, 245, 0.3)";

        // --- 设置按钮 (Settings) ---
        const settingsBtn = document.createElement("button");
        settingsBtn.id = "lk-settings-btn";
        settingsBtn.innerHTML = `⚙️`;
        settingsBtn.title = "设置 (API Key)";
        settingsBtn.style.cssText = `
            background: rgba(255, 255, 255, 0.1);
            color: #ddd;
            border: 1px solid rgba(255, 255, 255, 0.2);
            border-radius: 50%;
            width: 32px;
            height: 32px;
            display: flex;
            align-items: center;
            justify-content: center;
            cursor: pointer;
            transition: all 0.2s;
            font-size: 14px;
        `;
        settingsBtn.onmouseenter = () => {
            settingsBtn.style.background = "rgba(255, 255, 255, 0.2)";
            settingsBtn.style.color = "white";
        };
        settingsBtn.onmouseleave = () => {
            settingsBtn.style.background = "rgba(255, 255, 255, 0.1)";
            settingsBtn.style.color = "#ddd";
        };
        settingsBtn.onclick = () => showSettingsDialog();

        // --- 刷新按钮 ---
        const refreshBtn = document.createElement("button");
        refreshBtn.id = "lk-index-refresh-btn";
        refreshBtn.innerHTML = `🔄`;
        refreshBtn.title = "更新本地模型索引";
        refreshBtn.style.cssText = `
            background: rgba(255, 255, 255, 0.1);
            color: #ddd;
            border: 1px solid rgba(255, 255, 255, 0.2);
            border-radius: 50%;
            width: 32px;
            height: 32px;
            display: flex;
            align-items: center;
            justify-content: center;
            cursor: pointer;
            transition: all 0.2s;
            font-size: 14px;
        `;
        refreshBtn.onmouseenter = () => {
            refreshBtn.style.background = "rgba(255, 255, 255, 0.2)";
            refreshBtn.style.color = "white";
        };
        refreshBtn.onmouseleave = () => {
            refreshBtn.style.background = "rgba(255, 255, 255, 0.1)";
            refreshBtn.style.color = "#ddd";
        };

        // --- 事件绑定 ---
        refreshBtn.onclick = async () => {
            // Animate spin
            refreshBtn.style.transition = "transform 1s linear";
            refreshBtn.style.transform = "rotate(360deg)";

            refreshBtn.disabled = true;
            try {
                const res = await api.fetchApi("/auto-matcher/refresh-index", { method: "POST" });
                const data = await res.json();
                if (data.status === "ok") {
                    app.ui.dialog.show(`✅ 索引更新完成\n数据库共 ${data.count} 个模型文件。`);
                } else {
                    app.ui.dialog.show("更新失败: " + data.error);
                }
            } catch (e) {
                app.ui.dialog.show("请求出错: " + e.message);
            } finally {
                setTimeout(() => {
                    refreshBtn.style.transition = "none";
                    refreshBtn.style.transform = "none";
                    refreshBtn.disabled = false;
                }, 1000);
            }
        };

        autoMatchBtn.onclick = async (e) => {
            await runAutoMatch(autoMatchBtn, e.shiftKey);
        };

        // --- 挂载 ---
        floater.appendChild(titleSpan);
        floater.appendChild(autoMatchBtn);
        floater.appendChild(refreshBtn);
        floater.appendChild(settingsBtn); // Add settings button
        document.body.appendChild(floater);
    }
});

async function showSettingsDialog() {
    const content = document.createElement("div");
    content.style.width = "400px";
    content.style.fontFamily = "sans-serif";

    // 添加右上角关闭按钮
    const closeBtn = document.createElement("button");
    closeBtn.innerText = "✕";
    closeBtn.style.cssText = `
        position: absolute;
        top: 10px;
        right: 10px;
        background: transparent;
        border: none;
        color: #888;
        font-size: 18px;
        cursor: pointer;
        z-index: 10;
    `;
    closeBtn.onmouseenter = () => closeBtn.style.color = "white";
    closeBtn.onmouseleave = () => closeBtn.style.color = "#888";
    closeBtn.onclick = () => {
        const modal = content.closest(".comfy-modal");
        if (modal) modal.style.display = "none";
    };
    content.appendChild(closeBtn);

    const h3 = document.createElement("h3");
    h3.innerHTML = `⚙️ 插件设置 <span style="font-size:12px; color:#666; font-weight:normal; margin-left:8px;">v${VERSION}</span>`;
    h3.style.color = "#eee";
    h3.style.marginTop = "0";
    content.appendChild(h3);

    const desc = document.createElement("p");
    desc.innerText = "配置 API Key 以解决 Civitai 搜索被拦截 (403 Forbidden) 的问题。";
    desc.style.color = "#aaa";
    desc.style.fontSize = "13px";
    content.appendChild(desc);

    // Form
    const formGroup = document.createElement("div");
    formGroup.style.marginBottom = "15px";

    const label = document.createElement("label");
    label.innerText = "Civitai API Key:";
    label.style.display = "block";
    label.style.color = "#ddd";
    label.style.marginBottom = "5px";
    label.style.fontWeight = "bold";
    formGroup.appendChild(label);

    const input = document.createElement("input");
    input.type = "password";
    input.placeholder = "Paste your API Key here...";
    input.style.width = "100%";
    input.style.boxSizing = "border-box"; // Fix padding issue
    input.style.padding = "10px";
    input.style.background = "#2a2a2a";
    input.style.border = "1px solid #444";
    input.style.color = "#eee";
    input.style.borderRadius = "6px";
    input.style.outline = "none";
    input.style.fontSize = "14px";
    input.style.transition = "border-color 0.2s";
    input.onfocus = () => input.style.borderColor = "#64b5f6";
    input.onblur = () => input.style.borderColor = "#444";
    formGroup.appendChild(input);

    const helpLink = document.createElement("a");
    helpLink.href = "https://civitai.com/user/account";
    helpLink.target = "_blank";
    helpLink.style.textAlign = "right"; // Right align the link
    formGroup.appendChild(helpLink);

    content.appendChild(formGroup);

    // Fetch existing config
    try {
        const res = await api.fetchApi("/auto-matcher/get-config");
        const config = await res.json();
        if (config.civitai_api_key) {
            input.value = config.civitai_api_key;
        }
    } catch (e) {
        console.error("Failed to load config", e);
    }

    // Button Container
    const btnContainer = document.createElement("div");
    btnContainer.style.display = "flex";
    btnContainer.style.gap = "10px";
    content.appendChild(btnContainer);

    // Test Button
    const testBtn = document.createElement("button");
    testBtn.innerHTML = `
        <span style="font-size:16px; margin-right:6px;">🔌</span> 
        <span>验证连通性</span>
    `;
    testBtn.title = "测试 Civitai API Key 是否有效";
    testBtn.style.flex = "1"; // Equal width
    testBtn.style.display = "flex";
    testBtn.style.alignItems = "center";
    testBtn.style.justifyContent = "center";
    testBtn.style.padding = "10px";
    testBtn.style.background = "#37474f";
    testBtn.style.color = "white";
    testBtn.style.border = "1px solid #546e7a";
    testBtn.style.borderRadius = "6px";
    testBtn.style.cursor = "pointer";
    testBtn.style.fontSize = "14px";
    testBtn.style.fontWeight = "bold";
    testBtn.style.transition = "all 0.2s ease";
    testBtn.style.whiteSpace = "nowrap";

    testBtn.onmouseover = () => {
        testBtn.style.background = "#455a64";
        testBtn.style.transform = "translateY(-1px)";
    };
    testBtn.onmouseout = () => {
        testBtn.style.background = "#37474f";
        testBtn.style.transform = "translateY(0)";
    };

    testBtn.onclick = async () => {
        const key = input.value.trim();
        if (!key) {
            alert("请输入 API Key 后再测试");
            return;
        }
        const originalHTML = testBtn.innerHTML;
        testBtn.innerHTML = `<span>⏳ Testing...</span>`;
        testBtn.disabled = true;
        testBtn.style.opacity = "0.7";

        try {
            const res = await api.fetchApi("/auto-matcher/validate-config", {
                method: "POST",
                body: JSON.stringify({ civitai_api_key: key }),
                headers: { "Content-Type": "application/json" }
            });
            const result = await res.json();
            if (result.valid) {
                alert("✅ 验证成功: " + result.message);
            } else {
                alert("❌ 验证失败: " + result.message);
            }
        } catch (e) {
            alert("请求出错: " + e.message);
        } finally {
            testBtn.innerHTML = originalHTML;
            testBtn.disabled = false;
            testBtn.style.opacity = "1";
        }
    };
    btnContainer.appendChild(testBtn);

    // Save Button
    const saveBtn = document.createElement("button");
    saveBtn.innerHTML = `
        <span style="font-size:16px; margin-right:6px;">💾</span> 
        <span>保存设置</span>
    `;
    saveBtn.style.flex = "1"; // Equal width
    saveBtn.style.display = "flex";
    saveBtn.style.alignItems = "center";
    saveBtn.style.justifyContent = "center";
    saveBtn.style.padding = "10px";
    saveBtn.style.background = "linear-gradient(135deg, #6200ea 0%, #3700b3 100%)";
    saveBtn.style.color = "white";
    saveBtn.style.border = "none";
    saveBtn.style.borderRadius = "6px";
    saveBtn.style.cursor = "pointer";
    saveBtn.style.fontWeight = "bold";
    saveBtn.style.fontSize = "14px";
    saveBtn.style.whiteSpace = "nowrap";
    saveBtn.style.boxShadow = "0 4px 6px rgba(0,0,0,0.2)";
    saveBtn.style.transition = "all 0.2s ease";

    saveBtn.onmouseover = () => {
        saveBtn.style.transform = "translateY(-1px)";
        saveBtn.style.boxShadow = "0 6px 8px rgba(0,0,0,0.3)";
    };
    saveBtn.onmouseout = () => {
        saveBtn.style.transform = "translateY(0)";
        saveBtn.style.boxShadow = "0 4px 6px rgba(0,0,0,0.2)";
    };

    saveBtn.onclick = async () => {
        const newKey = input.value.trim();
        try {
            await api.fetchApi("/auto-matcher/save-config", {
                method: "POST",
                body: JSON.stringify({
                    civitai_api_key: newKey
                }),
                headers: { "Content-Type": "application/json" }
            });
            app.ui.dialog.close();
            app.ui.dialog.show("✅ 设置已保存！");
        } catch (e) {
            alert("保存失败: " + e.message);
        }
    };
    btnContainer.appendChild(saveBtn);

    app.ui.dialog.show(content);
}

async function runAutoMatch(btn, ignoreCache = false) {
    if (!app.graph || !app.graph._nodes || app.graph._nodes.length === 0) {
        app.ui.dialog.show("⚠️ 当前画布为空，请先加载工作流。");
        return;
    }

    const missingItems = findMissingModels();

    // Debug log for user transparency
    console.log("[LK Auto Match] Scan finished. Missing items:", missingItems);

    if (missingItems.length === 0) {
        app.ui.dialog.show("✨ 太棒了！未检测到丢失模型。\n(所有模型路径均有效)");
        return;
    }

    const originalHTML = btn.innerHTML;
    btn.innerHTML = `⏳ Scanning...`;
    btn.disabled = true;
    btn.style.cursor = "wait";

    try {
        // 1. 本地匹配
        const matchResponse = await api.fetchApi("/auto-matcher/match", {
            method: "POST",
            body: JSON.stringify({ items: missingItems }),
            headers: { "Content-Type": "application/json" }
        });
        const matchResult = await matchResponse.json();
        const matches = matchResult.matches || [];

        // 2. 筛选出仍然未匹配的项目
        const matchedIds = new Set(matches.map(m => m.id));
        const stillMissing = missingItems.filter(item => !matchedIds.has(item.id));

        let downloadResults = [];
        if (stillMissing.length > 0) {
            btn.innerHTML = `🌐 Searching...`;

            // 去重
            const uniqueMissing = [];
            const seenNames = new Set();
            for (const item of stillMissing) {
                if (!seenNames.has(item.current)) {
                    uniqueMissing.push(item);
                    seenNames.add(item.current);
                }
            }

            const searchResponse = await api.fetchApi("/auto-matcher/search", {
                method: "POST",
                body: JSON.stringify({ items: uniqueMissing, ignore_cache: ignoreCache }),
                headers: { "Content-Type": "application/json" }
            });
            const searchData = await searchResponse.json();
            downloadResults = searchData.downloads || [];
        }

        showResultsDialog(matches, downloadResults);

    } catch (err) {
        console.error("Auto Match Error:", err);
        app.ui.dialog.show("❌ 执行出错: " + err.message);
    } finally {
        btn.innerHTML = originalHTML;
        btn.disabled = false;
        btn.style.cursor = "pointer";
    }
}

function showResultsDialog(matches, downloadResults) {
    if (matches.length === 0 && downloadResults.length === 0) {
        app.ui.dialog.show("🤷‍♂️ 无匹配结果\n本地未找到替代文件，在线搜索也未命中。建议手动核对 Civitai/HuggingFace。");
        return;
    }

    const content = document.createElement("div");
    content.style.position = "relative"; // Ensure absolute positioning works for children
    content.style.padding = "10px";
    content.style.fontFamily = "sans-serif";
    content.style.minWidth = "400px";
    content.style.maxHeight = "80vh";
    content.style.overflowY = "auto";

    // 添加右上角关闭按钮 X
    const xBtn = document.createElement("button");
    xBtn.innerText = "✕";
    xBtn.style.cssText = `
        position: absolute;
        top: 5px;
        right: 5px;
        background: transparent;
        border: none;
        color: #888;
        font-size: 18px;
        cursor: pointer;
        z-index: 10;
        padding: 5px;
    `;
    xBtn.onmouseenter = () => xBtn.style.color = "white";
    xBtn.onmouseleave = () => xBtn.style.color = "#888";
    xBtn.onclick = () => {
        const modal = content.closest(".comfy-modal");
        if (modal) modal.style.display = "none";
    };
    content.appendChild(xBtn);

    // Helper to group items by type
    const groupByType = (items) => {
        const groups = {};
        for (const item of items) {
            const type = item.type || "unknown";
            if (!groups[type]) groups[type] = [];
            groups[type].push(item);
        }
        return groups;
    };

    // --- Local Matches Section ---
    if (matches.length > 0) {
        const h3 = document.createElement("h3");
        h3.innerText = `✅ 本地匹配 (${matches.length})`;
        h3.style.color = "#4caf50";
        h3.style.borderBottom = "1px solid #4caf50";
        h3.style.paddingBottom = "5px";
        h3.style.marginTop = "0";
        content.appendChild(h3);

        const groups = groupByType(matches);
        for (const [type, items] of Object.entries(groups)) {
            // Category Header
            const catHeader = document.createElement("div");
            catHeader.innerText = type.toUpperCase().replace("_", " ");
            catHeader.style.fontSize = "12px";
            catHeader.style.color = "#aaa";
            catHeader.style.marginTop = "10px";
            catHeader.style.fontWeight = "bold";
            catHeader.style.background = "rgba(255,255,255,0.05)";
            catHeader.style.padding = "4px 8px";
            catHeader.style.borderRadius = "4px";
            content.appendChild(catHeader);

            const ul = document.createElement("ul");
            ul.style.paddingLeft = "10px";
            ul.style.listStyle = "none";
            items.forEach(m => {
                const li = document.createElement("li");
                li.style.marginTop = "8px";
                li.style.background = "rgba(0,0,0,0.2)";
                li.style.padding = "6px";
                li.style.borderRadius = "4px";
                li.innerHTML = `
                    <div style="font-size:12px; opacity:0.7; text-decoration:line-through">${m.original}</div>
                    <div style="color:#81c784; font-weight:bold;">⬇ ${m.new_value}</div>
                `;
                ul.appendChild(li);
            });
            content.appendChild(ul);
        }
    }

    // --- Online Results Section ---
    if (downloadResults.length > 0) {
        const h3 = document.createElement("h3");
        h3.innerText = `🌐 在线资源 (${downloadResults.length})`;
        h3.style.color = "#64b5f6";
        h3.style.borderBottom = "1px solid #64b5f6";
        h3.style.paddingBottom = "5px";
        h3.style.marginTop = "20px";
        content.appendChild(h3);

        const groups = groupByType(downloadResults);
        for (const [type, items] of Object.entries(groups)) {
            // Category Header
            const catHeader = document.createElement("div");
            catHeader.innerText = type.toUpperCase().replace("_", " ");
            catHeader.style.fontSize = "12px";
            catHeader.style.color = "#aaa";
            catHeader.style.marginTop = "10px";
            catHeader.style.fontWeight = "bold";
            catHeader.style.background = "rgba(255,255,255,0.05)";
            catHeader.style.padding = "4px 8px";
            catHeader.style.borderRadius = "4px";
            content.appendChild(catHeader);

            const ul = document.createElement("ul");
            ul.style.paddingLeft = "10px";
            ul.style.listStyle = "none";
            items.forEach(d => {
                const li = document.createElement("li");
                li.style.marginTop = "8px";
                li.style.background = "rgba(0,0,0,0.2)";
                li.style.padding = "6px";
                li.style.borderRadius = "4px";
                li.innerHTML = `
                    <div style="font-weight:bold; margin-bottom:4px; color:#ffcc80">${d.original}</div>
                    <div style="display:flex; gap:8px;">
                        <a href="${d.result.url}" target="_blank" style="
                            display: inline-block;
                            background: #2196f3;
                            color: white;
                            text-decoration: none;
                            padding: 4px 12px;
                            border-radius: 4px;
                            font-size: 12px;
                            transition: background 0.2s;
                        ">⬇ 下载 (${d.result.source})</a>

                        ${d.result.pageUrl ? `
                        <a href="${d.result.pageUrl}" target="_blank" style="
                            display: inline-block;
                            background: #444;
                            color: #ccc;
                            text-decoration: none;
                            padding: 4px 12px;
                            border: 1px solid #666;
                            border-radius: 4px;
                            font-size: 12px;
                            transition: all 0.2s;
                        " onmouseover="this.style.color='white';this.style.borderColor='#999'" onmouseout="this.style.color='#ccc';this.style.borderColor='#666'">🌍 查看详情</a>
                        ` : ''}
                    </div>
                `;
                ul.appendChild(li);
            });
            content.appendChild(ul);
        }
    }

    // --- Action Buttons ---
    const actionsBar = document.createElement("div");
    actionsBar.style.display = "flex";
    actionsBar.style.gap = "10px";
    actionsBar.style.marginTop = "20px";
    actionsBar.style.borderTop = "1px solid var(--border-color)";
    actionsBar.style.paddingTop = "10px";

    if (matches.length > 0) {
        const confirmBtn = document.createElement("button");
        confirmBtn.innerText = "🚀 应用所有本地修复";
        confirmBtn.style.cssText = `
                flex: 2;
                padding: 10px;
                background: linear-gradient(135deg, #43a047 0%, #2e7d32 100%);
                color: white;
                border: none;
                border-radius: 6px;
                cursor: pointer;
                font-weight: bold;
                font-size: 14px;
                box-shadow: 0 2px 5px rgba(0, 0, 0, 0.3);
                `;
        confirmBtn.onclick = () => {
            applyFixes(matches);
            confirmBtn.innerText = "✅ 已应用修复";
            confirmBtn.disabled = true;
            confirmBtn.style.background = "#555";
            confirmBtn.style.cursor = "default";
        };
        actionsBar.appendChild(confirmBtn);
    }

    // 再次网络筛选按钮
    const retryBtn = document.createElement("button");
    retryBtn.innerText = "🔄 再次网络筛选";
    retryBtn.title = "强制忽略缓存，重新搜索在线资源";
    retryBtn.style.cssText = `
                flex: 1;
                padding: 10px;
                background: linear-gradient(135deg, #2196f3 0%, #1976d2 100%);
                color: white;
                border: none;
                border-radius: 6px;
                cursor: pointer;
                font-weight: bold;
                box-shadow: 0 2px 5px rgba(0, 0, 0, 0.3);
                `;
    retryBtn.onclick = async () => {
        const modal = content.closest(".comfy-modal");
        if (modal) modal.style.display = "none";
        const autoMatchBtn = document.getElementById("lk-auto-match-btn");
        if (autoMatchBtn) {
            await runAutoMatch(autoMatchBtn, true);
        }
    };
    actionsBar.appendChild(retryBtn);



    content.appendChild(actionsBar);

    app.ui.dialog.show(content);
}

function findMissingModels() {
    const missing = [];
    const graph = app.graph;

    if (!graph || !graph._nodes) return [];

    for (const node of graph._nodes) {
        if (!node.widgets) continue;

        for (const widget of node.widgets) {
            // FIX: Removed strict type check. 
            // Instead, check if the widget has an options object with a values array.
            // This covers "COMBO", "customtext", and many custom node widgets.
            if (widget.options && Array.isArray(widget.options.values)) {
                const value = widget.value;
                const options = widget.options.values;

                // Condition: Value exists AND Options array exists AND Value is NOT in Options
                if (value && options.length >= 0 && !options.includes(value)) {

                    // FIX: Ignore Image Uploads (don't try to match user input images)
                    const strVal = String(value).toLowerCase();
                    if (strVal.endsWith(".png") || strVal.endsWith(".jpg") || strVal.endsWith(".jpeg") ||
                        strVal.endsWith(".webp") || strVal.endsWith(".bmp") || strVal.endsWith(".tiff")) {
                        continue;
                    }
                    if (widget.name === "image" || widget.name === "upload") {
                        continue;
                    }

                    console.log("[LK Auto Match] Found missing:", {
                        node: node.title,
                        widget: widget.name,
                        missing_value: value,
                        available_options: options.length
                    });

                    // Infer model type
                    let type = "checkpoints"; // Default
                    const nameLower = widget.name.toLowerCase();

                    if (nameLower.includes("ckpt")) type = "checkpoints";
                    else if (nameLower.includes("vae")) type = "vae";
                    else if (nameLower.includes("lora")) type = "loras";
                    else if (nameLower.includes("control")) type = "controlnet";
                    else if (nameLower.includes("unet")) type = "unet";
                    else if (nameLower.includes("clip")) type = "clip";
                    else if (nameLower.includes("upscale")) type = "upscale_models";
                    else if (nameLower.includes("style")) type = "style_models";

                    missing.push({
                        id: node.id,
                        node_type: node.type,
                        widget_name: widget.name,
                        current: value,
                        type: type
                    });
                }
            }
        }
    }
    return missing;
}

function applyFixes(matches) {
    const graph = app.graph;
    for (const match of matches) {
        const node = graph.getNodeById(match.id);
        if (node) {
            const widget = node.widgets.find(w => w.name === match.widget_name);
            if (widget) {
                widget.value = match.new_value;
                if (widget.callback) {
                    widget.callback(match.new_value);
                }
            }
        }
    }
    graph.setDirtyCanvas(true, true);
}
