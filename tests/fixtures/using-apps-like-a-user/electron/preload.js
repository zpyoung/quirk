"use strict";

const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("fixture", {
  hit: (name) => ipcRenderer.send("hit", name),
  setText: (value) => ipcRenderer.send("text", value),
  saveAvatar: () => ipcRenderer.invoke("save-avatar"),
  saveFile: () => ipcRenderer.invoke("save-file"),
});
