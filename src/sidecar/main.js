const { app, BrowserWindow, ipcMain } = require('electron');
const fs = require('fs');

let mainWindow;
let stdinBuffer = "";
const bridgeDir = process.env.IMAGE_CLASSIFIER_BRIDGE_DIR || "";
const pythonToSidecarPath = process.env.IMAGE_CLASSIFIER_PY_TO_SIDECAR || "";
const sidecarToPythonPath = process.env.IMAGE_CLASSIFIER_SIDECAR_TO_PY || "";
let bridgeReadOffset = 0;
let bridgeWriteCounter = 1;
const seenMessageIds = new Set();

function nextBridgeId(prefix) {
  const id = `${prefix}-${bridgeWriteCounter}`;
  bridgeWriteCounter += 1;
  return id;
}

function ensureBridgeFile(filePath) {
  if (!filePath) {
    return;
  }
  try {
    fs.mkdirSync(require('path').dirname(filePath), { recursive: true });
    if (!fs.existsSync(filePath)) {
      fs.writeFileSync(filePath, '', 'utf8');
    }
  } catch (_err) {
    // Ignore bridge bootstrap errors; stdout fallback still exists.
  }
}

function sendToRenderer(message) {
  if (!message || !mainWindow || !mainWindow.webContents) {
    return;
  }

  const bridgeId = message._bridge_id;
  if (bridgeId) {
    if (seenMessageIds.has(bridgeId)) {
      return;
    }
    seenMessageIds.add(bridgeId);
  }

  mainWindow.webContents.send('from-python', message);
}

function sendToPython(message) {
  const payload = { ...message };
  if (!payload._bridge_id) {
    payload._bridge_id = nextBridgeId('js');
  }

  const serialized = JSON.stringify(payload);

  try {
    process.stdout.write(`${serialized}\n`);
  } catch (_err) {
    // Ignore stdout failures; file bridge is the fallback.
  }

  if (sidecarToPythonPath) {
    try {
      fs.appendFileSync(sidecarToPythonPath, `${serialized}\n`, 'utf8');
    } catch (_err) {
      // Ignore file bridge failures; stdout fallback may still work.
    }
  }
}

function startBridgePolling() {
  ensureBridgeFile(pythonToSidecarPath);
  ensureBridgeFile(sidecarToPythonPath);

  if (!pythonToSidecarPath) {
    return;
  }

  setInterval(() => {
    try {
      if (!fs.existsSync(pythonToSidecarPath)) {
        return;
      }

      const stats = fs.statSync(pythonToSidecarPath);
      if (stats.size < bridgeReadOffset) {
        bridgeReadOffset = 0;
      }

      if (stats.size === bridgeReadOffset) {
        return;
      }

      const fd = fs.openSync(pythonToSidecarPath, 'r');
      try {
        const length = stats.size - bridgeReadOffset;
        const buffer = Buffer.alloc(length);
        fs.readSync(fd, buffer, 0, length, bridgeReadOffset);
        bridgeReadOffset = stats.size;
        const lines = buffer.toString('utf8').split(/\r?\n/);
        for (const line of lines) {
          const trimmed = line.trim();
          if (!trimmed) {
            continue;
          }
          try {
            const message = JSON.parse(trimmed);
            sendToRenderer(message);
          } catch (_err) {
            // Ignore malformed bridge lines.
          }
        }
      } finally {
        fs.closeSync(fd);
      }
    } catch (_err) {
      // Ignore polling failures and keep retrying.
    }
  }, 200);
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 900,
    height: 700,
    webPreferences: {
      nodeIntegration: true,
      contextIsolation: false
    },
    title: "Creative Story Studio"
  });

  mainWindow.loadFile('index.html');

  // Handle data from Python via stdin
  process.stdin.on('data', (data) => {
    stdinBuffer += data.toString();
    const lines = stdinBuffer.split(/\r?\n/);
    stdinBuffer = lines.pop();

    for (const line of lines) {
      const trimmed = line.trim();
      if (!trimmed) {
        continue;
      }

      try {
        const message = JSON.parse(trimmed);
        sendToRenderer(message);
      } catch (e) {
        // Ignore malformed lines from the parent process.
      }
    }
  });

  mainWindow.on('closed', function () {
    mainWindow = null;
  });
}

app.on('ready', () => {
  createWindow();
  startBridgePolling();
});

app.on('window-all-closed', function () {
  app.quit();
});

// Relay messages from UI to Python via stdout
ipcMain.on('to-python', (event, arg) => {
  sendToPython(arg);
});
