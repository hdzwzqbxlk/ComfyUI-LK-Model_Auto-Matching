import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

app.registerExtension({
    name: "Comfy.AutoModelMatcher",
    async setup() {
        const menu = document.querySelector(".comfy-menu");
        
        const autoMatchBtn = document.createElement("button");
        autoMatchBtn.textContent = "Auto Match Models";
        autoMatchBtn.onclick = async () => {
            const missingItems = findMissingModels();
            if (missingItems.length === 0) {
                alert("No missing models found!");
                return;
            }

            // Show scanning status
            autoMatchBtn.textContent = "Scanning...";
            autoMatchBtn.disabled = true;

            try {
                const response = await api.fetchApi("/auto-matcher/match", {
                    method: "POST",
                    body: JSON.stringify({ items: missingItems }),
                    headers: { "Content-Type": "application/json" }
                });

                const result = await response.json();
                
                if (result.matches && result.matches.length > 0) {
                    if (confirm(`Found ${result.matches.length} matches. Apply fixes?\n\n` + 
                                result.matches.map(m => `${m.original} -> ${m.new_value}`).join("\n"))) {
                        applyFixes(result.matches);
                        alert("Models updated!");
                    }
                } else {
                    alert("No matching local models found for the missing items.");
                }

            } catch (err) {
                console.error("Auto Match Error:", err);
                alert("Error during matching: " + err.message);
            } finally {
                autoMatchBtn.textContent = "Auto Match Models";
                autoMatchBtn.disabled = false;
            }
        };

        // Insert before the generic "Queue Prompt" or just append
        menu.append(autoMatchBtn);
    }
});

function findMissingModels() {
    const missing = [];
    const graph = app.graph;
    
    for (const node of graph._nodes) {
        if (!node.widgets) continue;

        for (const widget of node.widgets) {
            // Check if it's a combo widget (model selectors are usually combos)
            if (widget.type === "COMBO" || widget.type === "customtext") { // Sometimes custom widgets use custom types, but standard is COMBO
                const value = widget.value;
                const options = widget.options ? widget.options.values : null;

                // If options exist and the current value is NOT in the list, it's missing
                if (Array.isArray(options) && options.length > 0 && !options.includes(value)) {
                    
                    // Infer model type from widget name (heuristic)
                    // Common names: ckpt_name, vae_name, lora_name, control_net_name
                    let type = "unknown";
                    if (widget.name.includes("ckpt")) type = "checkpoints";
                    else if (widget.name.includes("vae")) type = "vae";
                    else if (widget.name.includes("lora")) type = "loras";
                    else if (widget.name.includes("control")) type = "controlnet";
                    else if (widget.name.includes("unet")) type = "unet";
                    else if (widget.name.includes("clip")) type = "clip";
                    else {
                        // Fallback: try to pass "checkpoints" as default or let backend search all
                        // For MVP let's default to checkpoints if unknown, or maybe send null
                        type = "checkpoints"; 
                    }

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
                // Trigger callback if exists (some nodes update internal state)
                if (widget.callback) {
                    widget.callback(match.new_value);
                }
            }
        }
    }
    graph.setDirtyCanvas(true, true);
}
