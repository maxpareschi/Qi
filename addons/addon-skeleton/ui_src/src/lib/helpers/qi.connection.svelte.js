let session = new URLSearchParams(window.location.search).get("session");

if (!session) {
  session = crypto.randomUUID();
  console.log("Session not found, generating a new one.");
}
console.log("Active session: ", session);

let socket = new WebSocket("ws://127.0.0.1:8000/ws?session=" + session);

export const qiSession = session;
export const qiSocket = socket;
export function qiSend(topic, payload) {
  payload.addon = "addon-skeleton";
  socket.send(JSON.stringify({ topic, payload, session: session }));
}
