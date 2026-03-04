/* webui/static/chat.js — chat UI logic */
(function () {
  "use strict";

  const log  = document.getElementById("log");
  const goal = document.getElementById("goal");
  const send = document.getElementById("send");

  function addMsg(type, text) {
    const labels = {
      user:    "You",
      thought: "💭 Thought",
      command: "💻 Command",
      output:  "📤 Output",
      done:    "✅ Done",
      error:   "❌ Error",
    };
    const div = document.createElement("div");
    div.className = "msg " + type;
    if (labels[type]) {
      const lbl = document.createElement("div");
      lbl.className = "label";
      lbl.textContent = labels[type];
      div.appendChild(lbl);
    }
    const body = document.createElement("div");
    body.textContent = text;
    div.appendChild(body);
    log.appendChild(div);
    log.scrollTop = log.scrollHeight;
    return div;
  }

  async function runGoal(goalText) {
    send.disabled = true;
    goal.disabled = true;

    addMsg("user", goalText);

    try {
      const res = await fetch("/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ goal: goalText }),
      });

      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        addMsg("error", body.error || "Request failed: " + res.status);
        return;
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop(); // keep incomplete last line
        for (const line of lines) {
          const trimmed = line.trim();
          if (!trimmed) continue;
          try {
            const evt = JSON.parse(trimmed);
            addMsg(evt.type, evt.data);
          } catch {
            // ignore malformed lines
          }
        }
      }
    } catch (err) {
      addMsg("error", "Network error: " + err.message);
    } finally {
      send.disabled = false;
      goal.disabled = false;
      goal.focus();
    }
  }

  send.addEventListener("click", () => {
    const text = goal.value.trim();
    if (!text) return;
    goal.value = "";
    runGoal(text);
  });

  goal.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send.click();
    }
  });

  goal.focus();
})();
