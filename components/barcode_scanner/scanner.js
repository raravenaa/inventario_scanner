let scanner = null;
let active = false;
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
const torchButton = document.getElementById("btnTorch");

function setHeight() {
  Streamlit.setFrameHeight(660);
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
  torchButton.disabled = true;
  torchButton.textContent = "Linterna no disponible";
}

function getSupportedFormats() {
  if (!window.Html5QrcodeSupportedFormats) return undefined;

  return [
    Html5QrcodeSupportedFormats.CODE_128,
    Html5QrcodeSupportedFormats.CODE_39,
    Html5QrcodeSupportedFormats.CODE_93,
    Html5QrcodeSupportedFormats.EAN_13,
    Html5QrcodeSupportedFormats.EAN_8,
    Html5QrcodeSupportedFormats.UPC_A,
    Html5QrcodeSupportedFormats.UPC_E,
    Html5QrcodeSupportedFormats.ITF
  ].filter((format) => format !== undefined);
}

function getScannerConfig() {
  const formatsToSupport = getSupportedFormats();
  if (!formatsToSupport || formatsToSupport.length === 0) {
    return {};
  }

  return { formatsToSupport };
}

function getQrbox(viewfinderWidth, viewfinderHeight) {
  const width = Math.max(220, Math.min(viewfinderWidth - 24, 420));
  const height = Math.max(110, Math.min(viewfinderHeight - 24, 170));
  return { width, height };
}

function setupTorchButton() {
  if (!scanner || !scanner.getRunningTrackCapabilities) {
    resetTorchButton();
    return;
  }

  const capabilities = scanner.getRunningTrackCapabilities();
  if (!capabilities || !capabilities.torch) {
    resetTorchButton();
    setStatus("Camara abierta. Linterna no disponible en este navegador.");
    return;
  }

  torchButton.disabled = false;
  torchButton.textContent = "Encender linterna";
}

async function setTorch(enabled) {
  if (!scanner || !scanner.applyVideoConstraints) {
    throw new Error("La camara no permite controlar la linterna.");
  }

  await scanner.applyVideoConstraints({
    advanced: [{ torch: enabled }]
  });
  torchOn = enabled;
  torchButton.textContent = enabled ? "Apagar linterna" : "Encender linterna";
}

async function toggleTorch() {
  if (!active || torchButton.disabled) return;

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

  try {
    if (!window.Html5Qrcode) {
      throw new Error("No se cargo la libreria de escaneo.");
    }

    active = true;
    setStatus("Abriendo camara...");
    resetTorchButton();

    scanner = new Html5Qrcode("reader", getScannerConfig());

    await scanner.start(
      { facingMode: "environment" },
      {
        fps: 12,
        qrbox: getQrbox,
        aspectRatio: 1.777778,
        disableFlip: true
      },
      (decodedText) => {
        const text = String(decodedText || "").trim();
        if (!text) return;

        setStatus(text);
        Streamlit.setComponentValue(text);
        stopScanner();
      },
      () => {}
    );

    setupTorchButton();
    if (!torchButton.disabled) {
      setStatus("Camara abierta. Apunta al codigo.");
    }
    setHeight();
  } catch (e) {
    console.error("Error iniciando camara:", e);
    const detail = e && e.message ? ` Detalle: ${e.message}` : "";
    setStatus(`No se pudo acceder a la camara.${detail}`, true);
    active = false;
    scanner = null;
  }
}

async function stopScanner() {
  active = false;

  try {
    if (scanner && torchOn) {
      await setTorch(false).catch((e) => console.error("Error apagando linterna:", e));
    }
    if (scanner) {
      await scanner.stop();
      scanner.clear();
      scanner = null;
    }
    resetTorchButton();
    setStatus("");
    setHeight();
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
