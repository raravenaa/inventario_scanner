let codeReader = null;
let active = false;

const lastEl = document.getElementById("last");
const errorEl = document.getElementById("error");

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
    if (!window.ZXing || !window.ZXing.BrowserMultiFormatReader) {
      throw new Error("No se cargo la libreria de escaneo.");
    }

    setStatus("Abriendo camara...");
    codeReader = new ZXing.BrowserMultiFormatReader();

    const constraints = {
      video: {
        facingMode: { ideal: "environment" }
      }
    };

    await codeReader.decodeFromConstraints(
      constraints,
      "video",
      (result) => {
        if (result) {
          const text = result.getText ? result.getText() : result.text;
          setStatus(text);
          Streamlit.setComponentValue(text);
          stopScanner();
        }
      }
    );
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
    if (codeReader) {
      codeReader.reset();
      codeReader = null;
    }
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
