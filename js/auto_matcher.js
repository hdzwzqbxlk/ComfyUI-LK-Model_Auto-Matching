import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

const VERSION = "1.4.0";

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
    content.style.fontFamily = "'Segoe UI', Roboto, Helvetica, Arial, sans-serif";
    content.style.background = "linear-gradient(145deg, #2a2a2a, #1e1e1e)";
    content.style.borderRadius = "12px";
    content.style.padding = "20px";
    content.style.boxShadow = "0 8px 32px rgba(0, 0, 0, 0.5)";
    content.style.border = "1px solid rgba(255, 255, 255, 0.1)";

    // 添加右上角关闭按钮
    const closeBtn = document.createElement("button");
    closeBtn.innerText = "✕";
    closeBtn.title = "Close";
    closeBtn.style.cssText = `
        position: absolute;
        top: 12px;
        right: 12px;
        background: transparent;
        border: none;
        color: rgba(255, 255, 255, 0.6);
        font-size: 16px;
        cursor: pointer;
        z-index: 10;
        padding: 4px;
        border-radius: 50%;
        width: 28px;
        height: 28px;
        display: flex;
        align-items: center;
        justify-content: center;
        transition: all 0.2s ease;
    `;
    closeBtn.onmouseenter = () => {
        closeBtn.style.color = "white";
        closeBtn.style.background = "rgba(255, 255, 255, 0.1)";
    };
    closeBtn.onmouseleave = () => {
        closeBtn.style.color = "rgba(255, 255, 255, 0.6)";
        closeBtn.style.background = "transparent";
    };
    closeBtn.onclick = () => {
        // Find the specific modal container and hide/close it
        // ComfyUI usually appends .comfy-modal
        const modal = content.closest(".comfy-modal");
        if (modal) modal.style.display = "none";
    };
    content.appendChild(closeBtn);

    const h3 = document.createElement("h3");
    h3.innerHTML = `⚙️ 插件设置`;
    h3.style.color = "#eee";
    h3.style.marginTop = "0";
    h3.style.marginBottom = "5px";
    h3.style.fontSize = "18px";
    h3.style.borderBottom = "1px solid rgba(255,255,255,0.1)";
    h3.style.paddingBottom = "10px";
    content.appendChild(h3);

    const desc = document.createElement("p");
    desc.innerText = "配置 API Key 以解决 Civitai 搜索被拦截 (403 Forbidden) 的问题。";
    desc.style.color = "#aaa";
    desc.style.fontSize = "13px";
    desc.style.marginTop = "10px";
    desc.style.lineHeight = "1.4";
    content.appendChild(desc);

    // Form
    const formGroup = document.createElement("div");
    formGroup.style.marginBottom = "20px";
    formGroup.style.marginTop = "15px";

    const label = document.createElement("label");
    label.innerText = "Civitai API Key";
    label.style.display = "block";
    label.style.color = "#ddd";
    label.style.marginBottom = "8px";
    label.style.fontWeight = "600";
    label.style.fontSize = "13px";
    formGroup.appendChild(label);

    const inputContainer = document.createElement("div");
    inputContainer.style.position = "relative";

    const input = document.createElement("input");
    input.type = "password";
    input.placeholder = "Paste your API Key here...";
    input.style.width = "100%";
    input.style.boxSizing = "border-box";
    input.style.padding = "10px 12px";
    input.style.background = "rgba(0, 0, 0, 0.3)";
    input.style.border = "1px solid #444";
    input.style.color = "#eee";
    input.style.borderRadius = "6px";
    input.style.outline = "none";
    input.style.fontSize = "13px";
    input.style.fontFamily = "monospace";
    input.style.transition = "border-color 0.2s, background 0.2s";
    input.onfocus = () => {
        input.style.borderColor = "#64b5f6";
        input.style.background = "rgba(0, 0, 0, 0.5)";
    };
    input.onblur = () => input.style.borderColor = "#444";
    inputContainer.appendChild(input);
    formGroup.appendChild(inputContainer);

    const helpLink = document.createElement("a");
    helpLink.href = "https://civitai.com/user/account";
    helpLink.target = "_blank";
    helpLink.innerText = "👉 Get API Key";
    helpLink.style.display = "block";
    helpLink.style.textAlign = "right";
    helpLink.style.marginTop = "6px";
    helpLink.style.fontSize = "12px";
    helpLink.style.color = "#64b5f6";
    helpLink.style.textDecoration = "none";
    helpLink.style.opacity = "0.8";
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
    btnContainer.style.gap = "12px";
    btnContainer.style.marginTop = "25px";
    content.appendChild(btnContainer);

    // Test Button
    const testBtn = document.createElement("button");
    testBtn.innerHTML = `
        <span style="font-size:14px; margin-right:6px;">🔌</span> 
        <span>Test Connection</span>
    `;
    testBtn.title = "测试 Civitai API Key 是否有效";
    testBtn.style.flex = "1";
    testBtn.style.display = "flex";
    testBtn.style.alignItems = "center";
    testBtn.style.justifyContent = "center";
    testBtn.style.padding = "10px";
    testBtn.style.background = "#37474f";
    testBtn.style.color = "#eceff1";
    testBtn.style.border = "1px solid #455a64";
    testBtn.style.borderRadius = "6px";
    testBtn.style.cursor = "pointer";
    testBtn.style.fontSize = "13px";
    testBtn.style.fontWeight = "600";
    testBtn.style.transition = "all 0.2s ease";

    testBtn.onmouseover = () => {
        testBtn.style.background = "#455a64";
    };
    testBtn.onmouseout = () => {
        testBtn.style.background = "#37474f";
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
        <span style="font-size:14px; margin-right:6px;">💾</span> 
        <span>Save Settings</span>
    `;
    saveBtn.style.flex = "1";
    saveBtn.style.display = "flex";
    saveBtn.style.alignItems = "center";
    saveBtn.style.justifyContent = "center";
    saveBtn.style.padding = "10px";
    saveBtn.style.background = "linear-gradient(135deg, #7c4dff 0%, #651fff 100%)";
    saveBtn.style.color = "white";
    saveBtn.style.border = "none";
    saveBtn.style.borderRadius = "6px";
    saveBtn.style.cursor = "pointer";
    saveBtn.style.fontWeight = "600";
    saveBtn.style.fontSize = "13px";
    saveBtn.style.boxShadow = "0 4px 12px rgba(101, 31, 255, 0.3)";
    saveBtn.style.transition = "all 0.2s ease";

    saveBtn.onmouseover = () => {
        saveBtn.style.transform = "translateY(-1px)";
        saveBtn.style.boxShadow = "0 6px 16px rgba(101, 31, 255, 0.4)";
    };
    saveBtn.onmouseout = () => {
        saveBtn.style.transform = "translateY(0)";
        saveBtn.style.boxShadow = "0 4px 12px rgba(101, 31, 255, 0.3)";
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
            app.ui.dialog.close(); // Close the dialog
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

        // 2. 在线搜索 (针对本地未匹配的项目)
        const matchedNames = new Set(matches.map(m => m.original));
        const stillMissing = missingItems.filter(item => !matchedNames.has(item.current));

        // Update button text to show progress
        if (stillMissing.length > 0) {
            btn.innerHTML = `🌍 Searching online (${stillMissing.length})...`;
        }

        let downloadResults = [];
        if (stillMissing.length > 0) {
            downloadResults = await searchMissingModels(stillMissing, ignoreCache);
        }

        // 3. 计算最终未找到的项目
        // Items found locally
        const foundLocally = new Set(matches.map(m => m.original));
        // Items found online
        const foundOnline = new Set(downloadResults.map(d => d.original));

        const unmatched = missingItems.filter(item =>
            !foundLocally.has(item.current) && !foundOnline.has(item.current)
        );

        showResultsDialog(matches, downloadResults, unmatched);

    } catch (err) {
        console.error("Auto Match Error:", err);
        app.ui.dialog.show("❌ 执行出错: " + err.message);
    } finally {
        btn.innerHTML = originalHTML;
        btn.disabled = false;
        btn.style.cursor = "pointer";
    }
}

// Helper to search missing models online
async function searchMissingModels(missingItems, ignoreCache = false) {
    if (!missingItems || missingItems.length === 0) return [];

    try {
        const response = await api.fetchApi("/auto-matcher/search", {
            method: "POST",
            body: JSON.stringify({
                items: missingItems,
                ignore_cache: ignoreCache
            }),
            headers: { "Content-Type": "application/json" }
        });

        const result = await response.json();
        return result.downloads || [];
    } catch (e) {
        console.error("Search API failed:", e);
        return [];
    }
}

function showResultsDialog(matches, downloadResults, unmatched = []) {
    if (matches.length === 0 && downloadResults.length === 0 && unmatched.length === 0) {
        app.ui.dialog.show("🤷‍♂️ 无匹配结果\n本地未找到替代文件，在线搜索也未命中。建议手动核对 Civitai/HuggingFace。");
        return;
    }

    const content = document.createElement("div");
    content.style.position = "relative";
    content.style.padding = "20px";
    content.style.fontFamily = "'Segoe UI', Roboto, Helvetica, Arial, sans-serif";
    content.style.minWidth = "450px";
    content.style.maxHeight = "80vh";
    content.style.overflowY = "auto";
    content.style.background = "linear-gradient(145deg, #2a2a2a, #1e1e1e)";
    content.style.borderRadius = "12px";
    content.style.boxShadow = "0 10px 40px rgba(0,0,0,0.6)";
    content.style.border = "1px solid rgba(255,255,255,0.08)";
    content.style.color = "#eee";

    // --- HACK: Hide Default Close Button ---
    // Inject a style that hides the button immediately following our content's parent
    const style = document.createElement("style");
    style.innerHTML = `
        .comfy-modal-content > button { display: none !important; } 
    `;
    content.appendChild(style);


    // 添加右上角关闭按钮 X
    const xBtn = document.createElement("button");
    xBtn.innerText = "✕";
    xBtn.title = "Close";
    xBtn.style.cssText = `
        position: absolute;
        top: 12px;
        right: 12px;
        background: transparent;
        border: none;
        color: rgba(255, 255, 255, 0.6);
        font-size: 16px;
        cursor: pointer;
        z-index: 10;
        padding: 4px;
        border-radius: 50%;
        width: 28px;
        height: 28px;
        display: flex;
        align-items: center;
        justify-content: center;
        transition: all 0.2s ease;
    `;
    xBtn.onmouseenter = () => {
        xBtn.style.color = "white";
        xBtn.style.background = "rgba(255, 255, 255, 0.1)";
    };
    xBtn.onmouseleave = () => {
        xBtn.style.color = "rgba(255, 255, 255, 0.6)";
        xBtn.style.background = "transparent";
    };
    xBtn.onclick = () => {
        const modal = content.closest(".comfy-modal");
        if (modal) modal.style.display = "none";
    };
    content.appendChild(xBtn);

    // Header logic
    const totalCount = matches.length + downloadResults.length + unmatched.length;
    const h2 = document.createElement("h2");
    h2.innerText = `Auto Match Results (${totalCount})`;
    h2.style.margin = "0 0 15px 0";
    h2.style.fontSize = "20px";
    h2.style.fontWeight = "600";
    h2.style.color = "white";
    content.appendChild(h2);

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
        h3.innerHTML = `✅ 本地匹配 <span style="font-size:12px; font-weight:normal; opacity:0.7">(${matches.length})</span>`;
        h3.style.color = "#81c784";
        h3.style.borderBottom = "1px solid rgba(129, 199, 132, 0.3)";
        h3.style.paddingBottom = "6px";
        h3.style.marginTop = "5px";
        h3.style.fontSize = "15px";
        content.appendChild(h3);

        const groups = groupByType(matches);
        for (const [type, items] of Object.entries(groups)) {
            // Category Header
            const catHeader = document.createElement("div");
            catHeader.innerText = type.toUpperCase().replace("_", " ");
            catHeader.style.fontSize = "11px";
            catHeader.style.color = "#ccc";
            catHeader.style.marginTop = "10px";
            catHeader.style.fontWeight = "700";
            catHeader.style.background = "rgba(255,255,255,0.06)";
            catHeader.style.padding = "4px 8px";
            catHeader.style.borderRadius = "4px";
            catHeader.style.display = "inline-block";
            content.appendChild(catHeader);

            const ul = document.createElement("ul");
            ul.style.paddingLeft = "0";
            ul.style.marginTop = "8px";
            ul.style.listStyle = "none";
            items.forEach(m => {
                const li = document.createElement("li");
                li.style.marginTop = "6px";
                li.style.background = "rgba(0,0,0,0.2)";
                li.style.padding = "8px 10px";
                li.style.borderRadius = "6px";
                li.style.border = "1px solid rgba(255,255,255,0.03)";
                li.innerHTML = `
                    <div style="font-size:12px; color:#aaa; text-decoration:line-through; margin-bottom:2px;">${m.original}</div>
                    <div style="color:#a5d6a7; font-weight:600; font-size:13px; display:flex; align-items:center;">
                        <span style="margin-right:6px;">↪</span> ${m.new_value}
                    </div>
                `;
                ul.appendChild(li);
            });
            content.appendChild(ul);
        }
    }

    // --- Online Results Section ---
    if (downloadResults.length > 0) {
        const h3 = document.createElement("h3");
        h3.innerHTML = `🌐 在线资源 <span style="font-size:12px; font-weight:normal; opacity:0.7">(${downloadResults.length})</span>`;
        h3.style.color = "#64b5f6";
        h3.style.borderBottom = "1px solid rgba(100, 181, 246, 0.3)";
        h3.style.paddingBottom = "6px";
        h3.style.marginTop = "25px";
        h3.style.fontSize = "15px";
        content.appendChild(h3);

        const groups = groupByType(downloadResults);
        for (const [type, items] of Object.entries(groups)) {
            // Category Header
            const catHeader = document.createElement("div");
            catHeader.innerText = type.toUpperCase().replace("_", " ");
            catHeader.style.fontSize = "11px";
            catHeader.style.color = "#ccc";
            catHeader.style.marginTop = "10px";
            catHeader.style.fontWeight = "700";
            catHeader.style.background = "rgba(255,255,255,0.06)";
            catHeader.style.padding = "4px 8px";
            catHeader.style.borderRadius = "4px";
            catHeader.style.display = "inline-block";
            content.appendChild(catHeader);

            const ul = document.createElement("ul");
            ul.style.paddingLeft = "0";
            ul.style.marginTop = "8px";
            ul.style.listStyle = "none";
            items.forEach(d => {
                const li = document.createElement("li");
                li.style.marginTop = "6px";
                li.style.background = "rgba(0,0,0,0.2)";
                li.style.padding = "8px 10px";
                li.style.borderRadius = "6px";
                li.style.border = "1px solid rgba(255,255,255,0.03)";
                li.innerHTML = `
                    <div style="font-weight:600; margin-bottom:6px; color:#ffcc80; font-size:13px;">${d.original}</div>
                    <div style="display:flex; gap:8px; flex-wrap:wrap;">
                        <a href="${d.result.url}" target="_blank" style="
                            display: inline-flex;
                            align-items: center;
                            background: rgba(33, 150, 243, 0.85);
                            color: white;
                            text-decoration: none;
                            padding: 5px 12px;
                            border-radius: 4px;
                            font-size: 12px;
                            font-weight: 500;
                            transition: background 0.2s;
                        " onmouseover="this.style.background='#1976d2'" onmouseout="this.style.background='rgba(33, 150, 243, 0.85)'">⬇ 下载/Download (${d.result.source})</a>

                        ${d.result.pageUrl ? `
                        <a href="${d.result.pageUrl}" target="_blank" style="
                            display: inline-flex;
                            align-items: center;
                            background: rgba(255, 255, 255, 0.1);
                            color: #ccc;
                            text-decoration: none;
                            padding: 5px 12px;
                            border: 1px solid rgba(255, 255, 255, 0.15);
                            border-radius: 4px;
                            font-size: 12px;
                            transition: all 0.2s;
                        " onmouseover="this.style.color='white';this.style.borderColor='#999';this.style.background='rgba(255,255,255,0.2)'" onmouseout="this.style.color='#ccc';this.style.borderColor='rgba(255, 255, 255, 0.15)';this.style.background='rgba(255, 255, 255, 0.1)'">🌍 主页/Page</a>
                        ` : ''}
                    </div>
                `;
                ul.appendChild(li);
            });
            content.appendChild(ul);
        }
    }

    // --- Unmatched Section (New) ---
    if (unmatched.length > 0) {
        const h3 = document.createElement("h3");
        h3.innerHTML = `❌ 未找到 <span style="font-size:12px; font-weight:normal; opacity:0.7">(${unmatched.length})</span>`;
        h3.style.color = "#ef5350";
        h3.style.borderBottom = "1px solid rgba(239, 83, 80, 0.3)";
        h3.style.paddingBottom = "6px";
        h3.style.marginTop = "25px";
        h3.style.fontSize = "15px";
        content.appendChild(h3);

        const groups = groupByType(unmatched);
        for (const [type, items] of Object.entries(groups)) {
            // Category Header
            const catHeader = document.createElement("div");
            catHeader.innerText = type.toUpperCase().replace("_", " ");
            catHeader.style.fontSize = "11px";
            catHeader.style.color = "#ccc";
            catHeader.style.marginTop = "10px";
            catHeader.style.fontWeight = "700";
            catHeader.style.background = "rgba(255,255,255,0.06)";
            catHeader.style.padding = "4px 8px";
            catHeader.style.borderRadius = "4px";
            catHeader.style.display = "inline-block";
            content.appendChild(catHeader);

            const ul = document.createElement("ul");
            ul.style.paddingLeft = "0";
            ul.style.marginTop = "8px";
            ul.style.listStyle = "none";
            items.forEach(u => {
                const li = document.createElement("li");
                li.style.marginTop = "6px";
                li.style.background = "rgba(255, 0, 0, 0.1)"; // Slight red tint
                li.style.padding = "8px 10px";
                li.style.borderRadius = "6px";
                li.style.border = "1px solid rgba(239, 83, 80, 0.15)";
                li.innerHTML = `
                     <div style="font-weight:600; color:#ffcdd2; font-size:13px; word-break:break-all;">${u.current}</div>
                     <div style="font-size:11px; color:#aaa; margin-top:4px;">⚠️ 搜遍全网也没找到，请检查文件名拼写。</div>
                 `;
                ul.appendChild(li);
            });
            content.appendChild(ul);
        }
    }

    // --- Action Buttons ---
    const actionsBar = document.createElement("div");
    actionsBar.style.display = "flex";
    actionsBar.style.gap = "12px";
    actionsBar.style.marginTop = "25px";
    actionsBar.style.borderTop = "1px solid rgba(255,255,255,0.1)";
    actionsBar.style.paddingTop = "15px";

    if (matches.length > 0) {
        const confirmBtn = document.createElement("button");
        confirmBtn.innerHTML = "🚀 应用所有本地修复";
        confirmBtn.style.cssText = `
                flex: 2;
                padding: 12px;
                background: linear-gradient(135deg, #43a047 0%, #2e7d32 100%);
                color: white;
                border: none;
                border-radius: 6px;
                cursor: pointer;
                font-weight: 600;
                font-size: 14px;
                box-shadow: 0 4px 6px rgba(0, 0, 0, 0.2);
                transition: transform 0.1s, box-shadow 0.2s;
                `;
        confirmBtn.onmousedown = () => confirmBtn.style.transform = "scale(0.98)";
        confirmBtn.onmouseup = () => confirmBtn.style.transform = "scale(1)";

        confirmBtn.onclick = () => {
            applyFixes(matches);
            confirmBtn.innerHTML = "✅ 已应用 / Fixed";
            confirmBtn.disabled = true;
            confirmBtn.style.background = "#444";
            confirmBtn.style.color = "#aaa";
            confirmBtn.style.cursor = "default";
            confirmBtn.style.boxShadow = "none";
        };
        actionsBar.appendChild(confirmBtn);
    }

    // 再次网络筛选按钮
    const retryBtn = document.createElement("button");
    retryBtn.innerHTML = "🔄 再次网络筛选";
    retryBtn.title = "强制忽略缓存，重新搜索在线资源";
    retryBtn.style.cssText = `
                flex: 1;
                padding: 12px;
                background: linear-gradient(135deg, #2196f3 0%, #1976d2 100%);
                color: white;
                border: none;
                border-radius: 6px;
                cursor: pointer;
                font-weight: 600;
                font-size: 14px;
                box-shadow: 0 4px 6px rgba(0, 0, 0, 0.2);
                white-space: nowrap;
                transition: transform 0.1s, box-shadow 0.2s;
                `;
    retryBtn.onmousedown = () => retryBtn.style.transform = "scale(0.98)";
    retryBtn.onmouseup = () => retryBtn.style.transform = "scale(1)";

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

                    // FIX: Ignore Image/Video/Config Uploads (don't try to match user inputs)
                    const strVal = String(value).toLowerCase();
                    const ignoredExts = [
                        // Images
                        ".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff", ".gif",
                        // Videos
                        ".mp4", ".mov", ".avi", ".mkv", ".webm",
                        // Config/Text
                        ".txt", ".md", ".json", ".yaml", ".yml", ".ini",
                        // Archives
                        ".zip", ".rar", ".7z", ".tar", ".gz"
                    ];

                    if (ignoredExts.some(ext => strVal.endsWith(ext))) {
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
