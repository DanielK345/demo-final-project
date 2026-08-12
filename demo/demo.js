// Demo UI client — Phần 7 (docs/voice_ai_overview.md §4/§5).
//
// Nói chuyện đúng theo protocol định nghĩa trong src/models/voice_schemas.py
// (WSServerEvent / WSClientControl) — xem docstring đầu src/api/voice_routes.py
// để biết mô tả đầy đủ. Không dùng framework/build step, chỉ vanilla JS để
// dễ chạy trực tiếp (mở qua static file server của FastAPI, xem src/main.py).

const WS_PATH = "/api/v1/voice/stream";

const STAGE_LABELS = {
  IDLE: "⏸️ Chờ",
  LISTENING: "🎙️ Đang nghe",
  PROCESSING: "⚙️ Đang xử lý",
  SPEAKING: "🔊 AloSM đang nói",
  HANDED_OFF: "📞 Đã chuyển tổng đài viên",
  ENDED: "⏹️ Đã kết thúc cuộc gọi",
};

const els = {
  callButton: document.getElementById("call-button"),
  status: document.getElementById("status"),
  transcript: document.getElementById("transcript"),
};

let ws = null;
let audioContext = null;
let workletNode = null;
let micStream = null;
let pendingAudioMeta = null;
const playbackQueue = [];
let isPlayingAudio = false;

function setStatus(stageOrMessage) {
  els.status.textContent = STAGE_LABELS[stageOrMessage] || stageOrMessage;
}

function appendTranscript(who, text) {
  if (!text) return;
  const line = document.createElement("p");
  line.className = `line ${who}`;
  line.textContent = (who === "user" ? "🧑 Bạn: " : "🤖 AloSM: ") + text;
  els.transcript.appendChild(line);
  els.transcript.scrollTop = els.transcript.scrollHeight;
}

function wsUrl() {
  const scheme = location.protocol === "https:" ? "wss" : "ws";
  return `${scheme}://${location.host}${WS_PATH}`;
}

async function startCall() {
  els.transcript.innerHTML = "";
  setStatus("Đang xin quyền microphone…");

  micStream = await navigator.mediaDevices.getUserMedia({ audio: { channelCount: 1 } });

  audioContext = new AudioContext();
  await audioContext.audioWorklet.addModule("pcm-worklet.js");

  const source = audioContext.createMediaStreamSource(micStream);
  workletNode = new AudioWorkletNode(audioContext, "pcm-capture-processor");
  source.connect(workletNode);
  // Không nối workletNode -> destination: không cần nghe lại chính giọng mình.

  ws = new WebSocket(wsUrl());
  ws.binaryType = "arraybuffer";

  ws.addEventListener("open", () => {
    ws.send(
      JSON.stringify({
        type: "start_call",
        payload: { sample_rate: audioContext.sampleRate, channel: "WEB_VOICE" },
      })
    );
    workletNode.port.onmessage = (event) => {
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(event.data); // ArrayBuffer PCM16, binary WS frame
      }
    };
  });

  ws.addEventListener("message", (event) => {
    if (typeof event.data === "string") {
      handleServerEvent(JSON.parse(event.data));
    } else {
      handleAudioFrame(event.data);
    }
  });

  ws.addEventListener("close", () => {
    setStatus("ENDED");
    stopCapture();
    setCallButtonState("idle");
  });

  ws.addEventListener("error", () => {
    appendTranscript("agent", "[Mất kết nối WebSocket]");
  });

  setCallButtonState("in-call");
}

function endCall() {
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ type: "end_call", payload: {} }));
    ws.close();
  }
  stopCapture();
  setCallButtonState("idle");
}

function stopCapture() {
  if (micStream) {
    micStream.getTracks().forEach((track) => track.stop());
    micStream = null;
  }
  if (workletNode) {
    workletNode.disconnect();
    workletNode = null;
  }
  if (audioContext) {
    audioContext.close();
    audioContext = null;
  }
}

function setCallButtonState(state) {
  els.callButton.dataset.state = state;
  els.callButton.textContent = state === "in-call" ? "Kết thúc" : "Gọi";
}

function handleServerEvent(evt) {
  switch (evt.type) {
    case "session_ready":
      setStatus("LISTENING");
      break;
    case "status":
      setStatus(evt.payload.stage);
      break;
    case "transcript":
      appendTranscript("user", evt.payload.text);
      break;
    case "agent_message":
      appendTranscript("agent", evt.payload.text);
      break;
    case "audio_meta":
      pendingAudioMeta = evt.payload;
      break;
    case "handoff":
      appendTranscript("agent", `[Đã chuyển tổng đài viên — ${evt.payload.summary || evt.payload.reason}]`);
      break;
    case "error":
      appendTranscript("agent", `[Lỗi: ${evt.payload.message}]`);
      break;
    case "session_ended":
      setStatus("ENDED");
      break;
    default:
      console.warn("Unknown event type:", evt.type);
  }
}

function handleAudioFrame(arrayBuffer) {
  const mimeType = (pendingAudioMeta && pendingAudioMeta.mime_type) || "audio/mpeg";
  pendingAudioMeta = null;
  playbackQueue.push({ arrayBuffer, mimeType });
  if (!isPlayingAudio) playNextInQueue();
}

function playNextInQueue() {
  const item = playbackQueue.shift();
  if (!item) {
    isPlayingAudio = false;
    return;
  }
  isPlayingAudio = true;
  const blobUrl = URL.createObjectURL(new Blob([item.arrayBuffer], { type: item.mimeType }));
  const audio = new Audio(blobUrl);
  const cleanup = () => {
    URL.revokeObjectURL(blobUrl);
    playNextInQueue();
  };
  audio.addEventListener("ended", cleanup);
  audio.addEventListener("error", cleanup);
  audio.play().catch((err) => {
    console.error("Không phát được audio TTS:", err);
    cleanup();
  });
}

els.callButton.addEventListener("click", () => {
  if (els.callButton.dataset.state === "in-call") {
    endCall();
  } else {
    startCall().catch((err) => {
      console.error(err);
      setStatus("Lỗi mở microphone");
      appendTranscript("agent", `[Không mở được microphone: ${err.message}]`);
      setCallButtonState("idle");
    });
  }
});
