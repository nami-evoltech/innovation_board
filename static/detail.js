const form = document.querySelector(".autosave-form");
const statusEl = document.querySelector("[data-autosave-status]");
let saveTimer;
let activeRequest;

function setStatus(message, state = "") {
  if (!statusEl) return;
  statusEl.textContent = message;
  statusEl.dataset.state = state;
}

async function autosave() {
  if (!form) return;
  if (activeRequest) activeRequest.abort();

  activeRequest = new AbortController();
  setStatus("保存中...", "saving");

  try {
    const response = await fetch(form.action, {
      method: "POST",
      body: new FormData(form),
      headers: { "X-Requested-With": "fetch" },
      signal: activeRequest.signal
    });

    if (!response.ok) throw new Error("Autosave failed");
    const result = await response.json();
    setStatus(`保存済み ${result.updated_at}`, "saved");
  } catch (error) {
    if (error.name === "AbortError") return;
    setStatus("自動保存できませんでした", "error");
  }
}

if (form) {
  form.addEventListener("input", () => {
    setStatus("編集中...", "editing");
    window.clearTimeout(saveTimer);
    saveTimer = window.setTimeout(autosave, 800);
  });

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    window.clearTimeout(saveTimer);
    autosave();
  });
}
