import { browser } from "$app/environment";
import { windowState } from "$lib/states/qi.windowState.svelte";

export const qiConnection = $state({
  session: null,
  addon: null,
  socket: null,
  send: () => {},
});

export const initQiConnection = () => {
  let session = sessionStorage.getItem("qiSession");
  if (!session) {
    const params = new URLSearchParams(location.search);
    session = params.get("session") ?? crypto.randomUUID();
    sessionStorage.setItem("qiSession", session);
  }
  qiConnection.session = session;

  let addon = sessionStorage.getItem("qiAddon");
  if (!addon) {
    addon = location.pathname.split("/").filter(Boolean)[0] ?? "";
    sessionStorage.setItem("qiAddon", addon);
  }
  qiConnection.addon = addon;

  if (!window.__qiConnection) {
    const ws = new WebSocket(`ws://127.0.0.1:8000/ws?session=${session}`);
    ws.addEventListener("open", () => {
      // console.log("WebSocket opened once:", {
      //   session: session,
      //   addon: addon,
      //   socket: ws,
      // });
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
};
