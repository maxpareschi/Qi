localStorage.getItem("_x_darkMode_on") === "true" &&
  document.documentElement.classList.add("dark");

const pywebview_resizer = document.querySelectorAll(".pywebview-resizer");
const pywebview_minimize = document.querySelectorAll(".pywebview-minimize");
const pywebview_maximize = document.querySelectorAll(".pywebview-maximize");
const pywebview_close = document.querySelectorAll(".pywebview-close");

pywebview_resizer.onmousedown = () => {
  pywebview.api.start_resize();
};
pywebview_resizer.onmouseup = () => {
  pywebview.api.stop_resize();
};
pywebview_minimize.onclick = () => {
  pywebview.api.minimize_window();
};
pywebview_maximize.onclick = () => {
  pywebview.api.maximize_window();
};
pywebview_close.onclick = () => {
  pywebview.api.close_window();
};
