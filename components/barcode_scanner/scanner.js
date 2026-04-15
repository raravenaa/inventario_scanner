let codeReader = null;
let active = false;

function setHeight() {
  Streamlit.setFrameHeight(520);
}

async function startScanner() {
  if (active) return;
  active = true;

  try {
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
          document.getElementById("last").textContent = text;
          Streamlit.setComponentValue(text);
          stopScanner();
        }
      }
    );
  } catch (e) {
    console.error("Error iniciando camara:", e);
    alert("No se pudo acceder a la camara. Revisa permisos del navegador.");
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
