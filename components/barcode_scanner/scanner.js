let codeReader = null;
let stream = null;
let active = false;

function setHeight() {
  Streamlit.setFrameHeight(520);
}

async function startScanner() {
  if (active) return;
  active = true;

  try {
    codeReader = new ZXing.BrowserMultiFormatReader();

    // 🔑 FORZAR CÁMARA TRASERA
    const constraints = {
      video: {
        facingMode: { exact: "environment" }
      }
    };

    await codeReader.decodeFromConstraints(
      constraints,
      "video",
      (result, err) => {
        if (result) {
          const text = result.getText
            ? result.getText()
            : result.text;

          Streamlit.setComponentValue(text);
          stopScanner();
        }
      }
    );
  } catch (e) {
    console.error("Error iniciando cámara:", e);
    alert("No se pudo acceder a la cámara. Revisa permisos del navegador.");
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
  } catch (e) {
    console.error(e);
  }
}

document.getElementById("btnStart").addEventListener("click", startScanner);
document.getElementById("btnStop").addEventListener("click", stopScanner);

Streamlit.events.addEventListener(Streamlit.RENDER_EVENT, setHeight);
Streamlit.setComponentReady();
setHeight();
