let codeReader = null;
let active = false;

function setHeight() {
  // Let Streamlit size the iframe nicely on mobile
  Streamlit.setFrameHeight(520);
}

function setLast(text) {
  document.getElementById("last").textContent = text ? `Último: ${text}` : "";
}

async function startScanner() {
  if (active) return;
  active = true;

  setLast("");

  try {
    codeReader = new ZXing.BrowserMultiFormatReader();

    // Try default camera (on mobile it usually picks back camera)
    await codeReader.decodeFromVideoDevice(
      null,
      "video",
      (result, err) => {
        if (result) {
          const text = result.getText ? result.getText() : result.text;
          setLast(text);

          // Send value to Streamlit
          Streamlit.setComponentValue(text);

          // Stop after first successful read to avoid duplicates
          stopScanner();
        }
      }
    );
  } catch (e) {
    console.error(e);
    setLast("Error iniciando cámara. Revisa permisos.");
    active = false;
  }
}

function stopScanner() {
  if (!active) return;
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
