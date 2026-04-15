let controls = null;
let active = false;
let videoTrack = null;
let torchOn = false;

const Streamlit = window.Streamlit || {
  setComponentReady: () => {
    window.parent.postMessage(
      { isStreamlitMessage: true, type: "streamlit:componentReady", apiVersion: 1 },
      "*"
    );
  },
  setFrameHeight: (height) => {
    window.parent.postMessage(
      { isStreamlitMessage: true, type: "streamlit:setFrameHeight", height },
      "*"
    );
  },
  setComponentValue: (value) => {
    window.parent.postMessage(
      {
        isStreamlitMessage: true,
        type: "streamlit:setComponentValue",
        value,
        dataType: "json"
      },
      "*"
    );
  },
  RENDER_EVENT: "streamlit:render",
  events: {
    addEventListener: (type, callback) => {
      window.addEventListener("message", (event) => {
        if (event.data && event.data.type === type) {
          callback(event);
        }
      });
    }
  }
};

const lastEl = document.getElementById("last");
const errorEl = document.getElementById("error");
const videoEl = document.getElementById("video");
const torchButton = document.getElementById("btnTorch");

function setHeight() {
  Streamlit.setFrameHeight(520);
}

function setStatus(message, isError = false) {
  if (isError) {
    errorEl.textContent = message;
    return;
  }

  lastEl.textContent = message;
  errorEl.textContent = "";
}

function resetTorchButton() {
  torchOn = false;
  videoTrack = null;
  torchButton.disabled = true;
  torchButton.textContent = "Linterna";
}

function getActiveVideoTrack() {
  const stream = videoEl.srcObject;
  if (!stream || !stream.getVideoTracks) return null;

  const tracks = stream.getVideoTracks();
  return tracks.length > 0 ? tracks[0] : null;
}

function setupTorchButton() {
  videoTrack = getActiveVideoTrack();
  const capabilities = videoTrack && videoTrack.getCapabilities
    ? videoTrack.getCapabilities()
    : {};

  if (!videoTrack || !("torch" in capabilities)) {
    resetTorchButton();
    setStatus("Camara abierta. Linterna no disponible en este navegador.");
    return;
  }

  torchButton.disabled = false;
  torchButton.textContent = "Encender linterna";
}

async function setTorch(enabled) {
  if (!videoTrack || !videoTrack.applyConstraints) {
    throw new Error("La camara no permite controlar la linterna.");
  }

  await videoTrack.applyConstraints({
    advanced: [{ torch: enabled }]
  });
  torchOn = enabled;
  torchButton.textContent = enabled ? "Apagar linterna" : "Encender linterna";
}

async function toggleTorch() {
  if (!videoTrack) {
    setStatus("Abre la camara antes de usar la linterna.", true);
    return;
  }

  try {
    await setTorch(!torchOn);
  } catch (e) {
    console.error("Error controlando linterna:", e);
    const detail = e && e.message ? ` Detalle: ${e.message}` : "";
    setStatus(`No se pudo controlar la linterna.${detail}`, true);
  }
}

async function startScanner() {
  if (active) return;
  active = true;

  try {
    if (!window.ZXingBrowser || !window.ZXingBrowser.BrowserMultiFormatReader) {
      throw new Error("No se cargo la libreria de escaneo.");
    }
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      throw new Error("El navegador no permite acceso a camara en este contexto.");
    }

    setStatus("Abriendo camara...");
    const codeReader = new ZXingBrowser.BrowserMultiFormatReader();
    controls = await codeReader.decodeFromConstraints(
      {
        video: { facingMode: { ideal: "environment" } },
        audio: false
      },
      videoEl,
      (result) => {
        if (!result) return;

        const text = result.getText ? result.getText() : result.text;
        setStatus(text);
        Streamlit.setComponentValue(text);
        stopScanner();
      }
    );
    setupTorchButton();
    if (!torchButton.disabled) {
      setStatus("Camara abierta. Apunta al codigo.");
    }
  } catch (e) {
    console.error("Error iniciando camara:", e);
    const detail = e && e.message ? ` Detalle: ${e.message}` : "";
    setStatus(`No se pudo acceder a la camara. Revisa permisos del navegador.${detail}`, true);
    active = false;
  }
}

function stopScanner() {
  active = false;

  try {
    if (videoTrack && torchOn) {
      videoTrack
        .applyConstraints({ advanced: [{ torch: false }] })
        .catch((e) => console.error("Error apagando linterna:", e));
    }
    if (controls) {
      controls.stop();
      controls = null;
    }
    videoEl.srcObject = null;
    resetTorchButton();
    setStatus("");
  } catch (e) {
    console.error(e);
  }
}

document.getElementById("btnStart").addEventListener("click", startScanner);
document.getElementById("btnStop").addEventListener("click", stopScanner);
torchButton.addEventListener("click", toggleTorch);

Streamlit.events.addEventListener(Streamlit.RENDER_EVENT, setHeight);
Streamlit.setComponentReady();
setHeight();
