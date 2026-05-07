(() => {
  const focusTarget = document.querySelector("[data-focus-on-load='true']");
  if (focusTarget) {
    window.requestAnimationFrame(() => {
      focusTarget.scrollIntoView({ block: "center" });
      focusTarget.focus();
    });
  }

  const form = document.querySelector("[data-async-idea-form]");
  const list = document.querySelector("[data-idea-list]");
  if (!form || !list) return;

  const escapeHtml = (value) =>
    String(value).replace(/[&<>"']/g, (char) => ({
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#39;",
    })[char]);

  const rowHtml = (idea) => `
    <tr data-idea-row>
      <td><strong>${escapeHtml(idea.title)}</strong></td>
      <td><div class="bar-cell"><span style="width: ${Math.min(idea.vote_count * 8, 100)}%"></span>${idea.vote_count}票</div></td>
      <td>
        <div class="row-actions">
          <a class="text-button" href="${idea.detail_url}">詳細</a>
          <button
            class="danger-button"
            type="button"
            data-modal-open="delete-idea-modal"
            data-delete-action="${idea.delete_url}"
            data-delete-title="${escapeHtml(idea.title)}">削除</button>
        </div>
      </td>
    </tr>
  `;

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const submitButton = form.querySelector("button[type='submit']");
    const titleInput = form.elements.title;
    const title = titleInput.value.trim();
    if (!title) {
      titleInput.focus();
      return;
    }

    submitButton.disabled = true;
    try {
      const response = await fetch(form.action || window.location.href, {
        method: "POST",
        body: new FormData(form),
        headers: { "X-Requested-With": "fetch" },
      });
      const data = await response.json();
      if (!response.ok || !data.ok) throw new Error("登録に失敗しました。");

      list.querySelector("[data-empty-row]")?.remove();
      list.insertAdjacentHTML("afterbegin", rowHtml(data.idea));
      form.reset();
      titleInput.focus();
    } catch (error) {
      window.alert(error.message || "登録に失敗しました。");
    } finally {
      submitButton.disabled = false;
    }
  });

  document.addEventListener("click", (event) => {
    const button = event.target.closest("[data-delete-action]");
    if (!button) return;
    const modal = document.getElementById("delete-idea-modal");
    if (!modal) return;
    modal.querySelector("[data-delete-idea-title]").textContent = button.dataset.deleteTitle || "";
    modal.querySelector("[data-delete-idea-form]").action = button.dataset.deleteAction;
  });
})();
