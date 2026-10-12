"use strict";

const fs = require("fs");
const http = require("http");
const os = require("os");
const path = require("path");
const { app, BrowserWindow, dialog, ipcMain } = require("electron");

const state = {
  hits: { working: 0, dead: 0, hidden: 0, verify: 0, delete: 0, save: 0 },
  text: "",
  saved_path: null,
};

const statePath = path.resolve(
  process.env.LIKEUSER_FIXTURE_STATE ||
    path.join(fs.mkdtempSync(path.join(os.tmpdir(), "likeuser-electron-")), "state.json")
);

function writeState() {
  const tmp = `${statePath}.tmp`;
  fs.writeFileSync(tmp, JSON.stringify(state));
  fs.renameSync(tmp, statePath);
}

writeState();
process.stdout.write(`STATE ${statePath}\n`);

// avatar endpoint always fails so the renderer's "Saved" toast is a lie
const apiServer = http.createServer((req, res) => {
  res.writeHead(500, { "Content-Type": "text/plain" });
  res.end("avatar store unavailable");
});

function startApiServer() {
  return new Promise((resolve) => {
    apiServer.listen(0, "127.0.0.1", () => resolve(apiServer.address().port));
  });
}

function postAvatar(port) {
  return new Promise((resolve) => {
    const req = http.request(
      { host: "127.0.0.1", port, path: "/api/avatar", method: "POST" },
      (res) => {
        res.resume();
        res.on("end", () => resolve(res.statusCode));
      }
    );
    req.on("error", () => resolve(0));
    req.end();
  });
}

function registerIpc(win, apiPort) {
  ipcMain.on("hit", (_event, name) => {
    if (Object.prototype.hasOwnProperty.call(state.hits, name)) {
      state.hits[name] += 1;
      writeState();
    }
  });

  ipcMain.on("text", (_event, value) => {
    state.text = String(value);
    writeState();
  });

  ipcMain.handle("save-avatar", async () => {
    state.hits.save += 1;
    writeState();
    return postAvatar(apiPort);
  });

  ipcMain.handle("save-file", async () => {
    const result = await dialog.showSaveDialog(win, {
      title: "Save file",
      defaultPath: "likeuser-fixture.txt",
    });
    if (result.canceled || !result.filePath) {
      return null;
    }
    fs.writeFileSync(result.filePath, "likeuser fixture file\n");
    state.saved_path = result.filePath;
    writeState();
    return result.filePath;
  });
}

async function createWindow() {
  const apiPort = await startApiServer();
  const win = new BrowserWindow({
    width: 720,
    height: 640,
    title: "Likeuser Fixture",
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });
  registerIpc(win, apiPort);
  await win.loadFile(path.join(__dirname, "index.html"));
}

app.whenReady().then(createWindow);

app.on("window-all-closed", () => {
  apiServer.close();
  app.quit();
});
