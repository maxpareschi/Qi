import { browser } from "$app/environment";

export const qiConnection = $state({
  session: null,
  addon: null,
  socket: null,
  send: () => {},
});

export function initQiConnection() {
  if (!browser) return;

  let sess = sessionStorage.getItem("qiSession");
  if (!sess) {
    const params = new URLSearchParams(location.search);
    sess = params.get("session") ?? crypto.randomUUID();
    sessionStorage.setItem("qiSession", sess);
  }
  qiConnection.session = sess;

  let add = sessionStorage.getItem("qiAddon");
  if (!add) {
    add = location.pathname.split("/").filter(Boolean)[0] ?? "";
    sessionStorage.setItem("qiAddon", add);
  }
  qiConnection.addon = add;

  if (!window.__qiConnection) {
    const ws = new WebSocket(`ws://127.0.0.1:8000/ws/${sess}`);
    ws.addEventListener("open", () => {
      console.log("WebSocket opened once:", { session: sess, addon: add });
    });
    window.__qiConnection = ws;
  }
  qiConnection.socket = window.__qiConnection;

  qiConnection.send = (topic, payload = {}) => {
    payload.addon = qiConnection.addon;
    qiConnection.socket.send(
      JSON.stringify({
        topic,
        payload,
        session: qiConnection.session,
      })
    );
  };
}
