let controls = null;
let active = false;

const lastEl = document.getElementById("last");
const errorEl = document.getElementById("error");
const videoEl = document.getElementById("video");

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
    setStatus("Camara abierta. Apunta al codigo.");
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
    if (controls) {
      controls.stop();
      controls = null;
    }
    videoEl.srcObject = null;
    setStatus("");
  } catch (e) {
    console.error(e);
  }
}

document.getElementById("btnStart").addEventListener("click", startScanner);
document.getElementById("btnStop").addEventListener("click", stopScanner);

Streamlit.events.addEventListener(Streamlit.RENDER_EVENT, setHeight);
Streamlit.setComponentReady();
setHeight();
