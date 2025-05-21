localStorage.getItem("_x_darkMode_on") === "true" &&
  document.documentElement.classList.add("dark");

const match_resizer = document.querySelectorAll(".pywebview-resizer");
const minimize_button = document.getElementById("minimize-button");
const maximize_button = document.getElementById("maximize-button");
const close_button = document.getElementById("close-button");
const close_overlay = document.getElementById("close-overlay");
const close_dialog = document.getElementById("close-dialog");
const close_dialog_button = document.getElementById(
  "close-dialog-close-button"
);
const cancel_dialog_button = document.getElementById(
  "close-dialog-cancel-button"
);

match_resizer.forEach((resizer) => {
  resizer.onmousedown = () => {
    let direction = resizer.classList
      .toString()
      .replace("pywebview-resizer ", "")
      .replace("resize-", "");
    pywebview.api.resize_window(direction);
  };
});

minimize_button.onclick = () => {
  pywebview.api.minimize_window();
};

maximize_button.onclick = () => {
  pywebview.api.maximize_window();
};

close_button.onclick = () => {
  close_overlay.classList.add("close-overlay-active");
  close_dialog.classList.add("close-dialog-active");
};

close_dialog_button.onclick = () => {
  pywebview.api.close_window();
};

cancel_dialog_button.onclick = () => {
  close_overlay.classList.remove("close-overlay-active");
  close_dialog.classList.remove("close-dialog-active");
};

close_overlay.onclick = () => {
  close_overlay.classList.remove("close-overlay-active");
  close_dialog.classList.remove("close-dialog-active");
};
