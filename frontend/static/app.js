/* VibeQA 前端（原生 JS，无构建）
 * 对接后端 /api/v1：subjects、conversations、chat、chat/stream(SSE)、health
 */
"use strict";

const $ = (s) => document.querySelector(s);
const state = {
  subject: null,
  mode: "sync",
  busy: false,
  conversations: [],
};

/* ---------------- 工具 ---------------- */

async function api(path, options = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (res.status === 204) return null;
  const ct = res.headers.get("content-type") || "";
  const data = ct.includes("application/json") ? await res.json() : await res.text();
  if (!res.ok) {
    const msg = typeof data === "object" ? data.detail || res.status : data;
    throw new Error(msg);
  }
  return data;
}

const fmtTime = () =>
  new Date().toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" });

function el(tag, cls, text) {
  const node = document.createElement(tag);
  if (cls) node.className = cls;
  if (text !== undefined) node.textContent = text;
  return node;
}

/* ---------------- 渲染：消息 ---------------- */

const messagesBox = $("#messages");

function addMsg(role, text, sources = []) {
  const row = el("div", `msg ${role}`);
  const bubble = el("div", "bubble");
  const body = el("div", "body");
  body.textContent = text;
  bubble.appendChild(body);
  if (sources && sources.length) {
    const chips = el("div", "sources");
    sources.forEach((s) => {
      chips.appendChild(
        el("span", "src-chip", `${s.title || "来源"}${s.page ? " · 第" + s.page + "页" : ""}`)
      );
    });
    bubble.appendChild(chips);
  }
  row.appendChild(bubble);
  row.appendChild(el("span", "time", fmtTime()));
  messagesBox.appendChild(row);
  messagesBox.scrollTop = messagesBox.scrollHeight;
  return row;
}

function clearWelcome() {
  const w = messagesBox.querySelector(".welcome");
  if (w) w.remove();
}

/* ---------------- 学科选择 ---------------- */

async function loadSubjects() {
  const list = await api("/api/v1/subjects");
  const box = $("#subject-chips");
  box.innerHTML = "";
  list.forEach((s) => {
    const chip = el("span", "chip", s.name);
    chip.dataset.code = s.code;
    chip.onclick = () => selectSubject(s.code);
    box.appendChild(chip);
  });
  const preferred = list.some((s) => s.code === "ai") ? "ai" : list[0].code;
  selectSubject(preferred);
}

function selectSubject(code) {
  state.subject = code;
  document.querySelectorAll("#subject-chips .chip").forEach((c) => {
    c.classList.toggle("active", c.dataset.code === code);
  });
}

/* ---------------- 会话管理 ---------------- */

const convList = $("#conv-list");

async function loadConversations() {
  const list = await api("/api/v1/conversations");
  state.conversations = list;
  renderConversations();
}

function renderConversations() {
  convList.innerHTML = "";
  state.conversations.forEach((c) => {
    const item = el("div", "conv-item");
    item.dataset.id = c.id;
    const title = el("span", "title", c.title || "新会话");
    const meta = el("span", "meta", c.message_count || "");
    const del = el("button", "conv-del", "✕");
    del.title = "清除会话";
    del.onclick = async (e) => {
      e.stopPropagation();
      if (!confirm("确认清除该会话及其全部消息？")) return;
      await api(`/api/v1/conversations/${c.id}`, { method: "DELETE" });
      await loadConversations();
      if (state.convId === c.id) {
        state.convId = null;
        messagesBox.innerHTML = "";
        showWelcome();
      }
    };
    item.appendChild(title);
    item.appendChild(meta);
    item.appendChild(del);
    item.onclick = () => openConversation(c.id);
    if (state.convId === c.id) item.classList.add("active");
    convList.appendChild(item);
  });
}

function showWelcome() {
  const w = el("div", "welcome");
  w.appendChild(el("h2", null, "你好，我是 AI 助教 👋"));
  w.appendChild(el("p", null, "点击左侧会话查看历史，或直接在下方输入问题开始提问。"));
  messagesBox.appendChild(w);
}

async function openConversation(id) {
  state.convId = id;
  renderConversations();
  messagesBox.innerHTML = "";
  const data = await api(`/api/v1/conversations/${id}/messages`);
  const msgs = (data.messages || []).slice().reverse(); // 接口倒序，转正序展示
  msgs.forEach((m) => addMsg(m.role, m.content, m.sources || []));
  if (!msgs.length) showWelcome();
}

async function newConversation() {
  const created = await api("/api/v1/conversations", {
    method: "POST",
    body: JSON.stringify({ title: "新会话" }),
  });
  await loadConversations();
  openConversation(created.id);
}

/* ---------------- 问答 ---------------- */

const inputBox = $("#input");
const sendBtn = $("#btn-send");
const tip = $("#composer-tip");

function setBusy(on) {
  state.busy = on;
  sendBtn.disabled = on;
  inputBox.disabled = on;
}

function autosize() {
  inputBox.style.height = "auto";
  inputBox.style.height = Math.min(inputBox.scrollHeight, 140) + "px";
}

async function onSend() {
  const q = inputBox.value.trim();
  if (!q || state.busy) return;
  inputBox.value = "";
  autosize();
  setBusy(true);
  clearWelcome();
  try {
    if (state.mode === "stream") await streamAsk(q);
    else await askPersist(q);
  } catch (e) {
    addMsg("assistant", "请求失败：" + e.message);
  } finally {
    setBusy(false);
    inputBox.focus();
  }
}

/* 即时回答：写入当前会话（无会话则先建） */
async function askPersist(q) {
  if (!state.convId) {
    const created = await api("/api/v1/conversations", {
      method: "POST",
      body: JSON.stringify({ title: q.slice(0, 50) }),
    });
    state.convId = created.id;
  }
  addMsg("user", q);
  const body = JSON.stringify({ query: q, subject: state.subject });
  const res = await api(`/api/v1/conversations/${state.convId}/messages`, {
    method: "POST",
    body,
  });
  addMsg("assistant", res.answer, res.sources || []);
  await loadConversations(); // 刷新标题与消息数
}

/* 流式回答：走 /chat/stream(SSE)，本演示不写会话历史 */
async function streamAsk(q) {
  addMsg("user", q);
  const row = el("div", "msg assistant");
  const bubble = el("div", "bubble");
  const text = el("span", "body");
  const cursor = el("span", "cursor", "");
  bubble.appendChild(text);
  bubble.appendChild(cursor);
  row.appendChild(bubble);
  row.appendChild(el("span", "time", fmtTime()));
  messagesBox.appendChild(row);
  messagesBox.scrollTop = messagesBox.scrollHeight;

  const acc = [];
  let sourcesEl = null;
  const flushText = () => {
    text.textContent = acc.join("");
    messagesBox.scrollTop = messagesBox.scrollHeight;
  };

  const resp = await fetch("/api/v1/chat/stream", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query: q, subject: state.subject }),
  });
  if (!resp.ok || !resp.body) throw new Error("流式请求失败 " + resp.status);

  const reader = resp.body.getReader();
  const dec = new TextDecoder();

  // 逐行解析 SSE：事件以空行分隔（服务器用 CRLF），data 可能跨多行
  let buf = "";
  let current = { event: "message", lines: [] };

  const dispatch = () => {
    const data = current.lines.join("\n");
    const event = current.event;
    current = { event: "message", lines: [] };
    if (event === "sources") {
      let list = [];
      try { list = JSON.parse(data || "[]"); } catch { list = []; }
      if (list.length && !sourcesEl) {
        sourcesEl = el("div", "sources");
        list.forEach((s) =>
          sourcesEl.appendChild(
            el("span", "src-chip", `${s.title || "来源"}${s.page ? " · 第" + s.page + "页" : ""}`)
          )
        );
        bubble.appendChild(sourcesEl);
        messagesBox.scrollTop = messagesBox.scrollHeight;
      }
    } else if (event === "message") {
      if (data) { acc.push(data); flushText(); }
    } else if (event === "done") {
      cursor.remove();
    }
  };

  const pump = () => {
    let idx;
    while ((idx = buf.indexOf("\n")) >= 0) {
      let line = buf.slice(0, idx);
      buf = buf.slice(idx + 1);
      if (line.endsWith("\r")) line = line.slice(0, -1);
      if (line === "") {
        if (current.lines.length || current.event !== "message") dispatch();
      } else if (line.startsWith("event:")) {
        current.event = line.slice(6).trim();
      } else if (line.startsWith("data:")) {
        current.lines.push(line.slice(5).replace(/^ /, ""));
      }
      // 注释行(以":"开头)忽略
    }
  };

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += dec.decode(value, { stream: true });
    pump();
  }
  buf += dec.decode(); // 冲刷多字节残留
  pump();
  if (current.lines.length || current.event !== "message") dispatch(); // 末尾无空行事件
  if (acc.length === 0) {
    cursor.remove();
    text.textContent = "(空回复)";
  }
}

/* ---------------- 状态与启动 ---------------- */

async function refreshHealth() {
  const dot = $("#health-dot");
  const txt = $("#health-text");
  try {
    const h = await api("/api/v1/health");
    dot.className = "dot " + (h.status === "ok" ? "ok" : "bad");
    txt.textContent = h.status === "ok" ? "服务正常" : "服务降级";
  } catch {
    dot.className = "dot bad";
    txt.textContent = "后端不可达";
  }
}

function bind() {
  sendBtn.onclick = onSend;
  inputBox.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      onSend();
    }
  });
  inputBox.addEventListener("input", autosize);
  $("#btn-new").onclick = newConversation;

  document.querySelectorAll(".mode input").forEach((r) => {
    r.onchange = () => {
      state.mode = r.value;
      tip.textContent =
        r.value === "stream" ? "流式回答实时逐字输出（当前演示不写入会话历史）" : "";
    };
  });
}

(async function init() {
  bind();
  await loadSubjects();
  try {
    await loadConversations();
  } catch (e) {
    // 后端/库不可用时允许继续显示欢迎页，健康灯会提示
    console.error(e);
  }
  refreshHealth();
  setInterval(refreshHealth, 30000);
  inputBox.focus();
})();
