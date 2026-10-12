"use strict";

let workingClicks = 0;

document.getElementById("working").addEventListener("click", () => {
  workingClicks += 1;
  window.fixture.hit("working");
  document.getElementById("working-count").textContent =
    `Clicked ${workingClicks} ${workingClicks === 1 ? "time" : "times"}`;
});

document.getElementById("dead").addEventListener("click", () => {
  window.fixture.hit("dead");
});

document.getElementById("hidden").addEventListener("focus", () => {
  window.fixture.hit("hidden");
});

document.getElementById("avatar").addEventListener("click", async () => {
  await window.fixture.saveAvatar();
  document.getElementById("toast").textContent = "Saved";
});

document.getElementById("verify").addEventListener("click", (event) => {
  event.preventDefault();
  window.fixture.hit("verify");
});

document.getElementById("notes").addEventListener("input", (event) => {
  window.fixture.setText(event.target.value);
});

document.getElementById("save-file").addEventListener("click", () => {
  window.fixture.saveFile();
});
